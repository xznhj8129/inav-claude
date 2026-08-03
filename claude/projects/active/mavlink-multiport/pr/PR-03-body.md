**Part 3/7 of the mavlink_multiport2 stack.**

Replaces the monolithic `telemetry/mavlink.c` (~1.5k LOC) with focused modules under `src/main/mavlink/` — runtime, ports, streams, routing, modes, command, guided — plus `fc/fc_mavlink.c` for incoming-message dispatch. `telemetry/mavlink.c` stays as a thin telemetry-API adapter.

New behavior on top of the move:
- Up to 4 concurrent MAVLink ports (`MAX_MAVLINK_PORTS`), per-port runtime state, per-port `mavlink_port{1-4}_*` settings (stream rates, `min_txbuffer`, `radio_type`, `high_latency`). Port 1 streams fully by default; ports 2–4 start heartbeat-only.
- ArduPilot-style routing: routes learned as `(sysid, compid) → ingress port`, targeted traffic forwarded only on known routes, broadcasts fanned out, no repack. Fixed local identity `(mavlink_sysid, MAV_COMP_ID_AUTOPILOT1)`.
- Half-duplex TX backoff keyed to real per-port RX activity on shared `serialrx_halfduplex` MAVLink RX ports.
- mLRS radio link stats/information/flow-control handling per port.
- HIGH_LATENCY2 service (per-port setting + `MAV_CMD_CONTROL_HIGH_LATENCY`).
- RX parsing bounded per scheduler invocation; MAVLink moved behind the `MCU_FLASH_SIZE > 512` gate.

The incoming message/command surface otherwise matches upstream (DO_REPOSITION, DO_CHANGE_ALTITUDE, RC override, RADIO_STATUS, ADSB, param stub), now also accepted via COMMAND_LONG (upstream had that dispatch commented out).

**⚠ Mission protocol is intentionally absent at this stack point.** The old ad-hoc mission code is not carried over; a rewritten transfer state machine lands in part 5/7. Merge only as part of the stack.

## Testing
- Testing with Mavlink RXs (ELRS, MLRS) and QGC, Multiple ports work
- 19-test unit slice included (`mavlink_unittest`, 19/19). Also includes the live SITL multi-port benchmark/stress and sweep harnesses (`src/test/mavlink/ports/`) used to validate 1-4 concurrent port scenarios. Verified: full SITL build, warnings-as-errors, clean.
## Flash gating on 512 KB targets (deliberate)

Multi-port MAVLink does not fit alongside a full feature set on 512 KB flash boards, so this PR moves `USE_TELEMETRY_MAVLINK` / `USE_SERIALRX_MAVLINK` into the existing `#if (MCU_FLASH_SIZE > 512)` block in `target/common.h`. That gate excludes every 512 KB target — the deprecated F411 line **and** the current F722 line (~30 targets, e.g. AOCODARCF722AIO, BETAFPVF722, FOXEERF722V4, MAMBAF722_WING), which lose MAVLink telemetry/RX with no build error.

This is intentional, not incidental: even a lean config (MAMBAF722_WING) builds to **98.6% flash (484741 / 480 KB)** with these defines forced on — no headroom, and fuller F722 configs overflow. `MCU_FLASH_SIZE` cannot distinguish F411 from F722 (both 512 KB), so the gate necessarily catches both.

Follow-ups worth a separate discussion, out of scope here:
- a build-time opt-in (`USE_TELEMETRY_MAVLINK` on specific F722 targets that have flash to spare)
- shrinking the MAVLink footprint (dialect trimming, optional subsystems) to fit 512 KB

## PG version

`telemetryConfig_t`'s MAVLink section changes shape (single `mavlink` struct → `mavlink_common` + `mavlink[MAX_MAVLINK_PORTS]`), so `PG_TELEMETRY_CONFIG` is bumped 9 → 10; without it a firmware upgrade would load the old-layout EEPROM blob onto the new struct.
