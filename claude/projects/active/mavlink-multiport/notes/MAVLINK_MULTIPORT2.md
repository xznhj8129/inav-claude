This #11472 PR has been split into a sequence of PR's by inav-claude for easier review and handling, but i'll include a whole laydown of what it entails as final product here.

| # | PR | Branch | Contents | Tests |
|---|----|--------|----------|-------|
| 1 | #11712 | `mav/01-sitl-fixes` | SITL MAVLink-RX gate, SITL load accounting, X-Plane altitude inputs | — |
| 2 | #11713 | `mav/02-headers` | STorM32 dialect regen + `generate.sh` fix + include switch | — |
| 3 | #11714 | `mav/03-core` | modular split, multi-port runtime, routing, half-duplex, mLRS, HIGH_LATENCY2, port benchmark harness | 19/19 |
| 4 | #11715 | `mav/04-streams-protocol` | PING/TIMESYNC, stream/interval control, protocol replies, GPS accuracy, STATUSTEXT behaviors | 38/38 |
| 5 | #11716 | `mav/05-mission` | mission transfer state machine + translation + mission rig + routing harness + SITL sanity harness | 58/58 |
| 6 | #11717 | `mav/06-command-guided` | arm/RTH/LAND/home/mode commands, MSPv2 parity, PF ops, guided, loiter-radius override | 81/81 |
| 7 | #11718 | `mav/07-tunnel` | MSP-over-MAVLink tunnel + smoke test + user docs (`docs/Mavlink.md`, `Settings.md`) | 86/86 full |

Upstream PRs can't base on fork branches, so all 7 target `maintenance-10.x`; each body declares its own commit range with a fork compare link. As each part merges, the next one's diff auto-cleans.

## What this is

A ground-up rework of INAV's MAVLink implementation: from a single-port, single-file telemetry bolt-on into a modular MAVLink subsystem with:

- concurrent multi-port support
- ArduPilot-style routing
- a real mission protocol
- GCS command parity
- protocol services
- native mLRS integration
- high-latency mode
- MSP-over-MAVLink tunneling so the Configurator can ride an existing telemetry radio

Routing design follows ArduPilot's `MAVLink_routing.cpp`. The mission transfer state machine is adapted from Betaflight's GPLv3 `mavlink_mission.c` (`87d4bd63`) and reshaped for the routed multi-port runtime.

Developed on `inav:mavlink_multiport2`, shipped upstream as a 7-part stacked PR series rebuilt on current `maintenance-10.x`.

## Architecture

The monolithic `src/main/telemetry/mavlink.c` (~1.5k LOC) became modules under `src/main/mavlink/`, with `telemetry/mavlink.c` reduced to a thin telemetry-API adapter:

| Module | Owns |
|--------|------|
| `mavlink_runtime.c` | shared context, active-port switching, RX loop, TX fan-out, half-duplex backoff |
| `mavlink_ports.c` | port lifecycle (configure/free), per-port state reset |
| `mavlink_streams.c` | stream scheduling, per-message intervals, all periodic senders, STATUSTEXT |
| `mavlink_routing.c` | route learning `(sysid, compid) → ingress port`, forwarding decisions |
| `mavlink_mission.c` | mission transfer state machine + MAVLink↔INAV translation |
| `mavlink_modes.c` | ArduPlane/ArduCopter custom_mode maps (+ optional Standard Modes) |
| `mavlink_command.c` | `MAV_CMD_*` handling |
| `mavlink_guided.c` | SET_POSITION_TARGET / frame helpers / altitude targets |
| `fc/fc_mavlink.c` | incoming-message dispatch, mLRS handlers, MSP tunnel |
| `mavlink_internal.h` / `mavlink_types.h` | shared private context / shared types |

Headers: built against the checked-in **STorM32 dialect** (337-message STorM32/ArduPilot/common superset) because it carries OlliW's mLRS-specific messages. The regen moved the merged `MAV_CMD` enum into `storm32/storm32.h`; the first include (`rx/mavlink.h`) points there, and the old local APM mode-enum copies were dropped for the generated `PLANE_MODE`/`COPTER_MODE`.

## Feature laydown

### Multi-port

- Up to 4 concurrent MAVLink ports (`MAX_MAVLINK_PORTS`) with per-port runtime state.
- Per-port settings: `mavlink_port{1-4}_{ext_status,rc_chan,pos,extra1,extra2,extra3}_rate`, `_min_txbuffer`, `_radio_type` (GENERIC/ELRS/SIK/MLRS), `_high_latency`.
- Common settings: `mavlink_sysid`, `mavlink_autopilot_type` (GENERIC/ARDUPILOT), `mavlink_version`.
- Port 1 streams fully by default; ports 2–4 boot heartbeat-only until a GCS requests streams.
- Flow control uses `RADIO_STATUS.txbuf` (or mLRS flow control) against `min_txbuffer`; without flow-control input the port falls back to blind 20 ms frame pacing.
- Fixed local identity `(mavlink_sysid, MAV_COMP_ID_AUTOPILOT1)` — no per-port FC compids; attached devices are learned as remote components.
- RX parsing bounded per scheduler invocation; periodic deadlines phased against startup bursts.
- MAVLink is gated behind `MCU_FLASH_SIZE > 512`: multi-port MAVLink doesn't fit on 512 KB boards (MAMBAF722_WING builds to 98.6% flash with it forced on), so all 512 KB targets — F411 **and** the ~30 current F722 boards — lose MAVLink. `telemetryConfig_t` PG version bumped 9 → 10 for the reshaped struct.

