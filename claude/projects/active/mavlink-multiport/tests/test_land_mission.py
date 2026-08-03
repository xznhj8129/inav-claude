#!/usr/bin/env python3
"""LAND-terminated mission completion test (X-Plane HITL + SITL).

Verifies the navigation FSM fix: a mission ending in NAV_WP_ACTION_LAND must
fire MISSION_ITEM_REACHED for the LAND item and MISSION_CURRENT must report
MISSION_STATE_COMPLETE after touchdown.

Assumes:
  - SITL running with the mavlink_multiport2 eeprom (MAVLink telemetry on
    TCP 5762, MAVLink RC via RC_CHANNELS_OVERRIDE)
  - X-Plane 12 with INAV-X-Plane-HITL plugin connected, aircraft on runway
    (or positioned via slew mode)
  - Mode map from that eeprom: ARM=ch5 high, ANGLE=ch6 mid, NAV WP=ch8 high

Phases (run all, or select with --phase):
  upload   upload a 3-WP mission ending in LAND, relative to current position
  fly      arm, raise throttle, engage WP mode, stream RC
  monitor  watch MISSION_ITEM_REACHED / MISSION_CURRENT until COMPLETE or timeout
"""

import argparse
import sys
import threading
import time

from pymavlink import mavutil

RC_RATE_HZ = 5.0
CH = {  # 1-based channel -> default us
    1: 1500, 2: 1500, 3: 1000, 4: 1500,   # RPTY (AETR order per eeprom map)
    5: 1000,  # ARM
    6: 1500,  # ANGLE band 1300-1700
    7: 1000,
    8: 1000,  # NAV WP high 1700-2100
}


