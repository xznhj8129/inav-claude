# No-RC Control — Design

**Status:** Planning only, no code
**Date:** 2026-08-26

Operate INAV aircraft with no RC transmitter. Control via telemetry link, navigation autonomous, firmware keeps link-loss safety response.

---

## 1. Pilot vs Command

One new setting: `control_mode` = `PILOT` (default) | `COMMAND`.

- **Pilot** — RC channels drive arming, modes, flight. Any transport (serial RX, MSP RC, telemetry-carried RC). Behavior identical to today.
- **Command** — telemetry commands only, NAV modes only. Channels are irrelevant: not read, not used for arming/modes/flight.

Configuration-time, explicit, not inferred from `receiverType`. Default `PILOT` preserves all existing behavior.

**The invariant:** in Command mode, any code that reads a channel value to decide something is a defect. Channels freeze at init values (all 1500, throttle 885) — plausible, well-formed, meaningless. ~39 call sites affected (`throttleStickIsLow` 18, `isRollPitchStickDeflected` 10, `checkStickPosition` 8, `throttleStickMixedValue` 3).

"Manual" is taken (`MANUAL_MODE` at `runtime_config.h:99`, `BOXMANUAL = 10`). Hence **Pilot vs Command**.

### Open items

- Exact setting name / enum spelling (`control_mode` / `CONTROL_MODE_PILOT` proposed)
- Whether Command requires telemetry failsafe enabled (likely no hard requirement, consistent with "onus on user")
- Global or per-platform (expected: global)

---

## 2. Telemetry-link heartbeat failsafe

Second liveness source, independent of RC. Modeled on PX4 `COM_DL_LOSS_T` / ArduPilot `FS_GCS_ENABLE`.

### How INAV failsafe works today

Single liveness chain: `rx.c:544-548` → `failsafeOnValidDataReceived/Failed()` → `rxLinkState` boolean → `failsafeIsReceivingRxData()` → `ARMING_DISABLED_RC_LINK`. No telemetry-link liveness exists.

### Design

- New `lastTelemHeartbeatAt` timestamp, evaluated in `failsafeUpdateState`.
- Heartbeat source: MSP activity on configured RX/telemetry port(s) only (not global — USB/bench sessions don't count). `mspPort_t.lastActivityMs` already exists (`msp_serial.h:88`). Dedicated MSP heartbeat message deferred. MAVLink heartbeat follow-on (depends on `mavlink_multiport` inbound work).
- Liveness source **derived from control mode**: Pilot → RC loss triggers failsafe (unchanged); Command → telemetry heartbeat loss triggers failsafe. The old "Option C — RC senior, telemetry fallback" ladder is not a separate rule; it falls out of which mode you're in.
- Existing `failsafe_procedure` reused (AUTO_LANDING / DROP / RTH / NONE). No new procedures.

### Settings

| Setting | Default |
|---|---|
| `failsafe_telem_link_enabled` | OFF |
| `failsafe_telem_link_timeout` | 5 s |
| `failsafe_telem_link_source` | MSP (enum: MSP / MAVLINK / ANY) |

### Arming

- New `ARMING_DISABLED_TELEM_LINK` flag, set only when RC absent + telemetry stale.
- `ARMING_DISABLED_RC_LINK` unchanged — set only when RC is the control link.
- Mutually exclusive by construction (control mode decides which applies). Existing `isArmingDisabled()` OR correct as-is.
- No hard "at least one source" requirement. Advisory warning only if both disabled.

---

## 3. MC auto-launch

MCs have no auto-takeoff (`nav_fw_launch_*` exists for FW; nothing for MC). Required for headless operation.

### Sequence

1. Armed → motors idle
2. Wait `nav_mc_launch_idle_motor_delay`
3. Ramp throttle idle → `nav_mc_launch_thr` over `nav_mc_launch_spinup_time`, attitude ANGLE centered (no position control)
4. Climb to `nav_mc_launch_poshold_switch_alt` (default 200 cm) — altitude threshold, not timer
5. Switch to NAV POSHOLD targeting home GPS + `nav_mc_launch_altitude`, climbing at existing `nav_mc_auto_climb_rate`
6. At `nav_mc_launch_altitude`, LAUNCH ends → `nav_mc_launch_next_mode` (POSHOLD or WP)

### Settings

| Setting | Notes |
|---|---|
| `nav_mc_launch_thr` | takeoff throttle |
| `nav_mc_launch_spinup_time` | ramp duration |
| `nav_mc_launch_idle_motor_delay` | arm-to-spinup delay |
| `nav_mc_launch_poshold_switch_alt` | cm, default 200, switch to POSHOLD |
| `nav_mc_launch_altitude` | cm, LAUNCH end altitude |
| `nav_mc_launch_next_mode` | POSHOLD or WP |
| `nav_mc_launch_abort_time` | default 10 s |
| `nav_mc_auto_climb_rate` | **already exists** (`settings.yaml:2878`) |

### State machine

`navigation_mc_launch.c` (new), mirroring `navigation_fw_launch.c` pattern:

`IDLE_MOTOR_DELAY → MOTOR_SPINUP → CLIMB_TO_SWITCH_ALT → POSHOLD_CLIMB → FINISH (+ ABORTED)`

No throw/catapult detection (removes ~half the FW states).

### Resolved blockers

**B1 — Launch hard-gated to `STATE(AIRPLANE)`** at `navigation.c:4666,5558` and `fc_core.c:941`. Decision: reuse `NAV_LAUNCH_MODE` / `BOXNAVLAUNCH`, open the gates. FW regression testing mandatory.

**B2 — Abort is stick-based, unreachable without RC.** Decision: abort via `nav_mc_launch_abort_time` timeout or telemetry command (DISARM / `MAV_CMD_NAV_LAND`). On abort: disarm if on ground, land if airborne. Threshold: **50 cm AGL** (reuses landing detector constant). Bias toward land. After landing, `nav_disarm_on_landing` chains into disarm.

**B3 — FW activation requires GPS heading *invalid*.** Decision: MC gates on GPS fix + home set (the opposite — it needs valid GPS for the POSHOLD switch).

### Decided

- **`nav_mc_launch_thr` default:** independent of `nav_mc_hover_thr`. Only used for the short ramp before POSHOLD takes over; too dependent on frame/prop/weight to derive.
- **`MAV_CMD_NAV_TAKEOFF`:** yes, telemetry trigger for MC launch, PX4-style. Altitude param overrides `nav_mc_launch_altitude`. Replaces the `MAV_RESULT_UNSUPPORTED` stub on `mavlink_multiport3`.

VTOL included — takeoff is MC-profile, no difference.

---

## 4. Mode availability

Command mode → NAV modes only. This is definitional, not a separate rule.

- Firmware: non-NAV flight modes not selectable/activatable in Command mode
- Configurator: hides non-NAV modes in Command mode; warns if manual mode still configured

Keying resolved by control mode — `controlAllowsManualModes()` predicate, not a separate setting.

---

## 5. Implementation order

1. **Control-mode model (Pilot/Command)** — land the predicate inert, asserting it agrees with today's answers on an RC build. No behavior change.
2. **Migrate ~39 stick-read call sites** — batch by subsystem, RC/FW regression per batch. Each site either becomes unreachable in Command, or gets replaced by the vehicle-state question it actually meant.
3. **Telemetry failsafe + MC autolaunch** — both designs above. Telemetry failsafe becomes a source in the model rather than a bolt-on.
4. **Mode availability** — falls out as a model predicate.
5. **`MAV_CMD_NAV_TAKEOFF`** — after MC autolaunch exists to trigger.
