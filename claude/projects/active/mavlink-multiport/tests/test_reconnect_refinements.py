#!/usr/bin/env python3
"""Tests for the reconnect-detection refinements (mav/reconnect-refine).

Covers the per-peer (route table) heartbeat tracking and the per-port
arming-snapshot rate limit:
  1. slow-heartbeat peer (6.5 s period, above the 5 s gap threshold) gets
     rate-limited resends (<= 1 per 10 s), not one per beat
  2. a second peer joining the same port triggers its own snapshot even
     though the first peer's heartbeats never stopped

Run against SITL built from mav/reconnect-refine with the
mavlink_multiport2 eeprom (MAVLink telemetry on TCP 5762).
"""

import sys
import time

from pymavlink import mavutil

HOST = "127.0.0.1"
PORT = 5762
ARMING_PREFIX = "Arming disabled"

results = []


def report(name, ok, detail):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


def connect():
    conn = mavutil.mavlink_connection(
        f"tcp:{HOST}:{PORT}", source_system=255,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
        autoreconnect=False)
    if conn.wait_heartbeat(timeout=15) is None:
        sys.exit("FATAL: no FC heartbeat - is SITL running?")
    return conn


def send_heartbeat(conn, sysid=None):
    saved = conn.mav.srcSystem
    if sysid is not None:
        conn.mav.srcSystem = sysid
    conn.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
    conn.mav.srcSystem = saved


def drain_arming_texts(conn, duration_s):
    texts = []
    deadline = time.time() + duration_s
    while time.time() < deadline:
        msg = conn.recv_match(type="STATUSTEXT", blocking=True, timeout=0.2)
        if msg and msg.text.startswith(ARMING_PREFIX):
            texts.append((time.time(), msg.text))
    return texts


def main():
    # SITL flips HWFAIL into the arming flags ~5-10s after boot; that legit
    # flag-change broadcast would pollute the counts below. Let flags settle
    # before the first client connects (nothing is queued for TCP clients
    # that aren't connected yet).
    print("waiting for boot arming flags to settle...")
    time.sleep(12)

    # --- Test 1: slow-heartbeat peer is rate limited ---
    # Beats at t=0, 6.5, 13, 19.5, 26. Every beat after the first exceeds the
    # 5 s gap threshold and triggers reconnect handling, but the 10 s per-port
    # snapshot floor must cap actual sends at 3 (t~0, ~13, ~26). The old
    # per-port design would have sent 5.
    a = connect()
    texts = []
    start = time.time()
    beats = [0.0, 6.5, 13.0, 19.5, 26.0]
    for beat_at in beats:
        wait = start + beat_at - time.time()
        if wait > 0:
            texts += drain_arming_texts(a, wait)
        send_heartbeat(a)
    texts += drain_arming_texts(a, 2.0)
    n = len(texts)
    report("1. slow-heartbeat peer rate limited", 1 <= n <= 3,
           f"{n} arming texts over {len(beats)} slow beats (want 1..3, ideally 3)")
    a.close()

    # --- Test 2: second peer on the same port triggers its own snapshot ---
    # Peer A (sysid 255) heartbeats at 1 Hz. At t=12 (past the 10 s rate
    # floor from A's connect snapshot), peer B (sysid 77) sends its first
    # heartbeat on the same port. Per-peer tracking must classify B as a new
    # peer and resend, even though the port never went quiet.
    # Clear the 10s per-port snapshot floor left by test 1 before peer A
    # connects, or its baseline snapshot gets (correctly) suppressed.
    time.sleep(12)
    b = connect()
    send_heartbeat(b, sysid=254)  # peer A: fresh identity, first heartbeat
    baseline = len(drain_arming_texts(b, 3.0))

    start = time.time()
    b_joined_at = None
    post = []
    while time.time() - start < 16.0:
        send_heartbeat(b, sysid=254)  # peer A steady at ~1 Hz
        if b_joined_at is None and time.time() - start >= 12.0:
            send_heartbeat(b, sysid=77)  # peer B's first heartbeat
            b_joined_at = time.time()
        post += drain_arming_texts(b, 1.0)

    before_b = len([1 for ts, _ in post if b_joined_at is None or ts < b_joined_at - 0.1])
    after_b = len([1 for ts, _ in post if b_joined_at is not None and ts >= b_joined_at - 0.1])
    report("2. new peer on busy port gets snapshot",
           baseline >= 1 and before_b == 0 and after_b >= 1,
           f"baseline(A)={baseline} (want >=1), while A steady={before_b} (want 0), "
           f"after B joined={after_b} (want >=1)")
    b.close()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
