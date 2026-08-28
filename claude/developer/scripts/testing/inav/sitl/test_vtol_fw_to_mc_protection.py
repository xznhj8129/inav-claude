#!/usr/bin/env python3
"""
SITL reproduction test for PR #11553 (iNavFlight/inav "auto VTOL smooth
transition") - low-speed FW->MC protection abort race, combined with its
positive control, as a single parameterized script.

Background / suspected bug (src/main/flight/mixer_profile.c):

  shouldRequestManualFwToMcProtection()/outputProfileUpdateTask() starts a
  FW->MC auto transition (mixerATUpdateState(MIXERAT_REQUEST_MANUAL_TO_MC))
  when trusted airspeed drops below vtol_fw_to_mc_auto_switch_airspeed_cm_s,
  but never sets manualProfileSwitchAutoTransitionActive = true. Later in
  the SAME function call, the manual-switch abort detector:

      transitionSwitchAbort = !manualProfileSwitchAutoTransitionActive &&
                               !transitionModeActive;

  evaluates true (the pilot is not touching BOXMIXERTRANSITION) and
  immediately calls abortTransition(), cancelling the just-started
  protection transition before mixerProfileAT.hotSwitchDone is ever
  reached.

This script has two scenarios, selected with --scenario, that share ALL
setup/teardown/profile-pair-config/polling code and differ ONLY in the
airspeed level and whether BOXMIXERTRANSITION is toggled - by design, so
the two runs are apples-to-apples comparable:

  --scenario negative (the suspected-bug repro):
      Airspeed is dropped BELOW vtol_fw_to_mc_auto_switch_airspeed_cm_s
      after arming, and BOXMIXERTRANSITION is NEVER touched. Predicted
      bug-confirmed behavior: the mixer profile never leaves FW - phase
      cycles IDLE -> TRANSITION_INITIALIZE/TRANSITIONING -> IDLE (abort)
      every scheduler tick, and the aborted flag latches true.
      Equivalent to the former test_vtol_fw_to_mc_protection_abort.py.

  --scenario positive (positive control):
      Airspeed is kept HIGH throughout (protection never fires), and
      BOXMIXERTRANSITION IS actively toggled LOW->HIGH to request a normal
      manual FW->MC transition (the RC-switch path this PR also
      implements, separate from the low-airspeed auto-protection path).
      Expected: the switch completes and the mixer profile settles on MC
      and stays there. This validates that the shared test harness and
      profile-pair configuration are actually capable of completing a real
      hot-switch, ruling out "test setup is broken" as an explanation for
      a negative-scenario result.
      Equivalent to the former test_vtol_manual_transition_positive_control.py.

Setup avoids GPS entirely to keep the airspeed source fully deterministic:
  - pitot_hardware = MSP (driven via MSP2_SENSOR_AIRSPEED / diffPressurePa,
    converted from a target airspeed using the same formula pitotmeter.c
    uses: airSpeed_cms = pitot_scale * sqrt(2*|dP|/SSL_AIR_DENSITY) * 100)
  - mixer_profile 1 = AIRPLANE (FW) with
    mixer_vtol_manualswitch_autotransition_controller = ON
  - mixer_profile 2 = MULTIROTOR (simple QUADX mmix)
  - mixer_switch_trans_timer = 100 (10s) - REQUIRED to observe either
    scenario meaningfully: with the default 0, mixerATUpdateState()'s
    do/while(reprocessState) loop drives IDLE -> INIT -> TRANSITIONING ->
    hot-switch synchronously within the SAME call that starts the
    transition (the timer-ready check is elapsedMs >= 0, trivially true),
    so hotSwitchDone becomes true before the abort-detector code even
    runs in the negative scenario, and the positive scenario would
    complete too fast to usefully observe the TRANSITIONING phase either.
  - vtol_fw_to_mc_auto_switch_airspeed_cm_s = 500 (5 m/s)
  - BOXMIXERPROFILE and BOXMIXERTRANSITION mode ranges configured
    (present, required for checkMixerATRequired()) on AUX2/AUX3.

Usage:
    python3 test_vtol_fw_to_mc_protection.py --scenario negative [port]
    python3 test_vtol_fw_to_mc_protection.py --scenario positive [port]

    Default port: 5761

Note: run with dangerouslyDisableSandbox in the Claude sandbox - this
script needs a raw TCP socket to localhost.
"""

