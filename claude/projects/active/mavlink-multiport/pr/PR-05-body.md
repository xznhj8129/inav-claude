**Part 5/7 of the mavlink_multiport2 stack.**

Rewritten MAVLink mission protocol, replacing the old ad-hoc counter-based implementation (absent since part 3/7) with an owned transfer state machine. The transfer design is adapted from Betaflight's GPLv3 `mavlink_mission.c` (commit `87d4bd63`) and reshaped for INAV's routed multi-port runtime.

## Transfer robustness
- Transfers track the initiating system, component, and ingress port; only that partner may continue a transfer.
- Uploads retry the outstanding request every 1.5 s and abort after five retries. Downloads expire after 5 s of inactivity and accept one-item retransmission.
- Out-of-sequence upload items re-request the expected item; valid out-of-order download requests are served; explicit `MAV_MISSION_OPERATION_CANCELLED` returns the transfer to idle.
- Legacy `MISSION_REQUEST` downloads are answered with `MISSION_ITEM_INT`, per the current MAVLink mission service.
- Protocol-specific failure ACKs throughout.

## Translation (MAVLink ↔ INAV waypoints)
- Uploads are **staged**: the full MAVLink mission is received and translated into a temporary INAV waypoint list, validated, and committed only after the transfer succeeds — a failed upload never leaves a half-written mission.
- QGC planned-home item 0 is skipped (INAV stores home separately); MAVLink sequence 1 becomes INAV waypoint 1. A real current first waypoint is preserved, not mistaken for planned home.
- QGC-style NaN/unused waypoint params are tolerated.
- Modifier items fold onto the correct INAV waypoint instead of consuming slots: `DO_CHANGE_SPEED` → pending leg speed; `CONDITION_DELAY` → previous waypoint becomes/updates `POSHOLD_TIME`; altitude modifiers update the previous geographic waypoint while preserving INAV's `p3` bitfield semantics (bit 0 = AMSL reference, bits 1–4 = user actions).
- `NAV_WAYPOINT` → WAYPOINT or POSHOLD_TIME (hold time set), `NAV_LOITER_TIME` → POSHOLD_TIME, `NAV_LAND` → LAND (retaining supplied coordinates), `DO_JUMP` → JUMP with remapped target.

## Persistence and reporting
- Successful uploads and mission clears update nonvolatile waypoint storage; on persistence failure the previous mission is restored in RAM instead of leaving it cleared or half-written.
- 1 Hz `MISSION_CURRENT` (count, current item, execution mode, state); active-item flags on downloads.
- `MISSION_ITEM_REACHED` broadcast to all active MAVLink ports from a navigation-side reached latch (hold-time waypoints, altitude-enforced holds, and waypoint-next transitions).

## Caveats
Mission translation to INAV's MSP waypoint model is lossy (leg speed, LAND elevation, RTH land flag, `p3` user-action bits). MAVLink mission downloads are best-effort reconstruction from the stored MSP waypoint list — not a canonical mission backup. Documented in `docs/Mavlink.md` (part 7/7).

## Testing
- Unit slice: 58/58 passing (`mavlink_unittest`).
- Includes the live SITL mission rig (`src/test/mavlink/missions/`, 8 scenario cases incl. planned-home skip, modifier folding, JUMP remap, failed-upload preservation, legacy download) and the routing compliance harness (`src/test/mavlink/routing/`).
- Also includes the standalone SITL sanity harness (`src/test/mavlink/sanity/`): 8-check pass/fail rig covering MSP, MAVLink telemetry, RC override, GCS heartbeat, mission upload/readback, and stream/message-rate control.
- Full SITL build, warnings-as-errors, clean.
- X-Plane and QGC SITL testing successful; proprely made missions (without takeoff) load and fly accurately