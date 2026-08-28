#!/usr/bin/env python3
"""
Verify the MSP2_SENSOR_* payload-size bounds-check fix in mspProcessSensorCommand().

BUG BEING VERIFIED
-------------------
`mspProcessSensorCommand()` in `src/main/fc/fc_msp.c` dispatches incoming
MSP2_SENSOR_* push messages (GPS, rangefinder, compass, baro, airspeed, opflow)
to receiver functions that cast the raw payload pointer straight to a
fixed-size packed struct and read every field, with NO check that the actual
payload was as large as the struct. Because MSP's own CRC8 only covers the
bytes actually sent, a short-but-CRC-valid frame passes CRC just fine, and the
receiver would then read PAST the end of the payload into whatever stale
bytes happened to still be sitting in the FC's ~192-byte MSP input buffer
from a PREVIOUS message - silently treating that garbage as real sensor data.

THE FIX
-------
Each receiver function (`mspGPSReceiveNewData`, `mspRangefinderReceiveNewData`,
etc.) now takes a `dataSize` parameter and does:

    if (dataSize != sizeof(expected_struct_t)) return;

before touching the payload at all. These are fire-and-forget push messages
(mspProcessSensorCommand always returns MSP_RESULT_NO_REPLY), so there is no
MSP reply to check - the only way to observe rejection is to look at whether
FC *state* changed.

TEST STRATEGY
-------------
For each sensor (GPS, rangefinder) we:
  1. Send a full, correctly-sized frame ("B") with known values.
  2. Send a full, correctly-sized frame ("B2") with DIFFERENT known values, so
     the FC's internal MSP receive buffer now has B2's bytes sitting in it.
  3. Send a deliberately SHORT frame ("C") that is a truncated prefix of a
     frame with yet ANOTHER set of values - crucially, the truncated bytes
     DO include the fields that are cheapest to observe (GPS fixType/numSat
     are within the first 10 bytes; rangefinder quality is the first byte).
  4. Confirm FC state is STILL B2's values, not C's values and not some
     mangled combination - i.e. the short frame was rejected in its
     entirety, not partially applied from the bytes that WERE sent.
     (If the bounds check were missing, the fields that live within the
     truncated prefix - fixType/numSat for GPS, quality for rangefinder -
     would correctly reflect C's new values, while the remaining fields
     would come from stale buffer contents. Total-rejection is therefore a
     strictly stronger, easily observable guarantee.)
  5. Send one more full, correctly-sized frame ("D") with values distinct
     from B2, and confirm the FC DOES update to D's values - proving the
     harness/FC can actually accept valid frames (rejection isn't just
     "nothing ever works").

GPS state is read back via MSP_RAW_GPS (gpsSol is updated unconditionally by
mspGPSReceiveNewData()->gpsProcessNewDriverData(), regardless of the
configured gps_provider, so no FC configuration/reboot is required for the
GPS half of this test).

Rangefinder state is only observable once `rangefinder_hardware` is set to
MSP (3) and rangefinderInit() has run - which only happens at boot, so this
script configures that via MSP_SET_SENSOR_CONFIG + MSP_EEPROM_WRITE +
MSP_REBOOT and reconnects before running the rangefinder half of the test.
Rangefinder value is read back via MSP_SONAR_ALTITUDE.

USAGE
-----
    python3 verify_sensor_command_bounds_check.py [--host HOST] [--port PORT]

Requires: mspapi2 (pip install -e mspapi2/), a running SITL build with the
fix applied, listening for MSP on the given TCP port (default
localhost:5760).

NOTE ON SANDBOX: if the connection times out immediately, this may be a
sandbox restriction - localhost is allowlisted for this kind of test; if
access is still blocked, ask the user rather than disabling the sandbox.
"""

import argparse
import struct
import sys
import time
from pathlib import Path

MSPAPI2_PATH = Path(__file__).resolve().parents[6] / "mspapi2"
sys.path.insert(0, str(MSPAPI2_PATH))

try:
    from mspapi2 import MSPApi
    from mspapi2.lib import InavMSP, InavEnums
