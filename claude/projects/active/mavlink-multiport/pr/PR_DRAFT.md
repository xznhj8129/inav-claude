# MAVLink multi-port refactor, routing, protocol services, command parity, and MSP-over-MAVLink tunnel

> **SUPERSEDED (2026-07-17):** this single-PR draft was replaced by a 7-part stacked PR series on iNavFlight/inav: #11712 (SITL fixes) #11713 (storm32 headers) #11714 (multiport core) #11715 (streams/protocol) #11716 (missions) #11717 (command parity) #11718 (MSP tunnel). Kept as the whole-branch overview. Note: the X-Plane motor-output-with-XITL and pitch/yaw-sign fixes were dropped from the stack (suspected chanmap band-aids).
**Draft WIP:** The user setup workflow and settings still need review. Configurator support remains a separate PR, and hardware/flight testing is still required.

Routing, tunnel, telemetry, and performance test tooling is present in the branch workspace.

## Summary

Substantial refactor of INAV's MAVLink implementation. The main goal is to turn the existing single-block MAVLink telemetry code into a modular MAVLink subsystem that can support multiple concurrent MAVLink ports, more correct routing and message handling, and a broader set of MAVLink interactions needed by modern GCS and radio workflows. This enables you to use multiple Mavlink ports for receivers, GCS links, computers, gimbals, cameras and more as you would expect from a Mavlink vehicle. The routing is based on Ardupilot.

The old `src/main/telemetry/mavlink.c` file was split by responsibility instead of continuing to accumulate all MAVLink behavior in one place. Runtime state and active-port context moved into `src/main/mavlink/mavlink_runtime.c`; port lifecycle into `src/main/mavlink/mavlink_ports.c`; stream scheduling and periodic message emission into `src/main/mavlink/mavlink_streams.c`; route learning and forwarding into `src/main/mavlink/mavlink_routing.c`; mission upload/download and frame handling into `src/main/mavlink/mavlink_mission.c`; mode mapping into `src/main/mavlink/mavlink_modes.c`; MAV_CMD handling into `src/main/mavlink/mavlink_command.c`; guided/SET_POSITION_TARGET handling into `src/main/mavlink/mavlink_guided.c`; and FC-facing incoming-message dispatch plus MSP-over-MAVLink tunnel handling into `src/main/fc/fc_mavlink.c`. Shared types and internal interfaces were moved under `src/main/mavlink/`, leaving the telemetry entry layer much thinner and making further MAVLink work more tractable.

