#!/usr/bin/env python3
"""Verify per-port arming-reason STATUSTEXT on MAVLink (re)connect.

Exercises the mavlinkPortReconnected() logic against a live SITL:
  1. fresh connect + first HEARTBEAT  -> arming text arrives
  2. steady heartbeats                -> no duplicate resend
  3. reconnect within gap threshold   -> no resend (gap < 5 s)
  4. reconnect after gap threshold    -> resend (gap >= 5 s)
  5. fresh connect on second port     -> its own copy, independent state

SITL must be running with the mavlink_multiport2 eeprom (MAVLink telemetry
on serial ids 2 and 3 -> TCP 5762 / 5763).
"""

import sys
import time

from pymavlink import mavutil

HOST = "127.0.0.1"
PORT_A = 5762  # port index 0
PORT_B = 5763  # port index 1
GAP_THRESHOLD_S = 5.0
ARMING_PREFIX = "Arming disabled"

results = []


def report(name, ok, detail):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


def connect(tcp_port):
    conn = mavutil.mavlink_connection(
        f"tcp:{HOST}:{tcp_port}",
        source_system=255,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
        autoreconnect=False,
    )
    return conn


def gcs_heartbeat(conn):
    conn.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0, 0, 0,
    )


def collect_arming_texts(conn, duration_s, heartbeat_period_s=1.0):
    """Pump heartbeats and collect arming-disabled STATUSTEXTs for duration."""
    texts = []
    deadline = time.time() + duration_s
    next_hb = 0.0
    while time.time() < deadline:
        now = time.time()
        if now >= next_hb:
            gcs_heartbeat(conn)
            next_hb = now + heartbeat_period_s
        msg = conn.recv_match(type="STATUSTEXT", blocking=True, timeout=0.2)
        if msg and msg.text.startswith(ARMING_PREFIX):
            texts.append(msg.text)
    return texts


def listen_arming_texts(conn, duration_s):
    """Collect arming-disabled STATUSTEXTs WITHOUT sending heartbeats."""
    texts = []
    deadline = time.time() + duration_s
    while time.time() < deadline:
        msg = conn.recv_match(type="STATUSTEXT", blocking=True, timeout=0.2)
        if msg and msg.text.startswith(ARMING_PREFIX):
            texts.append(msg.text)
    return texts


def main():
    # --- Phase 1: fresh connect, first heartbeat triggers snapshot ---
    a = connect(PORT_A)
    fc_hb = a.wait_heartbeat(timeout=10)
    if fc_hb is None:
        print("FATAL: no FC heartbeat on port A - is SITL running?")
        sys.exit(2)

    # Quiet listen first: no GCS heartbeat yet, so nothing should trigger
    # (boot-time snapshot went into the void before we connected).
    pre = listen_arming_texts(a, 2.0)
    report("1a. no arming text before first GCS heartbeat", len(pre) == 0,
           f"got {len(pre)} texts: {pre[:2]}")

    texts = collect_arming_texts(a, 4.0)
    report("1b. arming text on first GCS heartbeat", len(texts) >= 1,
           f"got {len(texts)}: {texts[:2]}")
    last_text = texts[-1] if texts else None

    # --- Phase 2: steady heartbeats, no duplicate ---
    # The arming flags can legitimately change early after boot (e.g. HWFAIL
    # appearing when sensor init times out); the global edge detector then
    # correctly broadcasts the NEW text. Only an identical repeat of the
    # last-seen text would indicate a spurious per-port resend.
    texts = collect_arming_texts(a, 4.0)
    dupes = [t for t in texts if t == last_text]
    changed = [t for t in texts if t != last_text]
    if changed:
        print(f"  (note: flag-change broadcast during phase 2: {changed})")
        last_text = changed[-1]
    report("2. no identical resend while steadily connected", len(dupes) == 0,
           f"got {len(dupes)} duplicates of {last_text!r}")

    # --- Phase 3: quick reconnect (gap < threshold) ---
    a.close()
    time.sleep(1.5)
    a = connect(PORT_A)
    a.wait_heartbeat(timeout=10)
    texts = collect_arming_texts(a, 3.0)
    dupes = [t for t in texts if t == last_text]
    changed = [t for t in texts if t != last_text]
    if changed:
        print(f"  (note: flag-change broadcast during phase 3: {changed})")
        last_text = changed[-1]
    report("3. no resend on quick reconnect (<5s gap)", len(dupes) == 0,
           f"got {len(dupes)} duplicates")

    # --- Phase 4: reconnect after gap ---
    a.close()
    time.sleep(GAP_THRESHOLD_S + 2.0)
    a = connect(PORT_A)
    a.wait_heartbeat(timeout=10)
    texts = collect_arming_texts(a, 4.0)
    report("4. resend on reconnect after >5s gap", len(texts) >= 1,
           f"got {len(texts)}: {texts[:2]}")
    a.close()

    # --- Phase 5: second port gets its own copy independently ---
    b = connect(PORT_B)
    b.wait_heartbeat(timeout=10)
    texts = collect_arming_texts(b, 4.0)
    report("5. second port gets its own snapshot", len(texts) >= 1,
           f"got {len(texts)}: {texts[:2]}")
    b.close()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
