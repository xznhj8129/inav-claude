#!/usr/bin/env python3
"""
Round-trip correctness test for MSP_SET_RC_TUNING (204) / MSP_RC_TUNING (111)
and MSP2_INAV_SET_RATE_PROFILE (0x2008) / MSP2_INAV_RATE_PROFILE (0x2007).

Purpose: verify the refactored fixed-struct handlers in fc_msp.c
(mspSetRcTuning_t / mspSetRateProfile_t + sbufReadDataSafe) produce
bit-for-bit identical resulting profile state to the pre-refactor
hand-written field-by-field parsing.

This test:
  1. Sends a SET frame with distinct, easily-distinguishable values for
     every field (to catch any field-order transcription slip).
  2. Reads back the profile via the corresponding GET command and checks
     every field, accounting for the known clamp behavior:
       - roll/pitch rate clamped to [SETTING_CONSTANT_ROLL_PITCH_RATE_MIN,
         SETTING_CONSTANT_ROLL_PITCH_RATE_MAX]
       - yaw rate clamped to [SETTING_YAW_RATE_MIN, SETTING_YAW_RATE_MAX]
       - MSP_SET_RC_TUNING's dynPID is clamped via MIN(v, SETTING_TPA_RATE_MAX)
         (no lower bound)
       - MSP2_INAV_SET_RATE_PROFILE's throttleDynPID is NOT clamped at all
  3. Tests the two-length variant of MSP_SET_RC_TUNING: 10-byte frame must
     leave rcYawExpo8 unchanged; 11-byte frame must update it.
  4. Also sends out-of-range values to specifically verify clamp behavior
     (negative test / edge case, not just happy path).

Usage:
    python3 test_rc_tuning_rate_profile_roundtrip.py [host:port]
    (default host:port = localhost:5760)

Exit code 0 = all checks passed. Exit code 1 = any mismatch found.
"""
import sys
import struct

sys.path.insert(0, "/home/raymorris/Documents/planes/inavflight/mspapi2")

from mspapi2 import MSPApi
from mspapi2.lib import InavMSP

MSP_SET_RC_TUNING = int(InavMSP.MSP_SET_RC_TUNING)
MSP_RC_TUNING = int(InavMSP.MSP_RC_TUNING)
MSP2_INAV_SET_RATE_PROFILE = int(InavMSP.MSP2_INAV_SET_RATE_PROFILE)
MSP2_INAV_RATE_PROFILE = int(InavMSP.MSP2_INAV_RATE_PROFILE)

# Setting constants, grepped from build_sitl/src/main/target/SITL/SITL/settings_generated.h
ROLL_PITCH_RATE_MIN = 4
ROLL_PITCH_RATE_MAX = 180
YAW_RATE_MIN = 1
YAW_RATE_MAX = 180
TPA_RATE_MAX = 200

failures = []
passes = 0


def check(label, sent, got):
    global passes
    if sent == got:
        print(f"  OK   {label}: sent={sent} got={got}")
        passes += 1
    else:
        print(f"  FAIL {label}: sent={sent} got={got}  <-- MISMATCH")
        failures.append(f"{label}: sent={sent} got={got}")