class Rig:
    def __init__(self, endpoint):
        self.conn = mavutil.mavlink_connection(
            endpoint, source_system=255,
            source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER)
        self.rc = dict(CH)
        self.rc_enabled = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._pump, daemon=True)

    def start(self):
        print("waiting for FC heartbeat...")
        if self.conn.wait_heartbeat(timeout=15) is None:
            sys.exit("FATAL: no FC heartbeat")
        print(f"FC: sys {self.conn.target_system}")
        self._thread.start()

    def _pump(self):
        next_hb = 0.0
        next_rc = 0.0
        while not self._stop.is_set():
            now = time.time()
            if now >= next_hb:
                self.conn.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_GCS,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
                next_hb = now + 1.0
            if self.rc_enabled and now >= next_rc:
                ch = [self.rc.get(i, 65535) for i in range(1, 19)]
                self.conn.mav.rc_channels_override_send(
                    self.conn.target_system, self.conn.target_component, *ch)
                next_rc = now + 1.0 / RC_RATE_HZ
            time.sleep(0.02)

    def stop(self):
        self._stop.set()

    def recv(self, mtype, timeout):
        return self.conn.recv_match(type=mtype, blocking=True, timeout=timeout)

    def wait_fix(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            m = self.recv("GPS_RAW_INT", 2)
            if m and m.fix_type >= 3 and m.satellites_visible >= 6:
                print(f"GPS fix: {m.fix_type}, sats {m.satellites_visible}")
                return True
        return False

    def position(self, timeout=10):
        m = self.recv("GLOBAL_POSITION_INT", timeout)
        if not m:
            sys.exit("FATAL: no GLOBAL_POSITION_INT")
        return m.lat, m.lon


def offset(lat, lon, north_m, east_m):
    dlat = int(north_m / 0.0111320)  # deg1e7 per metre approx
    dlon = int(east_m / (0.0111320 * max(0.2, abs(__import__('math').cos(lat / 1e7 * 3.14159 / 180)))))
    return lat + dlat, lon + dlon


def upload_mission(rig, alt_m):
    lat, lon = rig.position()
    print(f"home: {lat/1e7:.6f} {lon/1e7:.6f}")
    mav = rig.conn.mav
    common = dict(target_system=rig.conn.target_system,
                  target_component=rig.conn.target_component)

    # seq 0 = QGC-style planned home (skipped by INAV), then 3 real items.
    wp1 = offset(lat, lon, 400, 0)
    wp2 = offset(lat, lon, 400, 400)
    wp3 = offset(lat, lon, 0, 400)
    items = [
        (0, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, lat, lon, 0, 1),
        (1, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, *wp1, alt_m, 0),
        (2, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, *wp2, alt_m, 0),
        (3, mavutil.mavlink.MAV_CMD_NAV_LAND, *wp3, 0, 0),
    ]

    mav.mission_count_send(**common, count=len(items),
                           mission_type=mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
    for _ in range(len(items) * 3):
        req = rig.recv(["MISSION_REQUEST", "MISSION_REQUEST_INT", "MISSION_ACK"], 10)
        if req is None:
            sys.exit("FATAL: mission upload stalled")
        if req.get_type() == "MISSION_ACK":
            if req.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                print("mission upload ACCEPTED")
                return
            sys.exit(f"FATAL: mission upload NACK type={req.type}")
        seq, cmd, ilat, ilon, ialt, cur = items[req.seq]
        mav.mission_item_int_send(
            **common, seq=seq,
            frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            command=cmd, current=cur, autocontinue=1,
            param1=0, param2=0, param3=0, param4=0,
            x=ilat, y=ilon, z=ialt,
            mission_type=mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
    sys.exit("FATAL: mission upload did not complete")


def fly(rig, throttle):
    print("arming (ch5 high, throttle low)...")
    rig.rc_enabled = True
    time.sleep(2)
    rig.rc[5] = 1800
    time.sleep(3)
    hb = rig.recv("HEARTBEAT", 5)
    while hb and hb.get_srcComponent() != mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1:
        hb = rig.recv("HEARTBEAT", 5)
    armed = bool(hb and hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    print(f"armed: {armed}")
    if not armed:
        m = rig.recv("STATUSTEXT", 3)
        sys.exit(f"FATAL: did not arm ({m.text if m else 'no statustext'})")
    print(f"throttle up ({throttle}) + NAV WP (ch8 high)")
    rig.rc[3] = throttle
    time.sleep(1)
    rig.rc[8] = 1900


def monitor(rig, timeout):
    """Report every MISSION_ITEM_REACHED and MISSION_CURRENT transition."""
    start = time.time()
    reached = []
    last_state = None
    verdict = None
    while time.time() - start < timeout:
        m = rig.recv(["MISSION_ITEM_REACHED", "MISSION_CURRENT", "STATUSTEXT"], 2)
        if m is None:
            continue
        t = m.get_type()
        stamp = time.time() - start
        if t == "MISSION_ITEM_REACHED":
            reached.append(m.seq)
            print(f"[{stamp:6.1f}s] MISSION_ITEM_REACHED seq={m.seq}")
        elif t == "MISSION_CURRENT":
            state = getattr(m, "mission_state", None)
            if state != last_state:
                print(f"[{stamp:6.1f}s] MISSION_CURRENT seq={m.seq} state={state}")
                last_state = state
            if state == mavutil.mavlink.MISSION_STATE_COMPLETE:
                verdict = True
                break
        elif t == "STATUSTEXT" and "disabled" not in m.text.lower():
            print(f"[{stamp:6.1f}s] STATUSTEXT: {m.text}")

    print(f"\nreached items: {reached}")
    if verdict and 2 in reached:  # INAV seq for LAND item (0-based after home skip)
        print("PASS: LAND item reported reached and mission state COMPLETE")
        return 0
    print("FAIL: " + ("no MISSION_STATE_COMPLETE seen"
                      if not verdict else "LAND item never reported reached"))
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="tcp:127.0.0.1:5762")
    ap.add_argument("--alt", type=int, default=60)
    ap.add_argument("--throttle", type=int, default=1700)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--phase", choices=["upload", "fly", "monitor", "all"], default="all")
    args = ap.parse_args()

    rig = Rig(args.endpoint)
    rig.start()
    try:
        if args.phase in ("upload", "all"):
            if not rig.wait_fix():
                sys.exit("FATAL: no GPS fix - is X-Plane HITL connected?")
            upload_mission(rig, args.alt)
        if args.phase in ("fly", "all"):
            fly(rig, args.throttle)
        if args.phase in ("monitor", "all"):
            sys.exit(monitor(rig, args.timeout))
    finally:
        rig.stop()


if __name__ == "__main__":
    main()