### Routing

- Routes learned from incoming traffic as `(sysid, compid) → ingress port`.
- Targeted messages forwarded only on known routes; broadcasts fanned to other ports without repack.
- `RADIO_STATUS` and mLRS flow control stay local to their ingress port.
- Local/system broadcasts execute locally for control-class messages.
- Same-sysid different-compid traffic is a remote component, not dropped as self.
- Caveat: first targeted frame to a never-seen endpoint won't forward until that endpoint has transmitted once.

### Streams & protocol services

- Legacy `REQUEST_DATA_STREAM` group control plus per-message `SET_MESSAGE_INTERVAL`/`GET_MESSAGE_INTERVAL` overrides layered on top.
- `MAV_CMD_REQUEST_MESSAGE` (incl. `MESSAGE_INTERVAL` query).
- `REQUEST_PROTOCOL_VERSION` and `REQUEST_AUTOPILOT_CAPABILITIES` (advertises ArduPilot-compatible 4.7.0 + MAVLink2 / mission / command-int / set-position-target capabilities).
- `GET_HOME_POSITION`.
- Protocol-correct `PING` and `TIMESYNC` (monotonic ns boot clock).
- `SYSTEM_TIME` with RTC Unix time when valid.

### Telemetry detail

- `EXTENDED_SYS_STATE` landed-state reporting.
- UBlox ellipsoid altitude and speed/heading accuracy retained and emitted in `GPS_RAW_INT`.
- Changed arming-disable reasons broadcast as `STATUSTEXT` once a port is active.
- INAV flight-mode transitions broadcast as `Notice: INAV: Entering <mode>` with explicit GCS NAV enter/exit.
- OSD-derived `STATUSTEXT` de-spammed per port (changed text immediate; unchanged notice 30 s / warning 10 s / critical 5 s) instead of every EXTRA3 tick.

### Missions

- Owned transfer state machine: partner + ingress-port bound, upload retries (1.5 s × 5), download timeout (5 s), one-item retransmission, out-of-sequence recovery, explicit cancel.
- Legacy `MISSION_REQUEST` answered with `MISSION_ITEM_INT`.
- Uploads are **staged** — translate whole mission → temp list → validate → commit — so failures never half-write.
- Uploads accept up to `NAV_MAX_WAYPOINTS * 4 + 1` MAVLink items; QGC planned-home item 0 skipped; NaN/unused params tolerated.
- Modifier items (`DO_CHANGE_SPEED`, `CONDITION_DELAY`, altitude changes) fold onto the correct waypoint preserving `p3` bitfield semantics.
- Persistence-failure restores the previous mission.
- 1 Hz `MISSION_CURRENT`; `MISSION_ITEM_REACHED` broadcast from a navigation-side latch.
- **Caveat:** translation is lossy (leg speed, LAND elevation, RTH land flag, p3 user bits); downloads are best-effort reconstruction, not canonical backups.

### Command parity (MAVLink + MSPv2 + Programming Framework)

- Arm/disarm: `MAV_CMD_COMPONENT_ARM_DISARM` / `MSP2_INAV_ARM_DISARM` (0x2227) through the normal arming path; ACK success only when the state is reached.
- RTH: `NAV_RETURN_TO_LAUNCH`, ArduPilot `DO_SET_MODE` RTL, `MSP2_INAV_ACTIVATE_RTH` (0x2225), PF op 61 → `activateRTHMode()` (temporary `BOXNAVRTH` RC-mode source, **not** the failsafe/geozone forced-RTH latch); cleared by pilot mode change or disarm.
- Pause: `DO_SET_MODE` Loiter/PosHold/Brake → normal PosHold at current position via temporary `BOXNAVPOSHOLD` (what QGC Pause sends).
- Land: `NAV_LAND` / `MSP2_INAV_ACTIVATE_LANDING` (0x2224) / PF op 62 → normal waypoint-style landing at current position via transient waypoint; mission untouched; not emergency landing.
- Home: `DO_SET_HOME` through the native waypoint-0 backend with all its gates.
- Time: `MSP2_INAV_TIMESYNC` (0x2228) = same ns boot clock as MAVLink TIMESYNC.
- Guided: `DO_REPOSITION` (waypoint 255), `SET_POSITION_TARGET_GLOBAL_INT/_LOCAL_NED` (position or altitude-only), `DO_CHANGE_ALTITUDE`, `CONDITION_YAW` (the latter two originating from the earlier `mav_fix2` work) — all gated on valid GCS navigation and hardened against non-finite/out-of-range params.
- Loiter radius: temporary fixed-wing PosHold override via `DO_REPOSITION.param3` (m) or appended int32 cm on `MSP2_INAV_SET_GLOBAL_TARGET`; reported in `MSP2_INAV_NAV_TARGET`; volatile, PosHold-only, cleared on disarm/reboot.
- `NAV_TAKEOFF`: explicit `UNSUPPORTED` stub.
- OSD shows `GCSN` while GCS nav is active.