def main():
    endpoint = sys.argv[1] if len(sys.argv) > 1 else "localhost:5760"
    print(f"Connecting to {endpoint} ...")
    print("Note: If running in sandbox, /dev/ttyACM*, /dev/ttyUSB*, and localhost")
    print("are allowlisted; if access is still blocked, ask the user rather than")
    print("disabling the sandbox.")

    try:
        api = MSPApi(tcp_endpoint=endpoint)
        api.open()
    except Exception as e:
        print(f"FAILED to connect: {e}")
        print("  Check: is SITL running and listening on this port?")
        return 1
    print("Connected.")

    # Sanity check: verify FC responds to a basic MSP query first.
    try:
        info, raw = api._request_raw(InavMSP.MSP_API_VERSION)
        if not raw:
            print("FC did not respond with API version payload. Aborting.")
            return 1
        print(f"FC responded to MSP_API_VERSION sanity check: {raw.hex()}")
    except Exception as e:
        print(f"FC not responding to sanity-check MSP command: {e}")
        print("  A previous test session may have left the FC in CLI mode.")
        return 1

    # ------------------------------------------------------------------
    # TEST 1: MSP_SET_RC_TUNING, 10-byte frame (base fields, in-range values)
    # ------------------------------------------------------------------
    print("\n=== TEST 1: MSP_SET_RC_TUNING (10-byte frame, in-range values) ===")
    sent = dict(
        rcRate8=100,           # unused/compat, any value
        stabilizedRcExpo8=55,
        rollRate=70,
        pitchRate=75,
        yawRate=60,
        dynPID=90,
        throttleRcMid8=40,
        throttleRcExpo8=20,
        throttlePaBreakpoint=1550,
    )
    payload = struct.pack(
        "<BBBBBBBBH",
        sent["rcRate8"],
        sent["stabilizedRcExpo8"],
        sent["rollRate"],
        sent["pitchRate"],
        sent["yawRate"],
        sent["dynPID"],
        sent["throttleRcMid8"],
        sent["throttleRcExpo8"],
        sent["throttlePaBreakpoint"],
    )
    assert len(payload) == 10, f"expected 10 bytes, got {len(payload)}"

    info, rsp = api._request_raw(MSP_SET_RC_TUNING, payload)
    print(f"  SET response code={info}")

    info, raw = api._request_raw(MSP_RC_TUNING)
    # MSP_RC_TUNING reply layout (11 bytes):
    # u8 rcRate8(unused=100), u8 stabRcExpo8, u8 roll, u8 pitch, u8 yaw,
    # u8 dynPID, u8 throttleMid, u8 throttleExpo, u16 paBreakpoint, u8 yawExpo8
    fields = struct.unpack("<BBBBBBBBHB", raw)
    (rcRate8, stabRcExpo8, roll, pitch, yaw, dynPID, thrMid, thrExpo, paBrk, yawExpo8_before) = fields
    print(f"  GET raw: {raw.hex()}")

    check("stabilizedRcExpo8", sent["stabilizedRcExpo8"], stabRcExpo8)
    check("rollRate", sent["rollRate"], roll)
    check("pitchRate", sent["pitchRate"], pitch)
    check("yawRate", sent["yawRate"], yaw)
    check("dynPID", sent["dynPID"], dynPID)  # in-range, no clamp expected
    check("throttleRcMid8", sent["throttleRcMid8"], thrMid)
    check("throttleRcExpo8", sent["throttleRcExpo8"], thrExpo)
    check("throttlePaBreakpoint", sent["throttlePaBreakpoint"], paBrk)

    # ------------------------------------------------------------------
    # TEST 2: MSP_SET_RC_TUNING, 10-byte frame -- rcYawExpo8 must be UNCHANGED
    # ------------------------------------------------------------------
    print("\n=== TEST 2: MSP_SET_RC_TUNING 10-byte frame leaves rcYawExpo8 unchanged ===")
    # First, explicitly set rcYawExpo8 to a known sentinel value via an
    # 11-byte frame, then send a 10-byte frame and confirm it's untouched.
    sentinel_yaw_expo = 77
    payload_11 = payload + struct.pack("<B", sentinel_yaw_expo)
    info, rsp = api._request_raw(MSP_SET_RC_TUNING, payload_11)
    info, raw = api._request_raw(MSP_RC_TUNING)
    fields = struct.unpack("<BBBBBBBBHB", raw)
    yaw_expo8_after_11 = fields[9]
    check("rcYawExpo8 after 11-byte SET (sentinel)", sentinel_yaw_expo, yaw_expo8_after_11)

    # Now send a 10-byte frame with DIFFERENT base values, rcYawExpo8 must stay at sentinel.
    sent2 = dict(
        rcRate8=100, stabilizedRcExpo8=33, rollRate=45, pitchRate=50,
        yawRate=20, dynPID=60, throttleRcMid8=15, throttleRcExpo8=10,
        throttlePaBreakpoint=1200,
    )
    payload_10 = struct.pack(
        "<BBBBBBBBH",
        sent2["rcRate8"], sent2["stabilizedRcExpo8"], sent2["rollRate"],
        sent2["pitchRate"], sent2["yawRate"], sent2["dynPID"],
        sent2["throttleRcMid8"], sent2["throttleRcExpo8"], sent2["throttlePaBreakpoint"],
    )
    info, rsp = api._request_raw(MSP_SET_RC_TUNING, payload_10)
    info, raw = api._request_raw(MSP_RC_TUNING)
    fields = struct.unpack("<BBBBBBBBHB", raw)
    (_, stabRcExpo8b, rollb, pitchb, yawb, dynb, thrMidb, thrExpob, paBrkb, yawExpo8_still) = fields
    check("stabilizedRcExpo8 (10-byte frame)", sent2["stabilizedRcExpo8"], stabRcExpo8b)
    check("rollRate (10-byte frame)", sent2["rollRate"], rollb)
    check("pitchRate (10-byte frame)", sent2["pitchRate"], pitchb)
    check("yawRate (10-byte frame)", sent2["yawRate"], yawb)
    check("dynPID (10-byte frame)", sent2["dynPID"], dynb)
    check("throttleRcMid8 (10-byte frame)", sent2["throttleRcMid8"], thrMidb)
    check("throttleRcExpo8 (10-byte frame)", sent2["throttleRcExpo8"], thrExpob)
    check("throttlePaBreakpoint (10-byte frame)", sent2["throttlePaBreakpoint"], paBrkb)
    check("rcYawExpo8 UNCHANGED after 10-byte frame", sentinel_yaw_expo, yawExpo8_still)

    # ------------------------------------------------------------------
    # TEST 3: MSP_SET_RC_TUNING, 11-byte frame -- rcYawExpo8 IS updated
    # ------------------------------------------------------------------
    print("\n=== TEST 3: MSP_SET_RC_TUNING 11-byte frame updates rcYawExpo8 ===")
    new_yaw_expo = 88
    payload_11b = payload_10 + struct.pack("<B", new_yaw_expo)
    info, rsp = api._request_raw(MSP_SET_RC_TUNING, payload_11b)
    info, raw = api._request_raw(MSP_RC_TUNING)
    fields = struct.unpack("<BBBBBBBBHB", raw)
    check("rcYawExpo8 after 11-byte frame (updated)", new_yaw_expo, fields[9])

    # ------------------------------------------------------------------
    # TEST 4: MSP_SET_RC_TUNING clamp behavior (out-of-range values)
    # ------------------------------------------------------------------
    print("\n=== TEST 4: MSP_SET_RC_TUNING clamp behavior (out-of-range) ===")
    oor = dict(
        rcRate8=100, stabilizedRcExpo8=44,
        rollRate=255,          # > MAX(180) -> clamp to 180
        pitchRate=1,           # < MIN(4) -> clamp to 4
        yawRate=255,           # > MAX(180) -> clamp to 180
        dynPID=250,            # > TPA_RATE_MAX(200) -> MIN clamp to 200
        throttleRcMid8=50, throttleRcExpo8=25, throttlePaBreakpoint=1400,
    )
    payload_oor = struct.pack(
        "<BBBBBBBBH",
        oor["rcRate8"], oor["stabilizedRcExpo8"], oor["rollRate"],
        oor["pitchRate"], oor["yawRate"], oor["dynPID"],
        oor["throttleRcMid8"], oor["throttleRcExpo8"], oor["throttlePaBreakpoint"],
    )
    info, rsp = api._request_raw(MSP_SET_RC_TUNING, payload_oor)
    info, raw = api._request_raw(MSP_RC_TUNING)
    fields = struct.unpack("<BBBBBBBBHB", raw)
    (_, _, rollc, pitchc, yawc, dync, _, _, _, _) = fields
    check("rollRate clamp (255 -> MAX)", ROLL_PITCH_RATE_MAX, rollc)
    check("pitchRate clamp (1 -> MIN)", ROLL_PITCH_RATE_MIN, pitchc)
    check("yawRate clamp (255 -> MAX)", YAW_RATE_MAX, yawc)
    check("dynPID clamp (250 -> TPA_RATE_MAX)", TPA_RATE_MAX, dync)

    # ------------------------------------------------------------------
    # TEST 5: MSP2_INAV_SET_RATE_PROFILE, 15-byte frame, in-range values
    # ------------------------------------------------------------------
    print("\n=== TEST 5: MSP2_INAV_SET_RATE_PROFILE (15-byte frame, in-range) ===")
    rp_sent = dict(
        throttleRcMid8=41,
        throttleRcExpo8=21,
        throttleDynPID=91,
        throttlePaBreakpoint=1560,
        stabilizedRcExpo8=56,
        stabilizedRcYawExpo8=34,
        stabilizedRollRate=71,
        stabilizedPitchRate=76,
        stabilizedYawRate=61,
        manualRcExpo8=22,
        manualRcYawExpo8=35,
        manualRollRate=72,
        manualPitchRate=77,
        manualYawRate=62,
    )
    rp_payload = struct.pack(
        "<BBBHBBBBBBBBBB",
        rp_sent["throttleRcMid8"],
        rp_sent["throttleRcExpo8"],
        rp_sent["throttleDynPID"],
        rp_sent["throttlePaBreakpoint"],
        rp_sent["stabilizedRcExpo8"],
        rp_sent["stabilizedRcYawExpo8"],
        rp_sent["stabilizedRollRate"],
        rp_sent["stabilizedPitchRate"],
        rp_sent["stabilizedYawRate"],
        rp_sent["manualRcExpo8"],
        rp_sent["manualRcYawExpo8"],
        rp_sent["manualRollRate"],
        rp_sent["manualPitchRate"],
        rp_sent["manualYawRate"],
    )
    assert len(rp_payload) == 15, f"expected 15 bytes, got {len(rp_payload)}"

    info, rsp = api._request_raw(MSP2_INAV_SET_RATE_PROFILE, rp_payload)
    print(f"  SET response code={info}")

    info, raw = api._request_raw(MSP2_INAV_RATE_PROFILE)
    print(f"  GET raw: {raw.hex()}")
    # MSP2_INAV_RATE_PROFILE reply layout (14 bytes):
    # u8 throttleMid, u8 throttleExpo, u8 throttleDynPID, u16 paBreakpoint,
    # u8 stabExpo, u8 stabYawExpo, u8 stabRoll, u8 stabPitch, u8 stabYaw,
    # u8 manExpo, u8 manYawExpo, u8 manRoll, u8 manPitch, u8 manYaw
    rp_fields = struct.unpack("<BBBHBBBBBBBBBB", raw)
    (thrMid, thrExpo, thrDyn, paBrk, stabExpo, stabYawExpo, stabRoll, stabPitch,
     stabYaw, manExpo, manYawExpo, manRoll, manPitch, manYaw) = rp_fields

    check("throttleRcMid8", rp_sent["throttleRcMid8"], thrMid)
    check("throttleRcExpo8", rp_sent["throttleRcExpo8"], thrExpo)
    check("throttleDynPID (unclamped)", rp_sent["throttleDynPID"], thrDyn)
    check("throttlePaBreakpoint", rp_sent["throttlePaBreakpoint"], paBrk)
    check("stabilizedRcExpo8", rp_sent["stabilizedRcExpo8"], stabExpo)
    check("stabilizedRcYawExpo8", rp_sent["stabilizedRcYawExpo8"], stabYawExpo)
    check("stabilizedRollRate", rp_sent["stabilizedRollRate"], stabRoll)
    check("stabilizedPitchRate", rp_sent["stabilizedPitchRate"], stabPitch)
    check("stabilizedYawRate", rp_sent["stabilizedYawRate"], stabYaw)
    check("manualRcExpo8", rp_sent["manualRcExpo8"], manExpo)
    check("manualRcYawExpo8", rp_sent["manualRcYawExpo8"], manYawExpo)
    check("manualRollRate", rp_sent["manualRollRate"], manRoll)
    check("manualPitchRate", rp_sent["manualPitchRate"], manPitch)
    check("manualYawRate", rp_sent["manualYawRate"], manYaw)

    # ------------------------------------------------------------------
    # TEST 6: MSP2_INAV_SET_RATE_PROFILE clamp behavior for rate fields,
    # and confirm throttleDynPID is NOT clamped (send out-of-normal-range
    # value that's still representable in a uint8, verify it passes through
    # unclamped -- since SETTING_TPA_RATE_MAX(200) doesn't apply here).
    # ------------------------------------------------------------------
    print("\n=== TEST 6: MSP2_INAV_SET_RATE_PROFILE clamp behavior ===")
    rp_oor = dict(
        throttleRcMid8=50, throttleRcExpo8=25,
        throttleDynPID=250,          # NOT clamped by TPA_RATE_MAX here -> expect 250 unchanged
        throttlePaBreakpoint=1400,
        stabilizedRcExpo8=44, stabilizedRcYawExpo8=44,
        stabilizedRollRate=255,      # > MAX -> clamp to 180
        stabilizedPitchRate=1,       # < MIN -> clamp to 4
        stabilizedYawRate=255,       # > MAX -> clamp to 180
        manualRcExpo8=44, manualRcYawExpo8=44,
        manualRollRate=1,            # < MIN -> clamp to 4
        manualPitchRate=255,         # > MAX -> clamp to 180
        manualYawRate=0,             # < MIN(1) -> clamp to 1
    )
    rp_payload_oor = struct.pack(
        "<BBBHBBBBBBBBBB",
        rp_oor["throttleRcMid8"], rp_oor["throttleRcExpo8"], rp_oor["throttleDynPID"],
        rp_oor["throttlePaBreakpoint"], rp_oor["stabilizedRcExpo8"], rp_oor["stabilizedRcYawExpo8"],
        rp_oor["stabilizedRollRate"], rp_oor["stabilizedPitchRate"], rp_oor["stabilizedYawRate"],
        rp_oor["manualRcExpo8"], rp_oor["manualRcYawExpo8"],
        rp_oor["manualRollRate"], rp_oor["manualPitchRate"], rp_oor["manualYawRate"],
    )
    info, rsp = api._request_raw(MSP2_INAV_SET_RATE_PROFILE, rp_payload_oor)
    info, raw = api._request_raw(MSP2_INAV_RATE_PROFILE)
    rp_fields = struct.unpack("<BBBHBBBBBBBBBB", raw)
    (thrMidc, thrExpoc, thrDync, paBrkc, stabExpoc, stabYawExpoc, stabRollc, stabPitchc,
     stabYawc, manExpoc, manYawExpoc, manRollc, manPitchc, manYawc) = rp_fields

    check("throttleDynPID NOT clamped (250 stays 250)", rp_oor["throttleDynPID"], thrDync)
    check("stabilizedRollRate clamp (255 -> MAX)", ROLL_PITCH_RATE_MAX, stabRollc)
    check("stabilizedPitchRate clamp (1 -> MIN)", ROLL_PITCH_RATE_MIN, stabPitchc)
    check("stabilizedYawRate clamp (255 -> MAX)", YAW_RATE_MAX, stabYawc)
    check("manualRollRate clamp (1 -> MIN)", ROLL_PITCH_RATE_MIN, manRollc)
    check("manualPitchRate clamp (255 -> MAX)", ROLL_PITCH_RATE_MAX, manPitchc)
    check("manualYawRate clamp (0 -> MIN)", YAW_RATE_MIN, manYawc)

    api.close()

    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"Total checks passed: {passes}")
    print(f"Total checks failed: {len(failures)}")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS - all fields round-tripped correctly (accounting for clamps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