except ImportError as e:
    print(f"FATAL: could not import mspapi2 from {MSPAPI2_PATH}: {e}")
    print("  Fix: cd mspapi2 && pip install -e .")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Struct layouts (must match src/main/msp/msp_protocol_v2_sensor_msg.h)
# ---------------------------------------------------------------------------

# mspSensorGpsDataMessage_t - 52 bytes packed
GPS_FMT = "<BHIBBHHHHiiiiiiHHHBBBBB"
GPS_FIELDS = (
    "instance", "gpsWeek", "msTOW", "fixType", "satellitesInView",
    "hPosAccuracy", "vPosAccuracy", "hVelAccuracy", "hdop",
    "longitude", "latitude", "mslAltitude",
    "nedVelNorth", "nedVelEast", "nedVelDown",
    "groundCourse", "trueYaw", "year", "month", "day", "hour", "minute", "sec",
)
GPS_STRUCT_SIZE = struct.calcsize(GPS_FMT)

# mspSensorRangefinderDataMessage_t - 5 bytes packed
RANGEFINDER_FMT = "<Bi"
RANGEFINDER_STRUCT_SIZE = struct.calcsize(RANGEFINDER_FMT)

# NOTE: the wire-level MSP fixType passed into MSP2_SENSOR_GPS (0=no fix, 2=2D, 3+=3D)
# is mapped by gpsMapFixType() to the FC-internal gpsFixType_e enum, which is what
# MSP_RAW_GPS reports back: GPS_NO_FIX=0, GPS_FIX_2D=1, GPS_FIX_3D=2. These are NOT
# the same numbering - compare readbacks against GPS_FIX_3D, not against the input "3".
GPS_FIX_3D = int(InavEnums.gpsFixType_e.GPS_FIX_3D)


def pack_gps(fixType, satellitesInView, lat_e7, lon_e7, alt_cm,
             instance=0, gpsWeek=0xFFFF, msTOW=0,
             hPosAccuracy=100, vPosAccuracy=100, hVelAccuracy=50, hdop=150,
             velN=0, velE=0, velD=0, groundCourse=0, trueYaw=65535,
             year=2026, month=1, day=1, hour=0, minute=0, sec=0):
    values = (
        instance, gpsWeek, msTOW, fixType, satellitesInView,
        hPosAccuracy, vPosAccuracy, hVelAccuracy, hdop,
        lon_e7, lat_e7, alt_cm,
        velN, velE, velD,
        groundCourse, trueYaw, year, month, day, hour, minute, sec,
    )
    packed = struct.pack(GPS_FMT, *values)
    assert len(packed) == GPS_STRUCT_SIZE == 52, f"GPS struct size mismatch: {len(packed)}"
    return packed


def pack_rangefinder(quality, distance_mm):
    packed = struct.pack(RANGEFINDER_FMT, quality, distance_mm)
    assert len(packed) == RANGEFINDER_STRUCT_SIZE == 5, f"Rangefinder struct size mismatch: {len(packed)}"
    return packed


class TestFailure(Exception):
    pass


def check(condition, ok_msg, fail_msg):
    if condition:
        print(f"  ✓ {ok_msg}")
        return True
    else:
        print(f"  ✗ {fail_msg}")
        return False