### mLRS integration

- With `radio_type = MLRS`: native `MLRS_RADIO_LINK_STATS` / `_INFORMATION` / `_FLOW_CONTROL` from `MAV_COMP_ID_TELEMETRY_RADIO`, stored per ingress port.
- Only the MAVLink-serial-RX port updates global `rxLinkStatistics`; flow control stays port-local.
- `RADIO_STATUS` remains the GENERIC/ELRS/SIK path.

### High latency

- Per-port `HIGH_LATENCY2` (setting or `MAV_CMD_CONTROL_HIGH_LATENCY`), MAVLink2-only.
- Replaces normal streams with one summary every 5 s for satellite/cellular/LoRa-class links.

### MSP-over-MAVLink tunnel

- `TUNNEL` payload type `0x8001`, MAVLink2-only.
- MSP parser/encoder reused via three narrow `msp_serial` seams.
- Replies fragmented on the ingress port only; MSPv1↔v1 / v2↔v2 framing preserved.
- `MSP_REBOOT` supported with post-process; serial/ESC-4way passthrough rejected pre-dispatch.
- Malformed lengths dropped, stale partials time out; file-scope buffers (no task-stack overflow).
- Not a generic serial tunnel; no CLI.
- Configurator side: "MAVLink Tunnel" under Wireless mode with SYSID selection (0 = first heartbeat), source identity `253/25`, tunnel off by default per session, CLI tab hidden; inbound truncated MAVLink2 payload tails are zero-padded back to `payload_length` before MSP parsing.
- Tested over ELRS-MAVLink and mLRS.

### SITL/simulator fixes

- SITL now defines `USE_TELEMETRY_MAVLINK`/`USE_SERIALRX_MAVLINK` explicitly. Upstream `common.h` defines them unconditionally today; part 3 moves them behind `MCU_FLASH_SIZE > 512`, which SITL never satisfies (it sets `TARGET_FLASH_SIZE`, and `common.h` is included first) — without the explicit defines `serialrx_provider = MAVLINK` would silently reset to NONE.
- SITL load accounting uses busy-time-over-wall-time excluding the host sleep (kills false `SYSTEM OVERLOADED` arming blocks).
- X-Plane feeds GPS NED velocity from local velocity and fake baro from aircraft elevation (fixes fixed-wing loiter sink).

## Design decisions worth remembering

- **RTH backend**: command RTH ≠ forced RTH. `activateForcedRTH()` sets the failsafe/geozone latch and is not equivalent to switching modes — proven in live testing. Commands use the temporary RC-mode-source mechanism instead.
- **One local identity**: transport ≠ component. The FC is always `AUTOPILOT1`; routing learns everything else. Per-port compid settings were removed.
- **Mode reporting**: ArduPilot heartbeat `custom_mode` is the compatibility path; MAVLink Standard Modes is compile-gated (`USE_MAVLINK_STANDARD_MODES`) and off — advertising GUIDED as a standard mode confused QGC.
- **Half-duplex**: keyed to `serialrx_halfduplex` on the shared RX port, not `telemetry_halfduplex` (using the latter caused a benchmark regression).
- **STorM32 dialect**: chosen for the mLRS messages; superset of ardupilotmega+common.
- **Stack base**: rebuilt on current `maintenance-10.x`, so the feared upstream re-merge is already done, in reviewable pieces.

## Verification

- `mavlink_unittest`: 86/86 at the tip; per-part slices 19/38/58/81 all green.
- Full SITL builds warnings-as-errors clean at **every** stack point (incl. the headers-only intermediate).
- Live (on the dev branch):
  - routing compliance 11/11
  - mission rig 8/8
  - SITL sanity rig 8/8 checks
  - MSP tunnel end-to-end incl. reboot+reconnect
  - companion `mspapi2` command helper tests 4/4
  - X-Plane + QGC flights — missions load and fly, pause/RTH/land behave
- In-tree harnesses: `src/test/mavlink/{routing,missions,ports,sanity,tunnel}/`.
- Benchmark baselines (short run, 1/2/3/4 ports): MSP failure rates ~2.7% / 4.0% / 0.7% / 1.3%.

## Known limits / non-goals

- Not a full ArduPilot/PX4-class MAVLink stack.
- Parameter API is a deliberate stub — configure via Configurator/CLI.
- Mission support is intentionally partial vs INAV's MSP model.
- Ports 2–4 don't stream by default.
- Directed forwarding needs route learning.
- No CLI over the tunnel.
- `NAV_TAKEOFF` recognized but unsupported.
- Open questions from the original draft still stand:
  - is 4 ports the right cap?
  - final flash/RAM cost across representative targets?
  - should the tunnel payload type be registered formally with MAVLink?