import sys
import time
import struct
import socket
import threading
import argparse

# ---------------------------------------------------------------------------
# MSP command IDs
# ---------------------------------------------------------------------------
MSP_API_VERSION      = 1
MSP_SET_RAW_RC        = 200
MSP2_INAV_STATUS       = 0x2000
MSP2_INAV_DEBUG        = 0x2019
MSP2_SENSOR_AIRSPEED   = 0x1F06
MSP_SIMULATOR          = 0x201F

RC_LOW, RC_MID, RC_HIGH = 1000, 1500, 2000
SSL_AIR_DENSITY = 1.225  # kg/m^3, matches src/main/common/maths.h
HITL_ENABLE = (1 << 0)
SIMULATOR_MSP_VERSION_LITE = 2

THRESHOLD_CM_S = 500     # vtol_fw_to_mc_auto_switch_airspeed_cm_s
ABOVE_CM_S = 1500.0      # normal FW cruise / positive-control airspeed
BELOW_CM_S = 200.0       # negative-scenario trigger airspeed

# Per docs/MixerProfile.md "VTOL transition debug mode" section:
#   debug[0] = transition phase (0=IDLE,1=INIT,2=TRANSITIONING,3=POST_SWITCH_FADE)
#   debug[1] = request | (direction<<8) | (waitReason<<16)
#   debug[2] bit7  = transition aborted
#   debug[2] bit8  = manual VTOL auto-transition controller enabled (current profile)
#   debug[2] bits10-11 = current mixer profile index
#   debug[2] bit20 = manual transition session latched
PHASE_NAMES = {0: "IDLE", 1: "TRANSITION_INITIALIZE", 2: "TRANSITIONING", 3: "POST_SWITCH_FADE"}


# ---------------------------------------------------------------------------
# MSP framing (v1 + v2)
# ---------------------------------------------------------------------------

def _crc8_dvb_s2(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0xD5) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
    return crc


def build_v1(cmd: int, data: bytes = b"") -> bytes:
    d = bytes(data)
    cs = len(d) ^ cmd
    for b in d:
        cs ^= b
    return bytes([0x24, 0x4D, 0x3C, len(d), cmd]) + d + bytes([cs])


def build_v2(cmd: int, data: bytes = b"") -> bytes:
    p = bytes(data)
    h = bytes([0x24, 0x58, 0x3C, 0x00,
               cmd & 0xFF, (cmd >> 8) & 0xFF,
               len(p) & 0xFF, (len(p) >> 8) & 0xFF])
    return h + p + bytes([_crc8_dvb_s2(h[3:] + p)])


def parse_msp(buf: bytes):
    i = 0
    while i < len(buf) - 4:
        if buf[i] == 0x24:
            if buf[i + 1] == 0x4D and i + 5 <= len(buf):
                size = buf[i + 3]
                cmd = buf[i + 4]
                if i + 5 + size <= len(buf):
                    return cmd, buf[i + 5:i + 5 + size]
            elif buf[i + 1] == 0x58 and i + 9 <= len(buf):
                size = buf[i + 6] | (buf[i + 7] << 8)
                cmd = buf[i + 4] | (buf[i + 5] << 8)
                if i + 9 + size <= len(buf):
                    return cmd, buf[i + 8:i + 8 + size]
        i += 1
    return None, None


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

class FC:
    def __init__(self, host: str, port: int, timeout=3.0):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.settimeout(timeout)
        self.s.connect((host, port))
        self._lock = threading.Lock()

    def send_raw(self, data: bytes):
        with self._lock:
            self.s.sendall(data)

    def recv_raw(self, timeout=1.0, maxlen=65536) -> bytes:
        self.s.settimeout(timeout)
        try:
            return self.s.recv(maxlen)
        except (socket.timeout, OSError):
            return b""

    def recv(self, timeout=1.0):
        self.s.settimeout(timeout)
        buf = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                chunk = self.s.recv(1024)
                if not chunk:
                    break
                buf += chunk
                cmd, data = parse_msp(buf)
                if cmd is not None:
                    return cmd, data
            except socket.timeout:
                break
        return parse_msp(buf)

    def exchange(self, frame: bytes, timeout=1.0):
        self.send_raw(frame)
        return self.recv(timeout)

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CLI configuration phase (IDENTICAL for both scenarios)
# ---------------------------------------------------------------------------