On top of that refactor, this branch adds MSP-over-MAVLink [Tunnel Service](https://mavlink.io/en/services/tunnel.html) support so the INAV Configurator can talk MSP over an existing MAVLink telemetry link, typically over a radio that does not expose a separate MSP transport. The configurator patch adds a "Mavlink Tunnel" option when Wireless Mode is selected and allows specification of SYSID for multi-vehicle networks. 

See docs/Mavlink.md

## Progress since the original draft

The branch was merged with the then-current `maintenance-10.x` line on June 8 and now carries two additional MAVLink improvement passes.

### Maintenance-10.x integration

- Integrated the June 8 maintenance base while retaining the split multi-port MAVLink runtime and routing design.
- Preserved upstream GPS hardware-version handling, CRSF legacy barometer configuration, RTC-backed MAVLink Unix time, and the `USE_BARO || USE_GPS` altitude-target guard.
- Adopted the current MSP documentation generation/versioning layout and regenerated the derived MSP and enum references.
- Merged the companion Configurator branch with its current maintenance line while preserving tunnel startup/reconnect behavior. MAVLink tunnel mode now defaults off and must be enabled explicitly for each session.

### Protocol reliability and interoperability

- Reworked mission upload/download into an owned transfer state machine that tracks the initiating system, component, and ingress port.
- Added upload retries and timeout handling, one-item download retransmission, final `MISSION_ACK` handling, transaction-partner validation, and protocol-specific failure ACKs.
- Successful uploads and mission clears now update nonvolatile waypoint storage.
- Mission upload now skips QGC planned-home item 0, stages the translated INAV waypoint list before committing it, and applies QGC/MAVLink modifier items such as delay, altitude, and speed changes to the appropriate translated INAV waypoint instead of blindly consuming waypoint slots.
- Added 1 Hz `MISSION_CURRENT`, active-item flags on downloaded mission items, and mission-completion tracking from `MISSION_ITEM_REACHED`.
- Added protocol-correct `PING` and `TIMESYNC` replies.
- Expanded `MAV_CMD_REQUEST_MESSAGE` with `MESSAGE_INTERVAL`; the MAVLink Standard Modes responses (`AVAILABLE_MODES`, `AVAILABLE_MODES_MONITOR`, `CURRENT_MODE`) are now build-time optional behind `USE_MAVLINK_STANDARD_MODES` and off by default for ArduPilot-style mode emulation.
- Hardened command and guided coordinate conversion against non-finite/out-of-range values.
- Bounded MAVLink RX work per scheduler invocation and phased initial message deadlines to reduce monopolization and startup bursts.
- Retained UBlox ellipsoid altitude and accuracy data for `GPS_RAW_INT`.
- Added changed arming-disable reasons as deferred `STATUSTEXT`.
- Added `STATUSTEXT` notices for INAV flight-mode transitions (`Notice: INAV: Entering <mode>`) including explicit GCS NAV mode enter/exit notices.
- Fixed `lib/main/MAVLink/generate.sh`/`generate.bat` to generate the STorM32 dialect INAV actually includes and regenerated the headers (337-message STorM32/ArduPilot/common set; merged `MAV_CMD` enum now lives in `storm32/storm32.h`).
- Added per-port suppression for unchanged OSD-derived `STATUSTEXT`, so persistent OSD states such as loiter/RTH messages remain visible in GCS vehicle messages without repeating at the EXTRA3 stream rate.
- Added `GCSN` to the OSD flight-mode element when GCS-assisted navigation is actually active.
- Corrected X-Plane SITL altitude sensor inputs: GPS NED velocity now comes from X-Plane local velocity and fake barometer pressure comes from aircraft elevation, matching the RealFlight SITL pattern.

### Command parity

- Added `MAV_CMD_COMPONENT_ARM_DISARM` and `MSP2_INAV_ARM_DISARM` through the normal INAV arming/disarming path.
- Added `MAV_CMD_NAV_RETURN_TO_LAUNCH`, the ArduPilot RTL/RTH `MAV_CMD_DO_SET_MODE` case, `MSP2_INAV_ACTIVATE_RTH`, and Programming Framework operation `61` through the normal INAV RTH mode path by adding a temporary `BOXNAVRTH` source to the RC mode selector instead of setting the failsafe/geozone forced-RTH latch. A later pilot RC flight-mode change or disarm clears the temporary source.
- Extended `MAV_CMD_DO_SET_MODE` for QGC/ArduPilot pause-style Loiter/PosHold requests. `PLANE_MODE_LOITER`, `COPTER_MODE_LOITER`, `COPTER_MODE_POSHOLD`, and `COPTER_MODE_BRAKE` now enter normal INAV PosHold at the current position and altitude through a temporary `BOXNAVPOSHOLD` source.
- Added `MAV_CMD_NAV_LAND`, `MSP2_INAV_ACTIVATE_LANDING`, and Programming Framework operation `62` as normal waypoint-style landing at the current position. This does not use emergency landing.
- Direct LAND uses a transient waypoint without modifying the uploaded mission; mission LAND items retain their supplied coordinates.
- Added `MAV_CMD_DO_SET_HOME` through the existing waypoint `0` backend. MSP continues to use `MSP_SET_WP` waypoint `0`, so no duplicate MSP home command was added.
- Added `MSP2_INAV_TIMESYNC`, returning the same monotonic nanosecond boot clock used by MAVLink `TIMESYNC`.
- Added temporary fixed-wing PosHold loiter-radius override support. MAVLink uses `MAV_CMD_DO_REPOSITION.param3` in meters; MSP appends `int32_t loiterRadius` in centimeters to `MSP2_INAV_SET_GLOBAL_TARGET` and appends the active override to `MSP2_INAV_NAV_TARGET`. The override is volatile and clears on disarm/reboot.
- Added an explicit `MAV_CMD_NAV_TAKEOFF` handler returning `MAV_RESULT_UNSUPPORTED` as the foundation for later takeoff work.
- Synchronized the companion `mspapi2:mavlink_multiport2` metadata and added arm/disarm, RTH, LAND, and timesync helpers.

## What this branch changes

- Splits the old monolithic `src/main/telemetry/mavlink.c` implementation into focused modules for runtime, streams, routing, mission handling, modes, and FC-facing message handling.
- Adds support for up to 4 concurrent MAVLink telemetry ports (`MAX_MAVLINK_PORTS`), with per-port runtime state and per-port configuration.
- Adds route learning and forwarding between MAVLink ports:
  - learned routes are tracked by `(sysid, compid) -> ingress port`
  - targeted traffic is forwarded only where a route is known
  - broadcasts are forwarded to other MAVLink ports, with local handling rules for specific control messages
- Keeps one fixed local FC MAVLink identity as `(mavlink_sysid, MAV_COMP_ID_AUTOPILOT1)` instead of introducing per-port FC component IDs; attached devices remain remote routed components learned from traffic.
- Moves MAVLink configuration from a single global port model to per-port settings:
  - `mavlink_port{1-4}_*_rate`
  - `mavlink_port{1-4}_min_txbuffer`
  - `mavlink_port{1-4}_radio_type`
  - `mavlink_port{1-4}_high_latency`
- Keeps port 1 as the main fully-streaming MAVLink port by default, while ports 2..4 start in a conservative profile with heartbeat enabled and other streams disabled until requested.
- Support of [High Latency service](https://mavlink.io/en/services/high_latency.html)
- Adds half-duplex etiquette improvements so a shared MAVLink RX/telemetry serial link configured with `serialrx_halfduplex` backs off after RX before transmitting.

## Protocol and behavior improvements

- Includes the `mav_fix2` behavior fixes that were already part of the branch history.
- Adds proper local execution for broadcast/system-broadcast control traffic where appropriate
- Replaces the older stream-bucket-only `MAV_CMD_SET_MESSAGE_INTERVAL` behavior with per-message interval overrides layered on top of the existing stream model.
- Splits some periodic scheduling out of shared stream buckets so messages such as `GPS_RAW_INT`, `GLOBAL_POSITION_INT`, `BATTERY_STATUS`, `SCALED_PRESSURE`, and `SYSTEM_TIME` can be controlled more correctly.
- Adds `SYSTEM_TIME` output and corresponding request/interval support.
- Makes mission transfers persistent, partner/port-owned, retry-capable, and timeout-bounded.
- Adds `PING`, `TIMESYNC`, `MISSION_CURRENT`, indexed mode discovery, requested interval reporting, GNSS accuracy extensions, arming-disable `STATUSTEXT`, and de-spammed OSD-derived `STATUSTEXT`.
- Adds MAVLink/MSP parity for arm/disarm, normal RTH mode activation including the ArduPilot `DO_SET_MODE` RTL case, normal current-position LAND, set-home through waypoint `0`, and MSP boot-time synchronization.

## MSP-over-MAVLink tunnel

- Requires configurator change
- Adds MSP transport over MAVLink `TUNNEL` using private payload type `0x8001`.
- Reuses the existing MSP parser and encoder outside the normal serial-only path by exposing the needed parser/command/encode entry points from `msp_serial`.
- Preserves MSP framing symmetry end-to-end:
  - MSPv1 requests receive MSPv1 replies
  - MSPv2 requests receive MSPv2 replies
- Replies are emitted back on the ingress MAVLink port only.
- Supports reboot post-processing over the tunnel.
- Explicitly rejects serial passthrough and ESC 4way passthrough over the tunnel.
- Requires MAVLink 2 for tunnel transport.

## User-visible impact

- INAV can now host multiple MAVLink telemetry ports at the same time instead of behaving like a single-port MAVLink endpoint.
- Ground stations and companion links can request streams and particular messages.
- Routing is now usable for multi-endpoint and relay/radio setups.
- Broadcast-targeted MAVLink control traffic behaves more like operators and GCS software expect on multi-endpoint networks.
- Guided commands, stream interval requests, capability requests, and mission interactions behave more consistently with MAVLink expectations than before.
- GCS and companion applications can arm/disarm, trigger the configured RTH sequence, command a normal landing at the current position, and update home through standard MAVLink commands.
- Configurator access over an existing MAVLink telemetry link becomes possible through MSP-over-MAVLink tunnel support.

## Documentation and tests

- Adds a dedicated `docs/Mavlink.md` document describing the implemented behavior, supported messages/commands, routing, stream configuration, tunnel support, and known MAVLink differences.
- Updates MAVLink-related settings documentation and MSP development docs where relevant.
- Adds a large unit test suite in `src/test/unit/mavlink_unittest.cc` covering routing, mission flow, guided and command handling, stream intervals, protocol/capability requests, telemetry details, and MSP tunnel behavior.
- The branch also includes live SITL validation of the refactored implementation, including a routing compliance pass and an end-to-end MSP-over-MAVLink tunnel smoke test with reboot and reconnect recovery.
- Current verification after the MAVLink mission hardening pass:
  - MAVLink mission unit filter passed: `mavlink_unittest --gtest_filter='MavlinkTelemetryTest.Mission*'` (`22/22`)
  - complete warnings-as-errors SITL rebuild passed: `ninja -C inav/cmake/build_SITL`
  - Python mission tester syntax and case listing passed
  - live SITL MAVLink mission rig passed all eight cases: `src/test/mavlink/missions/run_mavlink_mission_tester.sh`
  - full `mavlink_unittest`: `86/86` passing (the two OSD `STATUSTEXT` throttling failures were fixed 2026-07-11)
  - companion `mspapi2` command-helper tests from the previous command-control pass: `4/4` passed

## Important limits / non-goals

- This does not turn INAV into a full ArduPilot/PX4-class MAVLink vehicle implementation.
- MAVLink parameter API support remains intentionally minimal.
- Ports 2..4 do not start with full stream output by default.
- Directed forwarding depends on route learning, so the first targeted packet to a never-seen endpoint may not forward until that endpoint has transmitted at least once.
- MSP-over-MAVLink is for configurator/MSP access over MAVLink links; it is not intended as a generic serial tunnel, and CLI mode is not provided over this path.
- MAVLink mission support remains intentionally partial and does not provide full parity with INAV's MSP mission model.
- MAVLink mission downloads are best-effort reconstruction from INAV's stored MSP waypoint list and must not be treated as reliable canonical mission backups.
- `MAV_CMD_NAV_TAKEOFF` is explicitly recognized but remains unsupported.
- `nav_roi`, `gcs_improve`, geopointing, camera/payload work, and other independent feature branches are not included in this PR.

## Open Questions

- Is four concurrent MAVLink ports the right long-term cap?
- What are the final flash and runtime costs across representative flight-controller targets?
- Should the MSP tunnel payload type be registered formally with MAVLink?