def connect(host, port, retries=1, retry_delay=1.0):
    """Connect and sanity-check the FC responds to MSP before trusting any test result."""
    last_exc = None
    for attempt in range(retries):
        try:
            api = MSPApi(tcp_endpoint=f"{host}:{port}")
            api.open()
            # Sanity check: FC must actually answer MSP, or nothing below is trustworthy.
            info, ident = api._request(InavMSP.MSP_API_VERSION)
            return api
        except Exception as e:
            last_exc = e
            try:
                api.close()
            except Exception:
                pass
            if attempt < retries - 1:
                time.sleep(retry_delay)
    print(f"FATAL: could not connect/verify MSP on {host}:{port}: {last_exc}")
    print("  Checks:")
    print("  - Is SITL running and listening on this port?")
    print("  - Note: if running in a sandbox, localhost/SITL ports should be")
    print("    allowlisted; if connection is still blocked, ask the user rather")
    print("    than disabling the sandbox.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# GPS test
# ---------------------------------------------------------------------------

def test_gps(api):
    print("\n" + "=" * 70)
    print("MSP2_SENSOR_GPS bounds-check test")
    print("=" * 70)
    failures = 0

    # Frame B: known-good baseline, distinct/identifiable values.
    frame_b = pack_gps(fixType=3, satellitesInView=22, lat_e7=377749000, lon_e7=-1224194000, alt_cm=10000)
    bytes_written = api._serial.send(int(InavMSP.MSP2_SENSOR_GPS), frame_b)
    if not check(bytes_written and bytes_written > 0,
                  f"Sent full GPS frame B ({len(frame_b)} bytes)",
                  f"Failed to send frame B (send() returned {bytes_written!r})"):
        failures += 1
    time.sleep(0.2)

    _, gps_after_b = api.get_raw_gps()
    print(f"  State after frame B: fixType={int(gps_after_b['fixType'])} numSat={gps_after_b['numSat']} "
          f"lat={gps_after_b['latitude']:.5f} lon={gps_after_b['longitude']:.5f}")
    if not check(int(gps_after_b["fixType"]) == GPS_FIX_3D and gps_after_b["numSat"] == 22,
                  "Baseline frame B was applied as expected",
                  f"Baseline frame B was NOT applied correctly: {gps_after_b}"):
        failures += 1

    # Frame B2: full, correctly-sized, DIFFERENT values. This is what should
    # remain in effect after the short frame C below is rejected, and it
    # also leaves B2's bytes sitting in the FC's MSP receive buffer.
    frame_b2 = pack_gps(fixType=3, satellitesInView=18, lat_e7=511000000, lon_e7=139000000, alt_cm=5000)
    api._serial.send(int(InavMSP.MSP2_SENSOR_GPS), frame_b2)
    time.sleep(0.2)
    _, gps_after_b2 = api.get_raw_gps()
    print(f"  State after frame B2: fixType={int(gps_after_b2['fixType'])} numSat={gps_after_b2['numSat']} "
          f"lat={gps_after_b2['latitude']:.5f} lon={gps_after_b2['longitude']:.5f}")
    if not check(int(gps_after_b2["fixType"]) == GPS_FIX_3D and gps_after_b2["numSat"] == 18,
                  "Frame B2 was applied as expected",
                  f"Frame B2 was NOT applied correctly: {gps_after_b2}"):
        failures += 1

    # Frame C: SHORT (10 bytes instead of 52), truncated prefix of a frame
    # with fixType=2 (2D fix) and numSat=5 - both DIFFERENT from B2, and
    # both fields live entirely within the first 10 bytes sent.
    frame_c_full = pack_gps(fixType=2, satellitesInView=5, lat_e7=1000000, lon_e7=2000000, alt_cm=1)
    frame_c_short = frame_c_full[:10]
    assert len(frame_c_short) == 10
    bytes_written = api._serial.send(int(InavMSP.MSP2_SENSOR_GPS), frame_c_short)
    if not check(bytes_written and bytes_written > 0,
                  f"Sent SHORT GPS frame C ({len(frame_c_short)} bytes, struct is {GPS_STRUCT_SIZE} bytes)",
                  f"Failed to send frame C (send() returned {bytes_written!r})"):
        failures += 1
    time.sleep(0.2)

    _, gps_after_c = api.get_raw_gps()
    print(f"  State after SHORT frame C: fixType={int(gps_after_c['fixType'])} numSat={gps_after_c['numSat']} "
          f"lat={gps_after_c['latitude']:.5f} lon={gps_after_c['longitude']:.5f}")
    short_frame_rejected = (
        int(gps_after_c["fixType"]) == int(gps_after_b2["fixType"]) == GPS_FIX_3D
        and gps_after_c["numSat"] == gps_after_b2["numSat"] == 18
        and abs(gps_after_c["latitude"] - gps_after_b2["latitude"]) < 1e-6
        and abs(gps_after_c["longitude"] - gps_after_b2["longitude"]) < 1e-6
    )
    if not check(short_frame_rejected,
                  "SHORT GPS frame was REJECTED - state unchanged from frame B2 "
                  "(fixType/numSat did NOT flip to frame C's values, even though "
                  "those fields were within the truncated bytes actually sent)",
                  f"SHORT GPS frame was NOT fully rejected - state changed! "
                  f"Expected fixType=3,numSat=18 (frame B2), got fixType={int(gps_after_c['fixType'])},"
                  f"numSat={gps_after_c['numSat']}. This means the bounds check is missing or broken."):
        failures += 1

    # Frame D: full, correctly-sized, distinct values -> must be accepted.
    frame_d = pack_gps(fixType=3, satellitesInView=9, lat_e7=-338700000, lon_e7=1512100000, alt_cm=25000)
    api._serial.send(int(InavMSP.MSP2_SENSOR_GPS), frame_d)
    time.sleep(0.2)
    _, gps_after_d = api.get_raw_gps()
    print(f"  State after full frame D: fixType={int(gps_after_d['fixType'])} numSat={gps_after_d['numSat']} "
          f"lat={gps_after_d['latitude']:.5f} lon={gps_after_d['longitude']:.5f}")
    if not check(int(gps_after_d["fixType"]) == GPS_FIX_3D and gps_after_d["numSat"] == 9
                  and abs(gps_after_d["latitude"] - (-33.87)) < 0.001,
                  "Full-size GPS frame D WAS applied - valid frames are still accepted",
                  f"Full-size GPS frame D was NOT applied: {gps_after_d}"):
        failures += 1

    return failures


# ---------------------------------------------------------------------------
# Rangefinder test
# ---------------------------------------------------------------------------

def configure_rangefinder_msp(api, host, port):
    """Set rangefinder_hardware=MSP, persist, reboot, and reconnect."""
    print("\nConfiguring rangefinder_hardware = MSP (requires reboot)...")
    info, cfg = api._request(InavMSP.MSP_SENSOR_CONFIG)
    print(f"  Current MSP_SENSOR_CONFIG: {cfg}")

    if cfg["rangefinderHardware"] == 3:
        print("  rangefinder_hardware already = MSP (3), skipping reconfigure/reboot")
        return api

    payload = api._pack_request(InavMSP.MSP_SET_SENSOR_CONFIG, {
        "accHardware": cfg["accHardware"],
        "baroHardware": cfg["baroHardware"],
        "magHardware": cfg["magHardware"],
        "pitotHardware": cfg["pitotHardware"],
        "rangefinderHardware": 3,  # RANGEFINDER_MSP
        "opflowHardware": cfg["opflowHardware"],
    })
    bytes_written = api._serial.send(int(InavMSP.MSP_SET_SENSOR_CONFIG), payload)
    if not bytes_written:
        print("FATAL: failed to send MSP_SET_SENSOR_CONFIG")
        sys.exit(1)
    time.sleep(0.2)

    api._serial.send(int(InavMSP.MSP_EEPROM_WRITE), b"")
    time.sleep(0.5)

    print("  Sending MSP_REBOOT...")
    api._serial.send(int(InavMSP.MSP_REBOOT), b"")
    time.sleep(0.5)
    try:
        api.close()
    except Exception:
        pass

    api = connect(host, port, retries=20, retry_delay=1.0)
    info, cfg2 = api._request(InavMSP.MSP_SENSOR_CONFIG)
    print(f"  MSP_SENSOR_CONFIG after reboot: {cfg2}")
    if cfg2["rangefinderHardware"] != 3:
        print("FATAL: rangefinder_hardware did not persist as MSP (3) across reboot; "
              "cannot run rangefinder half of the test.")
        sys.exit(1)

    _, status = api._request(InavMSP.MSP_STATUS)
    rangefinder_bit = (status["sensorStatus"] >> 4) & 1
    if not check(rangefinder_bit == 1,
                  "Rangefinder sensor reports detected (MSP_STATUS bit 4 set)",
                  "Rangefinder sensor NOT detected after reboot - cannot proceed"):
        sys.exit(1)

    return api


def get_sonar_altitude_cm(api):
    _, raw = api._request_raw(InavMSP.MSP_SONAR_ALTITUDE)
    (alt_cm,) = struct.unpack("<i", raw)
    return alt_cm


def test_rangefinder(api, host, port):
    print("\n" + "=" * 70)
    print("MSP2_SENSOR_RANGEFINDER bounds-check test")
    print("=" * 70)
    failures = 0

    api = configure_rangefinder_msp(api, host, port)

    # Rangefinder task runs every 30ms; give it margin.
    SETTLE = 0.3

    # Frame B2: full, correctly-sized, known distance -> this is the value
    # that must survive the short frame below.
    frame_b2 = pack_rangefinder(quality=200, distance_mm=3000)  # 300.0 cm
    bytes_written = api._serial.send(int(InavMSP.MSP2_SENSOR_RANGEFINDER), frame_b2)
    if not check(bytes_written and bytes_written > 0,
                  f"Sent full rangefinder frame B2 ({len(frame_b2)} bytes)",
                  f"Failed to send frame B2 (send() returned {bytes_written!r})"):
        failures += 1
    time.sleep(SETTLE)
    alt_after_b2 = get_sonar_altitude_cm(api)
    print(f"  Altitude after frame B2 (expect ~300cm): {alt_after_b2} cm")
    if not check(280 <= alt_after_b2 <= 320,
                  "Baseline frame B2 was applied as expected",
                  f"Baseline frame B2 was NOT applied correctly: got {alt_after_b2}cm, expected ~300cm"):
        failures += 1

    # Frame C: SHORT (2 bytes instead of 5) - truncated prefix of a very
    # different distance (12.34m), with quality (byte 0, fully included in
    # the 2 sent bytes) also different from B2.
    frame_c_full = pack_rangefinder(quality=77, distance_mm=12340)  # 1234.0 cm
    frame_c_short = frame_c_full[:2]
    assert len(frame_c_short) == 2
    bytes_written = api._serial.send(int(InavMSP.MSP2_SENSOR_RANGEFINDER), frame_c_short)
    if not check(bytes_written and bytes_written > 0,
                  f"Sent SHORT rangefinder frame C ({len(frame_c_short)} bytes, "
                  f"struct is {RANGEFINDER_STRUCT_SIZE} bytes)",
                  f"Failed to send frame C (send() returned {bytes_written!r})"):
        failures += 1
    time.sleep(SETTLE)
    alt_after_c = get_sonar_altitude_cm(api)
    print(f"  Altitude after SHORT frame C (expect still ~300cm, NOT ~1234cm): {alt_after_c} cm")
    if not check(280 <= alt_after_c <= 320,
                  "SHORT rangefinder frame was REJECTED - altitude unchanged from frame B2",
                  f"SHORT rangefinder frame was NOT rejected - altitude changed to {alt_after_c}cm "
                  f"(expected it to stay ~300cm). This means the bounds check is missing or broken."):
        failures += 1

    # Frame D: full, correctly-sized, distinct value -> must be accepted.
    frame_d = pack_rangefinder(quality=200, distance_mm=5670)  # 567.0 cm
    api._serial.send(int(InavMSP.MSP2_SENSOR_RANGEFINDER), frame_d)
    time.sleep(SETTLE)
    alt_after_d = get_sonar_altitude_cm(api)
    print(f"  Altitude after full frame D (expect ~567cm): {alt_after_d} cm")
    if not check(547 <= alt_after_d <= 587,
                  "Full-size rangefinder frame D WAS applied - valid frames are still accepted",
                  f"Full-size rangefinder frame D was NOT applied: got {alt_after_d}cm, expected ~567cm"):
        failures += 1

    return failures, api


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5760)
    args = parser.parse_args()

    print(f"Connecting to SITL at {args.host}:{args.port}...")
    api = connect(args.host, args.port)
    print("  ✓ Connected and FC responded to MSP_API_VERSION")

    total_failures = 0
    total_failures += test_gps(api)

    rf_failures, api = test_rangefinder(api, args.host, args.port)
    total_failures += rf_failures

    print("\n" + "=" * 70)
    if total_failures == 0:
        print("RESULT: PASS - all bounds-check behaviors verified")
    else:
        print(f"RESULT: FAIL - {total_failures} check(s) failed")
    print("=" * 70)

    try:
        api.close()
    except Exception:
        pass

    sys.exit(0 if total_failures == 0 else 1)


if __name__ == "__main__":
    main()