def cli_send_and_wait(fc: FC, line: str, settle=0.15):
    fc.send_raw((line + "\n").encode("ascii"))
    time.sleep(settle)
    return fc.recv_raw(timeout=0.3).decode("ascii", errors="replace")


def configure_via_cli(fc: FC, threshold_cm_s: int) -> str:
    """
    Enter CLI mode ('#') and push the full VTOL/pitot/mode setup, then
    'save' (which reboots the FC). Returns the accumulated CLI transcript
    for diagnostics. Used unchanged by both --scenario negative and
    --scenario positive, so both runs share an identical profile-pair
    configuration and mixer_switch_trans_timer.
    """
    transcript = [cli_send_and_wait(fc, "#", settle=0.3)]

    commands = [
        "mixer_profile 1",
        "set platform_type = AIRPLANE",
        "set mixer_vtol_manualswitch_autotransition_controller = ON",
        "mmix reset",
        "mmix 0 1.0 0.0 0.0 0.0",
        "mixer_profile 2",
        "set platform_type = MULTIROTOR",
        "mmix reset",
        "mmix 0 1.0 -1.0  1.0 -1.0",
        "mmix 1 1.0 -1.0 -1.0  1.0",
        "mmix 2 1.0  1.0  1.0  1.0",
        "mmix 3 1.0  1.0 -1.0 -1.0",
        "mixer_profile 1",
        # Non-zero transition timer is required to usefully observe either
        # scenario - see module docstring.
        "set mixer_switch_trans_timer = 100",
        "set pitot_hardware = MSP",
        f"set vtol_fw_to_mc_auto_switch_airspeed_cm_s = {threshold_cm_s}",
        "set debug_mode = VTOL_TRANSITION",
        "set receiver_type = MSP",
        "aux 0 0 0 1700 2100",
        "aux 1 62 1 1700 2100",
        "aux 2 63 2 1700 2100",
    ]
    for cmd in commands:
        transcript.append(cli_send_and_wait(fc, cmd))

    transcript.append(cli_send_and_wait(fc, "save", settle=0.5))
    return "\n".join(transcript)


# ---------------------------------------------------------------------------
# RC + pitot sender thread (shared)
# ---------------------------------------------------------------------------

def airspeed_cms_to_diff_pressure_pa(airspeed_cm_s: float) -> float:
    """Inverse of pitotmeter.c's pitot_scale*sqrt(2*|dP|/SSL_AIR_DENSITY)*100 with pitot_scale=1.0."""
    v_ms = airspeed_cm_s / 100.0
    return 0.5 * SSL_AIR_DENSITY * v_ms * v_ms


def build_rc(throttle, roll=RC_MID, pitch=RC_MID, yaw=RC_MID,
             aux1=RC_LOW, aux2=RC_LOW, aux3=RC_LOW) -> bytes:
    channels = [roll, pitch, throttle, yaw, aux1, aux2, aux3] + [RC_MID] * 9
    data = b"".join(struct.pack('<H', ch) for ch in channels)
    return build_v1(MSP_SET_RAW_RC, data)


def build_airspeed_pkt(airspeed_cm_s: float) -> bytes:
    dp = airspeed_cms_to_diff_pressure_pa(airspeed_cm_s)
    payload = struct.pack('<BIfh', 0, 0, dp, 0)  # instance, timeMs, diffPressurePa, temp(centi-C)
    return build_v2(MSP2_SENSOR_AIRSPEED, payload)


class Sender:
    """Background 50Hz sender for RC + MSP2_SENSOR_AIRSPEED, shared by both scenarios."""

    def __init__(self, fc: FC):
        self._fc = fc
        self.throttle = RC_LOW
        self.aux1 = RC_LOW   # ARM
        self.aux2 = RC_LOW   # BOXMIXERPROFILE - inactive for both scenarios
        self.aux3 = RC_LOW   # BOXMIXERTRANSITION - negative: never touched; positive: toggled HIGH
        self.airspeed_cm_s = ABOVE_CM_S
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def set(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def _loop(self):
        while self._running:
            with self._lock:
                t, a1, a2, a3, spd = self.throttle, self.aux1, self.aux2, self.aux3, self.airspeed_cm_s
            try:
                self._fc.send_raw(build_rc(t, aux1=a1, aux2=a2, aux3=a3))
                self._fc.send_raw(build_airspeed_pkt(spd))
            except Exception:
                pass
            time.sleep(0.02)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# MSP readers (shared)
# ---------------------------------------------------------------------------

def ping(fc: FC) -> bool:
    cmd, data = fc.exchange(build_v1(MSP_API_VERSION), timeout=2.0)
    return data is not None


def enable_lightweight_hitl(fc: FC) -> None:
    """
    Enable just enough HITL to bypass ACC/COMPASS calibration timing (same
    lightweight trick used by sitl_arm_test.py) - no GPS/attitude/pressure
    sensor payload sent, so it does not interfere with the MSP-driven pitot
    injection used by this test.
    """
    payload = struct.pack('<BB', SIMULATOR_MSP_VERSION_LITE, HITL_ENABLE)
    fc.send_raw(build_v2(MSP_SIMULATOR, payload))
    fc.recv_raw(timeout=0.2)


def read_arming_flags(fc: FC):
    cmd, data = fc.exchange(build_v2(MSP2_INAV_STATUS), timeout=1.0)
    if data and len(data) >= 13:
        return struct.unpack_from('<I', data, 9)[0]
    return None


ARMED_BIT = (1 << 2)
BLOCKER_NAMES = {
    (1 << 9): "SENSORS_CALIBRATING",
    (1 << 10): "SYSTEM_OVERLOADED",
    (1 << 11): "NAVIGATION_UNSAFE",
    (1 << 12): "COMPASS_NOT_CALIBRATED",
    (1 << 13): "ACCEL_NOT_CALIBRATED",
    (1 << 14): "ARM_SWITCH",
    (1 << 15): "HARDWARE_FAILURE",
    (1 << 16): "BOXFAILSAFE",
    (1 << 18): "RC_LINK",
    (1 << 19): "THROTTLE",
    (1 << 20): "CLI",
    (1 << 23): "ROLLPITCH_NOT_CENTERED",
    (1 << 26): "INVALID_SETTING",
    (1 << 27): "PWM_OUTPUT_ERROR",
}


def decode_blockers(af: int):
    return [name for bit, name in BLOCKER_NAMES.items() if af & bit]


def read_debug(fc: FC, timeout=1.0):
    cmd, data = fc.exchange(build_v2(MSP2_INAV_DEBUG), timeout=timeout)
    if data and len(data) >= 32:
        return struct.unpack_from('<8i', data, 0)
    return None


def decode_debug2(flags: int):
    return {
        "direction": flags & 0x3,
        "auto_ctrl_active": bool(flags & (1 << 2)),
        "mixing_output_active": bool(flags & (1 << 3)),
        "rc_mixertransition_active": bool(flags & (1 << 4)),
        "airspeed_controlled": bool(flags & (1 << 5)),
        "profile_change_done": bool(flags & (1 << 6)),
        "aborted": bool(flags & (1 << 7)),
        "manual_controller_enabled": bool(flags & (1 << 8)),
        "dynamic_mixer_enabled": bool(flags & (1 << 9)),
        "current_profile_idx": (flags >> 10) & 0x3,
        "next_profile_idx": (flags >> 12) & 0x3,
        "manual_allowed_by_nav": bool(flags & (1 << 14)),
        "mission_active": bool(flags & (1 << 15)),
        "mixing_requested": bool(flags & (1 << 16)),
        "failsafe": bool(flags & (1 << 17)),
        "manual_ctrl_effective": bool(flags & (1 << 18)),
        "rc_mixerprofile_active": bool(flags & (1 << 19)),
        "session_latched": bool(flags & (1 << 20)),
    }


# ---------------------------------------------------------------------------
# Shared setup: connect, CLI-configure+reboot, reconnect, arm
# ---------------------------------------------------------------------------

def connect_configure_and_arm(host: str, port: int, arm_airspeed_cm_s: float):
    """
    Shared by both scenarios: connect, push identical CLI config, reboot,
    reconnect, start the RC/airspeed sender, enable lightweight HITL, and
    arm in FW. Returns (fc, sender) on success, or (None, None) with a
    printed reason on failure.
    """
    try:
        fc = FC(host, port)
    except Exception as e:
        print(f"ERROR: Cannot connect to {host}:{port}: {e}")
        print("  Check: Is SITL running? ss -tln | grep 576")
        print("  Note: if in a sandbox, localhost/SITL ports should be allowlisted;")
        print("  if still blocked, this may need dangerouslyDisableSandbox or asking the user.")
        return None, None

    if not ping(fc):
        print("ERROR: FC not responding to MSP. It may already be in CLI mode from")
        print("  a previous run - try sending 'exit\\n' or restarting SITL.")
        fc.close()
        return None, None
    print("[OK] FC responding to MSP")

    print("\n--- Phase 1: CLI configuration (FW/MC profile pair, shared by both scenarios) ---")
    transcript = configure_via_cli(fc, THRESHOLD_CM_S)
    fc.close()
    if "Invalid" in transcript or "ERROR" in transcript.upper():
        print("WARNING: CLI transcript contains possible errors:")
        for line in transcript.splitlines():
            if "Invalid" in line or "ERROR" in line.upper():
                print(f"    {line}")
    print("  CLI configuration sent, 'save' issued (FC rebooting)...")
    print("\n  Waiting 18s for SITL reboot + sensor calibration (incl. 4s pitot calib)...")
    time.sleep(18)

    print("\n--- Phase 2: Reconnect after reboot ---")
    try:
        fc = FC(host, port)
    except Exception as e:
        print(f"ERROR reconnecting: {e}")
        return None, None
    if not ping(fc):
        print("ERROR: FC not responding after reboot")
        fc.close()
        return None, None
    print("[OK] Reconnected")

    sender = Sender(fc)
    sender.set(throttle=RC_LOW, aux1=RC_LOW, aux2=RC_LOW, aux3=RC_LOW,
               airspeed_cm_s=arm_airspeed_cm_s)
    sender.start()

    print("  Enabling lightweight HITL to bypass ACC/COMPASS calibration timing...")
    enable_lightweight_hitl(fc)
    print("  Holding AUX1 LOW for 2s to let ARM_SWITCH/SENSORS_CALIBRATING clear...")
    time.sleep(2.0)

    print(f"\n--- Phase 3: Arm (FW profile, airspeed {arm_airspeed_cm_s:.0f} cm/s) ---")
    sender.set(aux1=RC_HIGH)
    armed = False
    af = None
    for i in range(100):
        time.sleep(0.1)
        af = read_arming_flags(fc)
        if af is not None and (af & ARMED_BIT):
            armed = True
            print(f"  Armed after {(i + 1) * 0.1:.1f}s")
            break
        if i % 20 == 19 and af is not None:
            print(f"  t={i * 0.1:.1f}s: flags=0x{af:08X} blockers={decode_blockers(af)}")

    if not armed:
        blockers = decode_blockers(af or 0)
        print(f"  FAILED TO ARM. Blockers: {blockers}")
        print("  Cannot proceed with reproduction - test result is INCONCLUSIVE.")
        sender.stop()
        fc.close()
        return None, None

    time.sleep(1.0)
    d = read_debug(fc)
    if d:
        d2 = decode_debug2(d[2])
        print(f"\n  Baseline (armed, FW, airspeed {arm_airspeed_cm_s:.0f} cm/s): "
              f"phase={d[0]}({PHASE_NAMES.get(d[0], '?')})  "
              f"manual_controller_enabled={d2['manual_controller_enabled']}  "
              f"current_profile_idx={d2['current_profile_idx']}  aborted={d2['aborted']}")
        if not d2["manual_controller_enabled"]:
            print("  WARNING: manual_controller_enabled is FALSE. shouldRequestManualFwToMcProtection()")
            print("  requires this to be true (mixer_vtol_manualswitch_autotransition_controller=ON")
            print("  on the FW profile) - the protection cannot trigger at all with this off.")
    else:
        print("  WARNING: could not read MSP2_INAV_DEBUG for baseline sample")

    return fc, sender


def sample_debug_series(fc: FC, duration_s: float, interval_s: float,
                         burst_s: float = 0.0, label: str = "") -> list:
    """
    Poll MSP2_INAV_DEBUG for duration_s seconds, printing each sample.
    If burst_s > 0, poll as fast as possible for the first burst_s seconds
    (used by the negative scenario to try to catch mid-transition phases
    between same-tick abort cycles), then continue at interval_s spacing.
    Returns the list of (t, phase, decoded_debug2) samples.
    """
    samples = []
    t0 = time.time()

    def sample_once(t):
        d = read_debug(fc, timeout=0.3)
        if d:
            d2 = decode_debug2(d[2])
            req = d[1] & 0xFF
            direction = (d[1] >> 8) & 0xFF
            samples.append((t, d[0], d2))
            print(f"  t={t:6.3f}s  phase={d[0]}({PHASE_NAMES.get(d[0], '?'):22s})  "
                  f"req={req} dir={direction}  aborted={str(d2['aborted']):5s}  "
                  f"cur_profile={d2['current_profile_idx']}  "
                  f"mixing_active={d2['mixing_output_active']}  "
                  f"rc_mt_active={d2['rc_mixertransition_active']}")
        else:
            print(f"  t={t:6.3f}s  <no debug data>")

    if burst_s > 0:
        print(f"  {label}-- burst phase: polling as fast as possible for {burst_s:.0f}s to try to catch")
        print("     mid-transition phases (INIT/TRANSITIONING) between abort cycles --")
        burst_deadline = time.time() + burst_s
        while time.time() < burst_deadline:
            sample_once(time.time() - t0)

    remaining_label = "steady" if burst_s > 0 else "sampling"
    print(f"  {label}-- {remaining_label} phase: ~{1.0/interval_s:.1f}Hz for the rest of the window --")
    while time.time() - t0 < duration_s:
        sample_once(time.time() - t0)
        time.sleep(interval_s)

    return samples


# ---------------------------------------------------------------------------
# Scenario: negative (suspected-bug repro)
# ---------------------------------------------------------------------------

def run_negative(host: str, port: int) -> int:
    print("=" * 72)
    print("SCENARIO: negative (suspected-bug repro)")
    print("PR #11553 - FW->MC low-airspeed protection abort race")
    print("=" * 72)
    print(f"Target: {host}:{port}")
    print(f"vtol_fw_to_mc_auto_switch_airspeed_cm_s = {THRESHOLD_CM_S}")
    print(f"Above-threshold arming airspeed: {ABOVE_CM_S} cm/s")
    print(f"Below-threshold (trigger) airspeed: {BELOW_CM_S} cm/s")
    print("BOXMIXERTRANSITION (AUX3) is NEVER toggled during this scenario.")
    print()

    fc, sender = connect_configure_and_arm(host, port, ABOVE_CM_S)
    if fc is None:
        return 2

    print(f"\n--- Phase 4: Drop airspeed to {BELOW_CM_S} cm/s (below {THRESHOLD_CM_S} threshold) ---")
    print("  AUX3 (BOXMIXERTRANSITION) stays LOW throughout.")
    sender.set(airspeed_cm_s=BELOW_CM_S)

    samples = sample_debug_series(fc, duration_s=15.0, interval_s=0.5, burst_s=3.0)

    sender.stop()
    fc.close()

    print("\n" + "=" * 72)
    print("ANALYSIS")
    print("=" * 72)
    if not samples:
        print("VERDICT: INCONCLUSIVE - no debug samples collected.")
        return 3

    phases_seen = sorted(set(s[1] for s in samples))
    reached_mc = any(s[2]["current_profile_idx"] == 1 for s in samples)
    ended_on_mc = samples[-1][2]["current_profile_idx"] == 1
    ever_aborted = any(s[2]["aborted"] for s in samples)
    aborted_at_end = samples[-1][2]["aborted"]
    abort_rising_edges = sum(
        1 for i in range(1, len(samples))
        if samples[i][2]["aborted"] and not samples[i - 1][2]["aborted"]
    )
    idle_after_nonidle = sum(
        1 for i in range(1, len(samples))
        if samples[i][1] == 0 and samples[i - 1][1] != 0
    )

    print(f"  Phases observed: {[PHASE_NAMES.get(p, p) for p in phases_seen]}")
    print(f"  current_profile_idx reached MC(1) at any point: {reached_mc}")
    print(f"  current_profile_idx == MC(1) at end of sampling: {ended_on_mc}")
    print(f"  aborted flag ever True: {ever_aborted}  (rising edges: {abort_rising_edges})")
    print(f"  aborted flag True at end of sampling: {aborted_at_end}")
    print(f"  Number of phase transitions back to IDLE from non-IDLE: {idle_after_nonidle}")

    if ended_on_mc and not ever_aborted:
        print("\nVERDICT: NOT CONFIRMED")
        print("  The mixer profile actually switched to MC and stayed there, with no")
        print("  abort ever observed. This does NOT match the predicted bug behavior.")
        return 0
    elif (not reached_mc) and ever_aborted:
        print("\nVERDICT: CONFIRMED")
        print("  The mixer profile NEVER reached MC despite airspeed staying below")
        print("  the configured protection threshold and BOXMIXERTRANSITION never")
        print("  being touched, and the transition-aborted flag was observed set.")
        print("  This matches the predicted bug: shouldRequestManualFwToMcProtection()")
        print("  starts a transition (mixerATUpdateState(MIXERAT_REQUEST_MANUAL_TO_MC))")
        print("  that the manual-switch abort detector in the same outputProfileUpdateTask()")
        print("  call immediately cancels, every tick, because")
        print("  manualProfileSwitchAutoTransitionActive was never set for this path.")
        return 1
    else:
        print("\nVERDICT: INCONCLUSIVE")
        print("  Results do not cleanly match either predicted outcome. Inspect")
        print("  the raw sample log above.")
        return 3


# ---------------------------------------------------------------------------
# Scenario: positive (positive control)
# ---------------------------------------------------------------------------

def run_positive(host: str, port: int) -> int:
    print("=" * 72)
    print("SCENARIO: positive (positive control)")
    print("PR #11553 - manual MIXER-TRANSITION FW->MC switch (airspeed HIGH)")
    print("=" * 72)
    print(f"Target: {host}:{port}")
    print(f"vtol_fw_to_mc_auto_switch_airspeed_cm_s = {THRESHOLD_CM_S} (kept OUT of range)")
    print(f"Airspeed held at {ABOVE_CM_S} cm/s throughout (protection must NOT fire)")
    print("BOXMIXERTRANSITION (AUX3) WILL be toggled LOW->HIGH to request a manual transition.")
    print()

    fc, sender = connect_configure_and_arm(host, port, ABOVE_CM_S)
    if fc is None:
        return 2

    print("\n--- Phase 4: Toggle BOXMIXERTRANSITION (AUX3) LOW->HIGH, request manual FW->MC ---")
    sender.set(aux3=RC_HIGH)

    samples = sample_debug_series(fc, duration_s=15.0, interval_s=0.3, burst_s=0.0)

    sender.stop()
    fc.close()

    print("\n" + "=" * 72)
    print("ANALYSIS")
    print("=" * 72)
    if not samples:
        print("VERDICT: INCONCLUSIVE - no debug samples collected.")
        return 3

    reached_mc = any(s[2]["current_profile_idx"] == 1 for s in samples)
    ended_on_mc = samples[-1][2]["current_profile_idx"] == 1
    ever_aborted = any(s[2]["aborted"] for s in samples)
    phases_seen = sorted(set(s[1] for s in samples))

    print(f"  Phases observed: {[PHASE_NAMES.get(p, p) for p in phases_seen]}")
    print(f"  current_profile_idx reached MC(1) at any point: {reached_mc}")
    print(f"  current_profile_idx == MC(1) at end of sampling: {ended_on_mc}")
    print(f"  aborted flag ever True during this run: {ever_aborted}")

    if ended_on_mc:
        print("\nVERDICT: CONFIRMED-VALID")
        print("  The manual MIXER-TRANSITION path DID complete the switch to MC and")
        print("  stayed there, using the SAME profile pair / same mixer_switch_trans_timer")
        print("  as the negative scenario. This validates that the shared test harness and")
        print("  profile-pair configuration ARE capable of completing a real hot-switch,")
        print("  so a negative-scenario result (protection trigger -> stuck on FW) is a")
        print("  genuine finding about the PR's low-airspeed-protection code path, not a")
        print("  test-setup artifact.")
        return 0
    else:
        print("\nVERDICT: SETUP-SUSPECT")
        print("  The manual MIXER-TRANSITION path ALSO never reached MC. This means a")
        print("  negative-scenario result would be INCONCLUSIVE - something in the shared")
        print("  test setup (not necessarily the PR's code) is preventing ANY hot-switch to MC.")
        return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("port", nargs="?", default="5761")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--scenario", choices=["negative", "positive"], required=True,
                         help="'negative' = suspected-bug repro (low airspeed, switch untouched); "
                              "'positive' = positive control (high airspeed, switch toggled)")
    args = parser.parse_args()

    if args.scenario == "negative":
        return run_negative(args.host, int(args.port))
    else:
        return run_positive(args.host, int(args.port))


if __name__ == "__main__":
    sys.exit(main())
