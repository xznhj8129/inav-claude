Previous (unlogged)
Implemented mavlink multiport feature and QoL improvements as detailed in plans

2026-04-09 03:05:05 EDT
- Reviewed `MAVLINK_ROADMAP.md`, `ROADMAP.md`, `inav/docs/Mavlink.md`, the live `mavlink_multiport2` source modules, and the adjacent feature notes (`gcs_improve`, `TakeoffMode`, `NavROI`, `GCSMode`, `GimbalPOI`) specifically to map what is still missing for a serious RAS-A / ATAK-style MAVLink push.
- Wrote `BIGPUSH.md` at the workspace root as the integrated execution plan. The plan treats `mavlink_multiport2` as the substrate, recommends a new `maintenance-10.x` integration branch (`frog_mavlink_dev`), and sequences the work as: baseline port/stabilization, GCS control plane, guided/offboard control, full takeoff-to-landing chain, read-only parameter microservice, then ROI/gimbal/camera follow-ons.

2026-04-09 03:05:05 EDT
- Fetched `inav` upstream and synchronized local `master`, `maintenance-9.x`, and `maintenance-10.x` with upstream, then returned to `mavlink_multiport2`.
- Confirmed `maintenance-10.x` is already current with upstream, while `maintenance-9.x` has newer MSP work not yet present on `maintenance-10.x`.
- Reviewed the specific upstream MSP deltas to carry forward into the future INAV 10 integration branch:
  - `216b76c21` / `f0f41be72`: `MSP2_INAV_SET_WP_INDEX` and `MSP2_INAV_SET_CRUISE_HEADING` lineage
  - `9ce075269`: `MSP_RESULT_NO_REPLY` fix for MSP-over-telemetry passthrough
- Revised `BIGPUSH.md` to match the user's updated constraints:
  - no redundant full validation round immediately after branch creation/replay
  - no port sweep/stress work
  - go straight into feature accumulation after quick compile/unit/smoke checks
  - move `nav_roi` much earlier
  - defer camera/video microservices
  - explicitly frame the push as both MAVLink interop work and MSP autonomy-platform expansion
  - reserve one large HITL/GCS validation round for the end

2026-04-09 03:48:59 EDT
- Tightened `BIGPUSH.md` again so the full human-run HITL / GCS / manual-flying test is explicitly the last implementation phase, not just a generic validation pass.
- Clarified that this final phase is where manual debugging begins, after feature accumulation is mostly complete, and that human HITL time should not be spent earlier unless absolutely necessary.

2026-04-09 03:48:59 EDT
- Removed the implication that this push should introduce a first-class machine-control regime / ownership-session architecture rewrite.
- Updated `BIGPUSH.md` to state the opposite explicitly: stay pragmatic, work within the current control/navigation structure, avoid inner-sanctum redesign unless a real blocker forces it, and leave deeper architecture research for a later effort.

2026-04-01 16:13:58 EDT
- Implemented FC-side MSP-over-MAVLink tunnel support on `mavlink_multiport2`.
- Refactored `msp_serial` so the MSP byte parser and command processing can be reused outside serial ports, and added packet-to-buffer encoding for tunnel replies.
- Added `TUNNEL` handling in `src/main/telemetry/mavlink.c` with ingress-port-local delivery, private payload type `0x8001`, MSP reply fragmentation, and post-process gating that allows reboot but rejects passthrough-style commands.
- Rebuilt SITL with `cmake -S inav -B inav/build_SITL -DSITL=ON` and `cmake --build inav/build_SITL -j4`.

2026-04-01 17:17:19 EDT
- Created `inav-configurator:mavlink_multiport2` from `maintenance-10.x`.
- Added explicit `MAVLink Tunnel` controls under `Wireless mode`, with `SYSID` selection where `0` means first FC heartbeat seen.
- Added a minimal MAVLink parser/builder in `js/mavlink/mspTunnel.js` for `HEARTBEAT` discovery and `TUNNEL` wrapping/unwrapping using source identity `253/25` and payload type `0x8001`.
- Hooked tunnel mode into the configurator connection flow so MSP handshake waits for heartbeat discovery, forces the wireless-style hard lock, and uses a longer timeout.
- Persisted tunnel UI state in the port handler and rebuilt the app with `npm run package`.

2026-04-01 17:31:58 EDT
- Fixed the tunnel `SYSID` control label so it uses the same localization path as the surrounding header controls.
- Restyled the `SYSID` field to use the same boxed header treatment as the existing `IP:Port` override field.
- Rebuilt the configurator package after the UI fix with `npm run package`.

2026-04-01 17:39:21 EDT
- Moved the tunnel `SYSID` control onto its own row under the `MAVLink Tunnel` toggle so it no longer shifts the toggle row horizontally.
- Updated the wireless option show/hide logic to toggle the dedicated `SYSID` row.
- Rebuilt the configurator package after the layout fix with `npm run package`.

2026-04-01 18:18:43 EDT
- Reworked the header layout so `SysID` sits under the `IP:Port` field in the second row, with the label left-aligned and the numeric input right-aligned, keeping the header at two rows.
- Fixed the tunnel heartbeat log strings so `SysID` values interpolate correctly in the command log.
- Hid the CLI tab while connected through MAVLink tunnel mode because the current tunnel implementation carries MSP only, not raw CLI text.
- Added tunnel-side debug logging for heartbeat discovery, outbound MSP-to-TUNNEL wrapping, inbound TUNNEL chunks, decoded MSP replies, and MSP request timeouts.
- Rebuilt the configurator package after the layout and debug changes with `npm run package`.

2026-04-01 19:18:42 EDT
- Moved the `SysID` field into the top connection row to the left of `IP:Port`, widened the header input area to keep the layout horizontal, and kept the wireless/tunnel toggles in the second row.
- Added a specific CLI denial message for MAVLink tunnel mode instead of the generic firmware-upgrade warning.
- Fixed inbound MAVLink tunnel chunk handling so truncated MAVLink 2 payload tails are zero-padded back to the declared `payload_length` before the MSP parser sees them.
- Rebuilt the configurator package after the tunnel receive fix with `npm run package`.

2026-04-01 19:28:11 EDT
- Fixed the Electron UDP IPC mismatch by changing `udpClose` to an `ipcMain.handle` endpoint to match the preload `invoke()` call.
- Reworked the main-process UDP helper so it closes and recreates its socket cleanly instead of calling `disconnect()` on a socket that was never `connect()`ed.
- Changed tunnel-mode reboot recovery to use a full disconnect/reconnect cycle rather than the normal post-reboot raw MSP status probe.
- Rebuilt the configurator package after the UDP and reconnect fixes with `npm run package`.

2026-04-01 19:34:57 EDT
- Expanded `inav/docs/Mavlink.md` with a fuller MSP-over-MAVLink tunnel section covering intended use, configurator-side expectations, and operational caveats.
- Documented the current configurator source identity (`253/25`), `target_component=0` usage, lack of CLI-over-tunnel support, and the need to restore truncated MAVLink2 payload tails before MSP parsing.

2026-04-01 19:43:34 EDT
- Trimmed the new `docs/Mavlink.md` tunnel documentation back to operator-relevant requirements.
- Removed configurator-internal implementation guidance from the end-user doc and replaced it with a shorter practical requirements subsection.

2026-04-01 19:45:26 EDT
- Cleaned up the live `docs/Mavlink.md` structure without reverting user edits: kept the merged routing/forwarding/local-handling section, removed the duplicate bottom high-latency stub, and expanded the real high-latency section with purpose and service-link context.

2026-04-01 19:53:52 EDT
- Committed the user's final `docs/Mavlink.md` layout adjustments, including moving the high-latency section back to the end of the document and tightening a few wording/link details.

2026-04-02 13:08:43 EDT
- Reviewed the latest firmware commit `4015d44e2` against its parent, the tunnel-related source paths, the existing BUGCHECK review bundle, and `docs/development/Development.md`.
- Appended a targeted bugfix proposal under `# CHARLES BUGFIX PLAN` in `mydev/branch/mavlink_multiport2/BUGCHECK.md`, keeping the recommended first patch scoped to the new MAVLink tunnel path in `src/main/telemetry/mavlink.c`.

2026-04-02 13:33:25 EDT
- Applied the tunnel safety fixes in `src/main/telemetry/mavlink.c`: reject malformed `payload_length > 128`, reset stale partial tunnel MSP state after a timeout, reject `MSP_SET_PASSTHROUGH` before MSP command dispatch, move tunnel reply/frame buffers out of the telemetry-task stack into file-scope storage, and pass the real ingress serial port to allowed post-process callbacks.
- Updated `docs/Mavlink.md` so the tunnel contract states passthrough-class commands are rejected before execution.
- Extended `src/test/unit/mavlink_unittest.cc` to link the shared MSP serial helpers and added focused tunnel regression tests for malformed length rejection, pre-dispatch passthrough rejection, reboot post-process port handling, stale partial-frame timeout reset, and multi-message tunnel reply fragmentation.
- Verification:
- `cmake --build inav/build_unit --target mavlink_unittest -j4`
- `inav/build_unit/src/test/unit/mavlink_unittest --gtest_filter=MavlinkTelemetryTest.Tunnel*`
- `inav/cmake/docker_build_sitl.sh`
- The new tunnel tests passed. The full `mavlink_unittest` binary still reports three pre-existing mission item failures unrelated to the tunnel patch: `MissionItemIntSingleItemAcksAccepted`, `MissionItemIntSingleFinalItemAllowsAutocontinueZero`, and `MissionItemIntNonFinalAutocontinueZeroIsRejected`.

2026-04-02 13:40:19 EDT
- Re-reviewed `mydev/branch/mavlink_multiport2/BUGCHECK.md` against the live `src/main/msp/msp_serial.c` implementation and confirmed the remaining `msp_serial` issue was the duplicated frame-construction path between `mspSerialEncodePacket()` and `mspSerialSendPacket()`.
- Refactored `src/main/msp/msp_serial.c` so both call sites now use one internal `mspSerialPrepareFrame()` helper for header construction, jumbo/V2-over-V1 sizing, and CRC generation. This removes the duplicated protocol logic without changing the public API or serial/tunnel behavior.
- Hoisted `V1_CHECKSUM_STARTPOS` out of the old function-local macro position into normal file scope so the framing code no longer depends on preprocessor leakage between functions.
- Verification:
- `cmake -S inav -B inav/build_verify -DTOOLCHAIN=`
- `cmake --build inav/build_verify --target mavlink_unittest -j4`
- `inav/build_verify/src/test/unit/mavlink_unittest --gtest_filter=MavlinkTelemetryTest.Tunnel*`
- `inav/cmake/docker_build_sitl.sh`
- The focused tunnel tests passed again and the SITL script build completed successfully with the refactored `src/main/msp/msp_serial.c` compiled into the host target.

2026-04-02 14:17:04 EDT
- Backed out the broad shared-code refactor from `src/main/msp/msp_serial.c` and restored `src/main/msp/msp_serial.c`, `src/main/msp/msp_serial.h`, and `src/main/io/serial.c` to maintenance-style structure wherever possible.
- Kept only the minimum tunnel-facing seams in `src/main/msp/msp_serial.c` and `src/main/msp/msp_serial.h`: one exported byte parser wrapper, one encode-to-buffer helper, and one command-processing helper that lets `src/main/telemetry/mavlink.c` execute MSP commands without going through the serial-port send path.
- Restored the maintenance implementation details needed to support that revert cleanly, including the passthrough path in `src/main/io/serial.c` and the corresponding baseline declarations/behaviour in `src/main/io/serial.h`, `src/main/drivers/serial.c`, and `src/main/drivers/serial.h`.
- Updated `src/main/telemetry/mavlink.c` and `src/test/unit/mavlink_unittest.cc` to use the reduced helper surface instead of the earlier shared refactor shape.
- Verification for the reduced design was completed in the same session before the final exact `serial.c` restore:
- `cmake -S inav -B inav/build_verify -DTOOLCHAIN=`
- `cmake --build inav/build_verify --target mavlink_unittest -j4`
- `inav/build_verify/src/test/unit/mavlink_unittest --gtest_filter=MavlinkTelemetryTest.Tunnel*`
- `inav/cmake/docker_build_sitl.sh`
- The focused tunnel tests passed and the SITL script build completed successfully.

2026-04-02 14:20:42 EDT
- Squashed the commit range starting at `33004c2ca2b6da7ce50763274360749f6281e505` into one replacement commit on top of `4015d44e2`.
- Dropped the accidental `src/utils/mavlink_tests/*` deletions from the rewritten history before recommitting, so the squashed result contains only the intended MAVLink MSP tunnel work.

2026-04-02 14:26:08 EDT
- Re-applied the intended deletion of `src/utils/mavlink_tests/*` by request, committed it as `remove mavtests`, then immediately squashed it into the top tunnel commit.
- Final branch tip after the rewrite is one local commit, `6145317cc` (`Harden MAVLink MSP tunnel`), on top of `4015d44e2`.

2026-04-02 14:26:08 EDT
- Revisited the scope of the top bugfix commit and removed the unrelated serial passthrough changes that had reintroduced the old Hayes `+++` escape-sequence implementation and its support helpers.
- Restored `src/main/io/serial.c`, `src/main/io/serial.h`, `src/main/drivers/serial.c`, and `src/main/drivers/serial.h` exactly to `4015d44e2`, leaving the bugfix delta confined to `src/main/telemetry/mavlink.c`, `src/main/msp/msp_serial.c`, and `src/main/msp/msp_serial.h` plus docs/tests.
- Verification:
- `inav/cmake/docker_build_sitl.sh`
- SITL build passed after the serial-file revert. The old `build_verify` unit-test directory was not present in this workspace, so the tunnel gtests were not rerun in this last narrowing pass.

2026-04-02 14:39:01 EDT
- Squashed the top bugfix commit into `4015d44e2a6ea2dc80c6fa8c1ad97e1ad92dc943` by resetting to its parent and recommitting the combined tree as one replacement commit with the original message `Add MSP tunnel over MAVLink`.
- Final branch tip after this rewrite is `f2dacc188`, which now contains both the original tunnel implementation and the narrowed safety fix in a single commit.

2026-04-03 12:27:43 EDT
- Reviewed `mavlink_multiport2` against the ArduPilot routing/requesting-data docs and the MAVLink ID-assignment guide, then wrote the findings verbatim into `mydev/branch/mavlink_multiport2/REVIEW.md` for follow-up.

2026-04-03 13:04:32 EDT
- Rewrote `mydev/branch/mavlink_multiport2/REVIEW.md` to reflect the clarified conclusions: broadcast/system-broadcast local execution is a real bug, `SET_MESSAGE_INTERVAL` is still stream-backed and lacks a per-message rate table, duplicate `compid` defaults are only a problem once multiple MAVLink ports are enabled, and `SYSTEM_TIME` should be added using the existing internal boot time source.

2026-04-03 17:50:19 EDT
- Moved the shared MAVLink enums, structs, constants, and mode descriptors out of `src/main/telemetry/mavlink.h` into `src/main/mavlink/mavlink_types.h` so the main MAVLink module owns its common type surface.
- Kept `src/main/telemetry/mavlink.h` as the thin telemetry adapter header and updated internal MAVLink users plus the unit test to include `mavlink/mavlink_types.h` directly.
- Renamed the new shared header away from the ambiguous `mavlink.h` filename to `mavlink_types.h` and updated `src/main/CMakeLists.txt` accordingly.
- Verification:
- `cmake --build inav/build/tests_mavrefactor --target mavlink_unittest -j4`
- `inav/build/tests_mavrefactor/src/test/unit/mavlink_unittest`
- `inav/cmake/docker_build_sitl.sh`
- The full `mavlink_unittest` suite passed all 46 tests and the SITL script build completed successfully with the renamed shared header.

2026-04-03 18:03:33 EDT
- Moved the outbound MAVLink message pack/send surface out of `src/main/fc/fc_mavlink.c` into `src/main/mavlink/mavlink_streams.c`, including heartbeat, status, GPS, mode-reporting, protocol-version, autopilot-version, home-position, and high-latency helpers.
- Added a narrow `mavlinkSendRequestedMessage()` entry point in `src/main/mavlink/mavlink_streams.c` / `src/main/mavlink/mavlink_streams.h` so incoming `REQUEST_MESSAGE` and `GET_HOME_POSITION` handling in `src/main/fc/fc_mavlink.c` no longer needs direct knowledge of all outbound senders.
- Reduced `src/main/fc/fc_mavlink.h` to the dispatch API, kept `src/main/fc/fc_mavlink.c` focused on incoming handlers plus mission/command helpers, and made the mode tables private to `mavlink_streams.c` instead of exporting them through `mavlink_types.h`.
- Verification:
- `cmake --build inav/build/tests_mavrefactor --target mavlink_unittest -j4`
- `inav/build/tests_mavrefactor/src/test/unit/mavlink_unittest`
- `inav/cmake/docker_build_sitl.sh`
- `cmake --build inav/build/tests_mavrefactor --target mavlink_unittest -j4`
- The `mavlink_unittest` suite passed all 46 tests, the SITL script build completed successfully, and the final header-narrowing pass rebuilt `mavlink_unittest` cleanly.

2026-04-03 13:20:29 EDT
- Re-checked the component-identity question against ArduPilot `mavlink-basics`, `mavlink-routing-in-ardupilot`, and `libraries/GCS_MAVLink/MAVLink_routing.cpp`, then updated `mydev/branch/mavlink_multiport2/REVIEW.md` to make the transport-vs-component distinction explicit: the FC should keep one local autopilot `compid`, while attached MAVLink devices identify themselves and are learned per port by routing.

2026-04-03 13:52:49 EDT
- Implemented the `mavlink_multiport2` review fixes in `inav/src/main/telemetry/mavlink.c`, `inav/src/main/telemetry/mavlink.h`, `inav/src/main/telemetry/telemetry.c`, and `inav/src/main/telemetry/telemetry.h`.
- Broadcast-targeted local control traffic now executes locally for `COMMAND_*`, `REQUEST_DATA_STREAM`, `SET_POSITION_TARGET_*`, and `PARAM_REQUEST_LIST` while mission protocol handlers remain exact-target only.
- Replaced the stream-bucket-only `MAV_CMD_SET_MESSAGE_INTERVAL` behaviour with per-message overrides layered on top of the existing stream-rate model, and split periodic scheduling for GPS position messages, `BATTERY_STATUS`, `SCALED_PRESSURE`, and new `SYSTEM_TIME`.
- Removed the per-port MAVLink FC `compid` settings from `src/main/fc/settings.yaml`, fixethe FC local identity to `MAV_COMP_ID_AUTOPILOT1`, regenerated `docs/Settings.md`, and updated `docs/Mavlink.md` to describe the new routing and scheduling behaviour.
- Extended `src/test/unit/mavlink_unittest.cc` with coverage for broadcast-local execution, same-sysid remote components, per-message interval overrides/reset, `SYSTEM_TIME`, and the fixed local identity model.
- Verification:
- `cmake -DTOOLCHAIN=none -B build/unit_mavlink_multiport2_top`
- `cmake --build build/unit_mavlink_multiport2_top --target mavlink_unittest -j4`
- `build/unit_mavlink_multiport2_top/src/test/unit/mavlink_unittest`
- `cd inav/cmake && ./docker_build_sitl.sh`
- Results:
- The MAVLink unit target built cleanly and all newly added MAVLink tests passed.
- The unit binary still has three pre-existing failing mission-item tests: `MissionItemIntSingleItemAcksAccepted`, `MissionItemIntSingleFinalItemAllowsAutocontinueZero`, and `MissionItemIntNonFinalAutocontinueZeroIsRejected`.
- SITL build completed successfully and produced `cmake/build_SITL/inav_9.0.1_SITL`.

2026-04-03 14:17:54 EDT
- Folded the pre-existing staged `inav/src/main/io/serial.c` fix into the local `mavlink_multiport2` review-fix commit by request.
- The added `serial.c` change is the narrow `#ifdef USE_TELEMETRY` guard around `telemetryCheckRxPortShared()` inside `isSerialConfigValid()`.
- Refreshed `mydev/branch/mavlink_multiport2/changes.diff` so it now includes the `serial.c` delta alongside the MAVLink review-fix files.

2026-04-03 14:34:52 EDT
- Updated the branch benchmark harness under `mydev/branch/mavlink_multiport2/mavlink_tests/` so it matches the current branch instead of the older `mav_multi` setup.
- In `mav_multi_benchmark.py`, made `mavsdk` optional, fixed the local `mspapi2` fallback path/import for the `inav_development` workspace, removed the obsolete `mavlink_port{1-4}_compid` CLI writes, and added transient TCP reconnect handling around MAVLink send/receive loops so the harness does not die immediately on a short reconnect window.
- In `test_config_multiport4_sweep_rc460800_tele115200.yaml`, repointed the SITL binary, workdir, EEPROM path, runtime log, and markdown output path to this branch's current layout.
- Ran a short benchmark validation under `conda run -n drone` with reduced durations and `run_mavsdk_probe = false` to verify the harness against the recreated branch EEPROM.
- Results:
- The baseline benchmark section completed successfully for 1, 2, 3, and 4 active MAVLink ports.
- Measured baseline MSP failure rates on the short validation run were approximately `2.68%` (1 port), `4.03%` (2 ports), `0.67%` (3 ports), and `1.34%` (4 ports).
- The first stress scenario (`50 req/s` on telemetry port `5762`) triggered a runtime outage: all MAVLink sockets dropped, reconnect attempts saw `Connection refused`, and the next warmup timed out with zero FC heartbeats on ports `5761-5764`.
- SITL runtime log `mydev/branch/mavlink_multiport2/mavlink_tests/sitl_runtime_multi4_sweep.log` shows the initial expected `save` reboot, then later mass UART2-5 disconnects during the first stress run without a clean in-process diagnostic.

2026-04-03 17:13:52 EDT
- Reviewed `mydev/plans/refactor_plan.md` against the current `mavlink_multiport2` code before starting the refactor work.
- Kept the same broad target layout (`fc_mavlink`, `mavlink_runtime`, `mavlink_ports`, `mavlink_streams`, `mavlink_routing`, thin telemetry adapter), but updated the plan to match the current file reality instead of the older pre-branch shape.
- Recorded the stale assumptions explicitly: `src/main/telemetry/mavlink.c` is now ~3.5k LOC, already contains per-message interval overrides, already sends `SYSTEM_TIME`, already handles MSP-over-`TUNNEL`, and already uses fixed local `MAV_COMP_ID_AUTOPILOT1`.
- Tightened the implementation sequence so it starts with a private shared context in `mavlink_internal.h`, extracts ports/streams/routing first, moves payload builders before the full handler block, and defers public-header cleanup until the end to reduce compile/test churn.
- Added the missing practical note that `src/test/unit/CMakeLists.txt` must be updated along with `src/main/CMakeLists.txt` because the MAVLink unit target currently depends directly on `telemetry/mavlink.c`.

2026-04-03 17:17:32 EDT
- Updated `mydev/plans/refactor_plan.md` again to make the transfer method explicit: keep `src/main/telemetry/mavlink.c` completely untouched and authoritative until the final cutover step.
- Reworked the migration sequence accordingly so the new module files are populated first as a shadow transfer, with `telemetry/mavlink.c` left intact for one-to-one comparison and verification.
- The final cutover step is now the only step that rewires the build/runtime and reduces `telemetry/mavlink.c` to wrappers.

2026-04-03 17:37:50 EDT
- Implemented the refactor described in `mydev/plans/refactor_plan.md` on `mavlink_multiport2` with the planned split: `src/main/fc/fc_mavlink.c`, `src/main/mavlink/mavlink_runtime.c`, `src/main/mavlink/mavlink_ports.c`, `src/main/mavlink/mavlink_streams.c`, `src/main/mavlink/mavlink_routing.c`, plus the shared private header `src/main/mavlink/mavlink_internal.h`.
- Moved the file-static MAVLink state into the private shared context in `mavlink_internal.h`, preserved the fixed local identity model (`MAV_COMP_ID_AUTOPILOT1`), kept per-message interval overrides, `SYSTEM_TIME`, routing, mission handling, and MSP-over-`TUNNEL`, and reduced `src/main/telemetry/mavlink.c` to the thin telemetry API wrappers required by the plan.
- Updated `src/main/CMakeLists.txt` and `src/test/unit/CMakeLists.txt` so the new modules are built explicitly, and adjusted `src/test/unit/mavlink_unittest.cc` test-state reset so the mission tests run with clean arming/state flags between cases.
- Verification:
- `cd inav/cmake && ./docker_build_sitl.sh`
- `cmake -S . -B build/tests_mavrefactor -DTOOLCHAIN=none`
- `cmake --build build/tests_mavrefactor --target mavlink_unittest -j4`
- `build/tests_mavrefactor/src/test/unit/mavlink_unittest`
- Results:
- SITL build completed successfully and produced `cmake/build_SITL/inav_9.0.1_SITL`.
- `mavlink_unittest` built successfully and all 46 tests passed.

2026-04-03 18:22:51 EDT
- Split the MAVLink mode and mission concerns into dedicated modules under `src/main/mavlink/` as requested: added `mavlink_modes.c/.h` for mode enums, mappings, translation helpers, current/available mode emission, and added `mavlink_mission.c/.h` for mission frame helpers, mission item translation, upload/download flow, and mission request handlers.
- Trimmed `src/main/fc/fc_mavlink.c` back toward incoming-dispatch scope by moving the mission transaction and mission-item handling block into `mavlink_mission.c`, leaving `fc_mavlink` with incoming command handling and only the immediate mission-frame helpers it still calls from command/set-position paths.
- Moved the ArduPilot mode enums and mode selection surface into `src/main/mavlink/mavlink_modes.h`, moved mission support types into `src/main/mavlink/mavlink_mission.h`, and reduced `src/main/mavlink/mavlink_types.h` back to generic MAVLink runtime/shared transport types.
- Updated `src/main/mavlink/mavlink_streams.c` to consume the new mode module for heartbeat/high-latency/current-mode/available-mode work, and updated both `src/main/CMakeLists.txt` and `src/test/unit/CMakeLists.txt` so the new modules build in firmware and unit-test targets.
- Verification:
- `cmake --build build/tests_mavrefactor --target mavlink_unittest -j4`
- `build/tests_mavrefactor/src/test/unit/mavlink_unittest`
- `cd inav/cmake && ./docker_build_sitl.sh`
- Results:
- `mavlink_unittest` rebuilt successfully and all 46 tests passed.
- SITL build completed successfully and produced `cmake/build_SITL/inav_9.0.1_SITL`.

2026-04-03 18:30:00 EDT
- Ran a live SITL telemetry validation pass against `inav/cmake/build_SITL/inav_9.0.1_SITL` using the branch EEPROM `mydev/branch/mavlink_multiport2/eeprom.bin`.
- Explicitly verified process control before the test run: started SITL manually, confirmed listeners on TCP `5760`, `5761`, `5762`, `5763`, `5764`, then sent `Ctrl-C` and confirmed there was no remaining `inav_9.0.1_SITL` process and no remaining listeners on `5760-5764,5766,5767`.
- Restarted SITL under `mydev/branch/mavlink_multiport2/mavlink_tests/sitl_runtime_live_tests.log` and ran the normal non-benchmark telemetry tools:
- `conda run -n drone python mydev/branch/mavlink_multiport2/mavlink_tests/mavlink_msp_tunnel_smoketest.py --mavlink-endpoint tcp:127.0.0.1:5761 --target-system 1 --post-reboot-timeout 20`
- `conda run -n drone python mydev/branch/mavlink_multiport2/mavlink_tests/mavlink_routing_compliance_test.py --config <temp config based on mydev/branch/mavlink_multiport2/mavlink_tests/routing_test_config.yaml with report path redirected to mydev/branch/mavlink_multiport2/mavlink_tests/ROUTING_TEST.latest.md>`
- `inav/build/tests_mavrefactor/src/test/unit/mavlink_unittest`
- Results:
- MSP-over-`TUNNEL` smoke test passed end-to-end, including `MSP_API_VERSION`, `MSP_FC_VARIANT`, `MSP_FC_VERSION`, `MSP_BUILD_INFO`, `MSP_EEPROM_WRITE`, `MSP_REBOOT`, reconnect after reboot, and post-reboot tunnel recovery.
- Routing compliance test passed all 11/11 cases and refreshed `mydev/branch/mavlink_multiport2/mavlink_tests/ROUTING_TEST.latest.md`.
- `mavlink_unittest` passed all 46 tests.
- Explicitly shut SITL down again after the test run and confirmed there was no remaining `inav_9.0.1_SITL` process and no remaining listeners on `5760-5764,5766,5767`.

2026-04-03 18:36:27 EDT
- Reviewed `inav/docs/Mavlink.md` against the current implementation and `src/main/fc/settings.yaml`.
- Fixed the primary user doc to list the actual implemented commands `MAV_CMD_DO_CHANGE_ALTITUDE` and `MAV_CMD_CONTROL_HIGH_LATENCY`, which were missing from the supported-commands section.
- Corrected the documented default `EXTRA1` datastream rate from `3 Hz` to the actual `2 Hz` that matches the current CLI default in `settings.yaml`.
- No code changes or test reruns were needed for this pass; this was a documentation correction only.

2026-04-03 18:48:00 EDT
- Fixed MAVLink half-duplex TX gating so it keys off real per-port RX activity instead of the old single-port-era `receivedMessage` proxy that only covered locally handled traffic.
- Added `lastRxFrameUs` to the per-port MAVLink runtime state in `src/main/mavlink/mavlink_types.h`, reset it during port configure/free in `src/main/mavlink/mavlink_ports.c`, and stamped it on every successfully parsed MAVLink frame in `src/main/mavlink/mavlink_runtime.c` before any local/forwarding/routing decisions.
- Changed `mavlinkRuntimeHandle()` so half-duplex backoff now suppresses TX on a port whenever that physical port has received any full MAVLink frame within `TELEMETRY_MAVLINK_DELAY`, including forwarded-only, ignored, and non-local traffic.
- Applied that half-duplex backoff independently of `txbuffValid`, which closes the old hole where active flow control could still transmit immediately after RX on a half-duplex link.
- Verification:
- `cmake --build build/tests_mavrefactor --target mavlink_unittest -j4`
- `build/tests_mavrefactor/src/test/unit/mavlink_unittest`
- `cd inav/cmake && ./docker_build_sitl.sh`
- Results:
- `mavlink_unittest` rebuilt successfully and all 46 tests passed.
- SITL build completed successfully and produced `cmake/build_SITL/inav_9.0.1_SITL`.

2026-04-03 19:00:00 EDT
- Ran the branch benchmark harness `mydev/branch/mavlink_multiport2/mavlink_tests/mav_multi_benchmark.py` under `conda run -n drone` with the default config `mydev/branch/mavlink_multiport2/mavlink_tests/test_config_multiport4_sweep_rc460800_tele115200.yaml`.
- The harness started its own SITL instance, applied the CLI serial/MAVLink config, and exited cleanly without leaving an `inav_9.0.1_SITL` process behind.
- The benchmark now fails immediately in the first baseline scenario (`1 MAVLink port(s)` on shared RC/MAVLink port `5761`) during warmup with `TimeoutError: Warmup failed: heartbeat_counts={5761: 0} required=3 timeout_s=30.0`.
- Captured the failed run output in `mydev/branch/mavlink_multiport2/mavlink_tests/benchmark_run_2026-04-03.log`.
- Compared that result against the existing benchmark report `mydev/branch/mavlink_multiport2/mavlink_tests/TESTING_multiport4_sweep_rc460800_tele115200.md`, which shows the same benchmark/config previously completed successfully across all baseline and stress scenarios. That points to the new half-duplex RX backoff as the likely regression on the shared RC+telemetry port.
- No source changes were made in this pass.

2026-04-03 18:59:09 EDT
- Narrowed the MAVLink half-duplex condition in `src/main/mavlink/mavlink_runtime.c` so the per-frame RX backoff only applies on a port that is actually configured as the shared `FUNCTION_RX_SERIAL` MAVLink receiver port with `serialrx_halfduplex` enabled.
- Removed the accidental dependency on generic `telemetry_halfduplex` for MAVLink. That setting is documented for other telemetry protocols and MAVLink ports are not opened with `SERIAL_BIDIR`, so treating it as a MAVLink half-duplex switch was the direct cause of the benchmark regression.
- Updated `docs/Mavlink.md` so the half-duplex guidance now points to `serialrx_halfduplex` for shared MAVLink RX/telemetry wiring instead of suggesting `telemetry_halfduplex`.
- Verification:
- `cmake --build build/tests_mavrefactor --target mavlink_unittest -j4`
- `build/tests_mavrefactor/src/test/unit/mavlink_unittest`
- `cd inav/cmake && ./docker_build_sitl.sh`
- `conda run -n drone python mydev/branch/mavlink_multiport2/mavlink_tests/mav_multi_benchmark.py --config mydev/branch/mavlink_multiport2/mavlink_tests/test_config_multiport4_sweep_rc460800_tele115200.yaml`
- Results:
- `mavlink_unittest` rebuilt successfully and all 46 tests passed.
- SITL build completed successfully and produced `cmake/build_SITL/inav_9.0.1_SITL`.
- The benchmark no longer fails in the first shared RC+MAVLink baseline; it now completes the 1-, 2-, and 3-port baselines and only later fails in the 4-port baseline warmup after a SITL disconnect/reset. The failed rerun output was captured again in `mydev/branch/mavlink_multiport2/mavlink_tests/benchmark_run_2026-04-03.log`.

2026-04-03 19:08:41 EDT
- Implemented MAVLink `MISSION_ITEM_REACHED` emission, based on the MAVLink mission documentation requirement that the vehicle broadcast it whenever a new mission item is reached.
- Added a narrow navigation-side pending latch for reached mission items: `navigation.c` now marks the current mission item as reached when hold-time waypoints are actually reached, when altitude-enforced hold begins after altitude is satisfied, and as a fallback when transitioning through `NAV_STATE_WAYPOINT_NEXT` for the other mission item types.
- Added `navigationConsumeWaypointReached()` in `navigation.h` and consumed that event from `src/main/mavlink/mavlink_mission.c`, which now broadcasts `MISSION_ITEM_REACHED` to all active MAVLink telemetry ports once per pending event.
- Called the new mission-event sender once per MAVLink runtime handle in `src/main/mavlink/mavlink_runtime.c` so the notification is not tied to one port's periodic stream schedule.
- Updated the primary user doc `docs/Mavlink.md` to list `MISSION_ITEM_REACHED` under the event/on-demand outgoing messages.
- Added unit coverage in `src/test/unit/mavlink_unittest.cc` to verify that a pending reached item is emitted as `MAVLINK_MSG_ID_MISSION_ITEM_REACHED` with the expected sequence and is only broadcast once.
- Verification:
- `cmake --build build/tests_mavrefactor --target mavlink_unittest -j4`
- `build/tests_mavrefactor/src/test/unit/mavlink_unittest`
- `cd inav/cmake && ./docker_build_sitl.sh`
- Results:
- `mavlink_unittest` rebuilt successfully and all 47 tests passed.
- SITL build completed successfully and produced `cmake/build_SITL/inav_9.0.1_SITL`.

2026-04-03 19:22:39 EDT
- Added a small standalone SITL sanity harness under `tools/`:
- `tools/mavlink_sitl_sanity.py`
- `tools/mavlink_sitl_sanity.yaml`
- `tools/mavlink_sitl_sanity_mission.waypoints`
- The harness starts SITL against the branch EEPROM, applies the known-good multiport CLI serial layout, then runs a short pass/fail matrix across:
- MSP telemetry on UART1 via `mspapi2`
- MAVLink receiver telemetry on UART2
- quick RC override/echo on UART2 via `mydev/tools/mavlink_test_rc.py`
- MAVLink GCS heartbeat on UART3 via `mavproxy`
- mission upload and readback via MAVProxy `wp load` / `wp save`
- stream-rate setting via MAVProxy `set streamrate`
- message-rate setting via MAVProxy `messagerate set/get`
- The harness emits one unambiguous `PASS`/`FAIL` line per check plus a final `OVERALL` line, and keeps runtime artifacts in `mydev/branch/mavlink_multiport2/mavlink_tests/`.
- Initial live run exposed an overly strict RC sanity pattern and a too-conservative CLI save/reboot wait assumption; adjusted the RC pulse to a neutral mid-stick frame and kept the reboot handling aligned with the benchmark logic.
- Verification:
- `python -m py_compile tools/mavlink_sitl_sanity.py`
- `conda run -n drone python tools/mavlink_sitl_sanity.py`
- Results:
- All checks passed end-to-end:
- `MSP_UART1`
- `MAVLINK_TELEMETRY_UART2`
- `RC_QUICK_CHECK_UART2`
- `MAVLINK_GCS_UART3`
- `MISSION_UPLOAD_UART3`
- `MISSION_READBACK_UART3`
- `STREAM_RATE_UART3`
- `MESSAGE_RATE_UART3`
- The live run produced:
- `mydev/branch/mavlink_multiport2/mavlink_tests/sitl_runtime_sanity.log`
- `mydev/branch/mavlink_multiport2/mavlink_tests/mavproxy_sanity.log`
- `mydev/branch/mavlink_multiport2/mavlink_tests/mavlink_sitl_sanity_readback.waypoints`
- No `inav/` source files were changed in this pass, so there is no new repo commit.

2026-04-03 19:28:06 EDT
- Rewrote the branch history to squash the half-duplex break/fix pair into one commit, as requested.
- Squashed:
- `44ef897b1246b5bcd2e233cb567957aec7a14870`
- `df9a1d87e25bf204c8384d50414aa0a4c1a8ef4d`
- Resulting combined commit:
- `a412f8cc9`
- The later `MISSION_ITEM_REACHED` commit was replayed cleanly and now has hash `756c03174`.
- No source content changed in this pass beyond the requested history rewrite.
2026-04-03 19:34:25 EDT
- Drafted `mydev/branch/mavlink_multiport2/PR_DRAFT.md` from the actual `inav` git history and diff against `maintenance-10.x`, focusing on branch outcome rather than stale workspace notes. Captured the large MAVLink refactor, multi-port/routing work, protocol behavior changes, MSP-over-MAVLink tunnel support, and test/doc additions.

2026-04-22 19:23:02 EDT
- Reviewed `mydev/branch/frog_mavlink_dev/PLAN.2.md` only for next-phase direction, then read `mydev/RAS-A_MAVLink_Control_Link_Interoperability_Profile_.IOP_._v1.2 (1).pdf` and compared it against the live `mavlink_multiport2` MAVLink implementation/docs.
- Wrote `mydev/branch/mavlink_multiport2/RAS_A.md` as the branch-local RAS-A compliance note, separating what `mavlink_multiport2` already provides, what is only partial/non-compliant, and the concrete next implementation steps needed for FC-side control-link compliance.

2026-04-22 19:23:02 EDT
- Re-read the RAS-A PDF section by section in depth instead of just extracting the FC-facing command/telemetry gaps.
- Rewrote `mydev/branch/mavlink_multiport2/RAS_A.md` into a deeper document that walks the full profile structure: purpose/JRA, MAVLink transport and capabilities, networking assumptions, pairing, heartbeat/identity, generic payload attributes, telemetry, manual control, mission, parameter, extended parameter, command, camera, gimbal, terrain, exploration, and the closing system-modes/arming sections.
- Captured the broader conclusion that `mavlink_multiport2` is a good substrate for RAS-A-style FC-side interoperability work, but that the PDF defines a larger service and transport contract than the branch currently implements, especially around manual control, parameters, mode semantics, and the IP/UDP connection model.

2026-06-08 17:55 EDT
- Merged `upstream/maintenance-10.x` into `mavlink_multiport2` and resolved the GitHub conflict set.
- Kept the branch's split/multi-port MAVLink runtime while carrying forward upstream behavior:
  - MSP GPS `hwVersion` remains `uint8_t`/`sbufWriteU8`.
  - `crsf_use_legacy_baro_packet` is preserved beside the branch MAVLink common/per-port telemetry config.
  - MAVLink GPS raw/system-time sends use RTC Unix time when available.
  - Altitude target handling keeps the upstream `USE_BARO || USE_GPS` guard.
- Adopted upstream MSP doc generation/versioning changes, removed obsolete `msp_messages.checksum` and `rev`, regenerated MSP docs/enums, and reran CLI docs generation.
- Fixed an embedded `docs/ADSB.md` conflict-marker block from the upstream release merge, keeping SoftRF notes and one copy of CPA alert documentation.
- Updated `mydev/branch/mavlink_multiport2/changes.diff` against `upstream/maintenance-10.x`.
- Verification:
  - `cmake/docker_build_sitl.sh` from `inav/cmake` built `cmake/build_SITL/inav_9.1.0_SITL`.
  - `cmake -DTOOLCHAIN=none -GNinja -B /tmp/inav_mavlink_multiport2_unit . && ninja -C /tmp/inav_mavlink_multiport2_unit run-mavlink_unittest`
  - MAVLink unit test result: 52/52 passed.

2026-06-08 18:27 EDT
- Merged `upstream/maintenance-10.x` into `inav-configurator` branch `mavlink_multiport2`.
- Resolved the lone conflict in `js/serial_backend.js` by keeping upstream reconnect/tab reopen behavior while preserving the MAVLink MSP tunnel handshake and tunnel reconnect timing.
- Committed the configurator merge as `9eb8bee1`.
- Refreshed `mydev/branch/mavlink_multiport2/configurator_changes.diff` against `upstream/maintenance-10.x`.
- Verification:
  - `node --check inav-configurator/js/serial_backend.js`
  - `yarn lint` was not run because `yarn` is not installed in this shell.
  - `git diff --cached --check` reported upstream/merge trailing whitespace outside the resolved conflict file; those files were left untouched.

2026-06-08 19:05 EDT
- Fixed `inav-configurator` MAVLink tunnel startup behavior so enabling Wireless mode always reveals the MAVLink tunnel option unchecked.
- Stopped restoring a saved `wireless_mavlink_tunnel_enabled` value during port initialization; the user must explicitly enable the tunnel in the current session.
- Committed as `98b87553` (`Default MAVLink tunnel off`) and refreshed `mydev/branch/mavlink_multiport2/configurator_changes.diff`.
- Verification:
  - `node --check inav-configurator/js/serial_backend.js`
  - `node --check inav-configurator/js/port_handler.js`
  - `git diff --check -- js/serial_backend.js js/port_handler.js`
  - `yarn lint` (script currently prints `No linting configured`)

2026-06-28 10:22 EDT
- Compared the split INAV MAVLink implementation with Betaflight `87d4bd63` and implemented the useful behavioral gaps while retaining INAV's routing and navigation semantics.
- Replaced the ad-hoc mission counters with a transfer state machine that tracks sender and ingress port, retries uploads, times out downloads, accepts retransmission of the previous item, validates mission data before conversion, handles final `MISSION_ACK`, and emits protocol-specific failure ACKs.
- Persisted completed MAVLink uploads and mission clears through INAV nonvolatile waypoint storage. Empty waypoint lists can now be deliberately saved to erase a stored mission.
- Added 1 Hz `MISSION_CURRENT`, active-item flags on mission downloads, and mission-completion tracking from `MISSION_ITEM_REACHED`.
- Added `PING` and `TIMESYNC` responses, indexed `AVAILABLE_MODES` with standard-mode/property metadata, `AVAILABLE_MODES_MONITOR`, and requested `MESSAGE_INTERVAL` replies.
- Hardened `COMMAND_LONG` float-to-integer conversions and guided altitude/coordinate handling against non-finite and out-of-range values.
- Bounded MAVLink RX parsing to 64 bytes per scheduler invocation and phased initial stream/message deadlines to reduce scheduler monopolization and startup bursts.
- Retained UBlox ellipsoid altitude, speed accuracy, and heading accuracy in the common GPS solution and exposed them through `GPS_RAW_INT`.
- Added changed arming-disable reasons as `STATUSTEXT`, deferred until a MAVLink port is active.
- Updated `inav/docs/Mavlink.md`, `ROADMAP.md`, and branch `CHANGELOG.md`.
- Updated the SITL sanity fixture to target this branch and corrected its three-port serial/MAVLink configuration. The loader now omits `batch start`/`batch end` because it applies commands individually around save/reboot cycles.
- Verification:
  - MAVLink unit test binary: 61/61 passed.
  - `cmake/docker_build_sitl.sh`: built `cmake/build_SITL/inav_9.1.0_SITL`.
  - `git diff --check`.
  - `python3 -m py_compile tools/mavlink_sitl_sanity.py` and YAML parse.
- Live SITL serial sanity was attempted twice. Those runs exposed and led to fixes for the stale branch fixture and nested CLI batch handling. The corrected third run could not be started because the execution-credit quota rejected it; the live end-to-end rerun remains outstanding.
- The required local `inav` commit was also attempted, but staging was rejected by the same execution-credit quota before the git index changed. The source tree remains modified and uncommitted; nothing was pushed.

2026-07-04 14:17 EDT
- Implemented the scoped command-control work directly on `inav:mavlink_multiport2`.
- Added shared FC arming and native waypoint-0 home-gate helpers.
- Added MAVLink arm/disarm, RTH, normal current-position LAND, set-home, and explicit unsupported takeoff handling.
- Added matching MSPv2 LAND, RTH, arm/disarm, and nanosecond boot-time commands.
- Added a transient normal-LAND navigation path that does not mutate the uploaded mission; retained mission LAND coordinates.
- Added Programming Framework RTH and LAND operations.
- Updated MAVLink, Programming Framework, and MSP source documentation; regenerated MSP derived references.
- Created `mspapi2:mavlink_multiport2`, synchronized local protocol metadata, and added command/time helpers.
- Corrected the documentation handoff after initially writing it into the reference-only `frog_mavlink_dev` folder; all current records now live here.
- Verification:
  - `mavlink_unittest`: 69/69 passed.
  - `python3 -m unittest discover -s test -p 'test_command_helpers.py'`: 4/4 passed.
  - `cmake/docker_build_sitl.sh`: completed all 450 build steps with warnings treated as errors.
  - MSP JSON and generated enum JSON parse successfully; changed Python files compile successfully.

2026-07-04 15:10 EDT
- Updated `mydev/branch/mavlink_multiport2/PR_DRAFT.md`, which previously described the branch before the maintenance-10.x merge.
- Added the maintenance-base integration, Betaflight-derived mission/protocol reliability pass, MAVLink/MSP command-parity additions, current verification totals, and explicit exclusions.
- Prepared a concise PR-thread progress update covering the same work without including `nav_roi`, `gcs_improve`, geopointing, or other independent features.

2026-07-09 13:44 EDT
- Fixed SITL's MAVLink RX feature gate.
- Root cause: SITL defines `TARGET_FLASH_SIZE`, but `target/common.h` enables `USE_TELEMETRY_MAVLINK` and `USE_SERIALRX_MAVLINK` behind `MCU_FLASH_SIZE > 512` before `target/SITL/target.h` is included.
- Added explicit SITL target defines for MAVLink telemetry and MAVLink serial RX so `serialrx_provider = MAVLINK` compiles the receiver backend.
- Updated `inav/docs/Mavlink.md`, branch notes, and branch changelog to clarify that MAVLink RC uses `receiver_type = SERIAL` plus `serialrx_provider = MAVLINK`.
- Verification:
  - Initial sandboxed SITL build failed before compilation because `ccache` could not create a temp file under the user cache directory.
  - Escalated `cmake/docker_build_sitl.sh` completed all 450 steps and produced `cmake/build_SITL/inav_9.1.0_SITL`.
  - `nm` on the SITL binary now shows `mavlinkRxInit`, `mavlinkRxHandleMessage`, `serialRxInit`, and `mavlinkRuntimeInit`.

2026-07-09 14:20 EDT
- Fixed false `SYSTEM OVERLOADED` arming blocks in SITL.
- Root cause: the SITL scheduler deliberately sleeps between due tasks to avoid pegging a host CPU core, but the normal firmware load metric is based on waiting-task samples from a tight scheduler loop. With host sleeps enabled, most scheduler samples happen when work is already due, so `averageSystemLoadPercent` can sit at or above `100` even when the host is not overloaded.
- Changed SITL-only scheduler load accounting to use busy time over elapsed wall time, excluding the intentional host sleep. Normal firmware keeps the existing waiting-task load metric.
- Updated `inav/docs/SITL/SITL.md`, branch notes, and branch changelog.
- Verification:
  - `cmake/docker_build_sitl.sh` completed all 450 build steps and produced `cmake/build_SITL/inav_9.1.0_SITL`.

2026-07-09 14:35 EDT
- Fixed X-Plane SITL motor output when the INAV-XITL plugin is detected.
- Root cause: the X-Plane SITL output path sent only the plugin heartbeat when `inav_xitl/plugin/xitlDrefVersion` was present and skipped `sim/cockpit2/engine/actuators/throttle_ratio_all`.
- Kept the XITL heartbeat but always sends INAV motor output to X-Plane throttle.
- Updated `inav/docs/SITL/X-Plane.md`.
- Verification:
  - `cmake/docker_build_sitl.sh` completed all 450 build steps and produced `cmake/build_SITL/inav_9.1.0_SITL`.

2026-07-09 14:49 EDT
- Corrected X-Plane SITL pitch and yaw output signs.
- The channels were not swapped; pitch and yaw were inverted relative to X-Plane, so stabilized/autopilot corrections moved the wrong way.
- X-Plane pitch and yaw yoke outputs now use the same channel mapping but are multiplied by `-1`.
- Updated `inav/docs/SITL/X-Plane.md`.
- Verification:
  - `cmake/docker_build_sitl.sh` completed all 450 build steps and produced `cmake/build_SITL/inav_9.1.0_SITL`.

2026-07-09 15:01 EDT
- Superseded by the 20:28 correction below; kept here as chronology of the initial investigation.
- Investigated live X-Plane guided/loiter yaw glitches without rebuilding or resetting the simulator.
- Local MAVLink TCP diagnostics against `localhost:5763` were blocked by the execution sandbox permission layer, so diagnostics proceeded from fc diff, source paths, and test coverage.
- Found QGC's `Position (1)` label path: GUIDED was advertised in `AVAILABLE_MODES` as `MAV_STANDARD_MODE_POSITION_HOLD`. Since MAVLink common has no standard GUIDED enum, changed fixed-wing and copter GUIDED metadata to `MAV_STANDARD_MODE_NON_STANDARD` while keeping the mode name `GUIDED`.
- Added a unit-test check that indexed `AVAILABLE_MODES` reports fixed-wing GUIDED as named non-standard mode when POSHOLD and GCSNAV are configured.
- Found a likely fixed-wing loiter/guided twitch source: when POSHOLD/GCS-guided hold is effectively at the loiter center, the virtual loiter target's radial vector is undefined and can be selected from tiny position noise for one GPS sample.
- Added a 50 cm center deadband that seeds the fixed-wing loiter tangent from current ground course rather than the undefined center vector.
- Updated `inav/docs/Mavlink.md`, `inav/docs/Navigation.md`, branch notes, and branch changelog.
- No SITL rebuild or simulator reset was performed in order to preserve the active live flight session.

2026-07-09 20:28 EDT
- Corrected the mode-reporting direction after user review: ArduCopter/ArduPilot-compatible mode emulation remains the traditional `HEARTBEAT.custom_mode` path via the existing ArduPlane/ArduCopter maps.
- Made the MAVLink Standard Modes microservice build-time optional behind `USE_MAVLINK_STANDARD_MODES` and off by default. `AVAILABLE_MODES`, `AVAILABLE_MODES_MONITOR`, and `CURRENT_MODE` handlers are compiled only with that flag.
- Kept GUIDED as a named non-standard mode only inside the optional Standard Modes path; default QGC/ArduPilot compatibility should no longer depend on Standard Modes.
- Reverted the fixed-wing loiter-center tangent change because the yaw snap also appeared in ACRO, making navigation controller changes the wrong suspect for this symptom.
- Reviewed the web-chat mission upload patch. The important compatibility fix is relaxing unused waypoint params so QGC NaN/unused fields no longer make normal waypoint mission items invalid; the upload path also skips QGC planned-home item 0 and commits staged INAV waypoints after the transaction succeeds.
- Fixed an unused `param3` compile-risk introduced by the relaxed mission parameter handling and added a short comment documenting why QGC planned home is skipped.
- Updated `inav/docs/Mavlink.md`, branch notes, branch changelog, and the PR draft wording for the Standard Modes correction and mission upload behavior.
- No SITL rebuild or simulator reset was performed in order to preserve the active live flight session.

2026-07-09 20:37 EDT
- Reviewed `src/main/mavlink/mavlink_mission.c` for hyperspecific one-line helpers added during the QGC mission upload patch.
- Removed the current-message `mavlinkSendMissionAck()` wrapper, `mavlinkMissionAltitudeToCentimeters()`, `mavlinkMissionP3ForFrame()`, and `mavlinkMissionSequenceCanBeMapped()`.
- Inlined those simple expressions at their call sites while keeping semantic helpers that still clarify mission behavior, such as QGC planned-home detection and staged upload/commit helpers.
- Verification: `git -C inav diff --check` passed. No SITL rebuild was run.

2026-07-09 20:46 EDT
- Added a narrow `MAV_CMD_DO_SET_MODE` compatibility handler for the ArduPilot RTL/RTH custom mode.
- The handler requires `MAV_MODE_FLAG_CUSTOM_MODE_ENABLED`, accepts only the current vehicle type's RTL custom mode (`PLANE_MODE_RTL` or `COPTER_MODE_RTL`), requires armed state, then routes to RTH just like `MAV_CMD_NAV_RETURN_TO_LAUNCH`.
- Non-RTH `DO_SET_MODE` requests remain `UNSUPPORTED`; unarmed RTH requests remain `DENIED`.
- Added unit coverage for unarmed denial, armed RTH success, and non-RTH mode rejection.
- Updated `inav/docs/Mavlink.md` and branch changelog.

2026-07-09 21:04 EDT
- Investigated QGC vehicle-message spam from repeated `LOITERING AROUND HOME` notices.
- Found that INAV was exporting the current persistent OSD system message through MAVLink `STATUSTEXT` on every EXTRA3 stream tick, unlike ArduPilot/PX4-style queued/event text handling.
- Added per-port OSD-derived `STATUSTEXT` suppression state: last text string, severity, first-seen time for the current quiet window, and last-seen time for stale/gap detection.
- Changed OSD-derived text is sent immediately. Unchanged notices repeat after 30 seconds, warnings after 10 seconds, and critical messages after 5 seconds. Blank OSD status clears the remembered text.
- Added unit coverage for unchanged notice suppression/repeat, immediate changed-text send, and shorter warning repeat interval.
- Updated `inav/docs/Mavlink.md`, branch notes, changelog, and PR draft.
- Verification: `git -C inav diff --check` and `git -C inav diff --cached --check` passed. No SITL rebuild was run.

2026-07-09 21:21 EDT
- Corrected the command-triggered RTH backend after live testing showed `activateForcedRTH()` is not equivalent to switching into RTH mode.
- Added `activateRTHMode()`, which adds a temporary `BOXNAVRTH` source to the normal RC mode selector without setting the failsafe/geozone `forcedRTHActivated` latch.
- Moved `MAV_CMD_NAV_RETURN_TO_LAUNCH`, the ArduPilot RTL/RTH `MAV_CMD_DO_SET_MODE` case, `MSP2_INAV_ACTIVATE_RTH`, and Programming Framework operation `61` to `activateRTHMode()`.
- The temporary RTH mode source is retained across mode-selector updates until the pilot changes a real RC flight-mode selection, then it clears and control returns to the normal selector state.
- The temporary source also clears while disarmed, so a command-triggered RTH cannot survive into a later arming attempt.
- Left `activateForcedRTH()` intact for failsafe/geozone/internal forced-RTH users.
- Added unit coverage for the temporary RC mode source staying active across unrelated AUX changes, clearing on flight-mode changes, and clearing while disarmed.
- Updated docs, notes, changelog, PR draft, and MAVLink unit-test naming to distinguish normal RTH mode activation from forced-RTH latch behavior.

2026-07-10 10:42 EDT
- Updated the OSD flight-mode display to show `GCSN` when `isGCSValid()` is true, so active GCS-assisted POSHOLD/guided navigation is visible on the aircraft OSD instead of the generic hold/loiter label.
- Updated the branch changelog and PR draft with the operator-facing display change.

2026-07-10 11:03 EDT
- Investigated fixed-wing altitude loss in POSHOLD/loiter/post-RTH loiter with no live flight active.
- Reverted the branch-local unconditional ALTHOLD Z setpoint capture back to the upstream gated behavior, so ALTHOLD initialization only captures current altitude when the altitude controller is reset/setup.
- Found an X-Plane SITL altitude-state bug likely to explain slow loiter sink: X-Plane passed zero GPS NED velocity while `gpsFakeSet()` marked vertical velocity valid, and fake baro pressure came from X-Plane weather altimeter pressure rather than aircraft altitude.
- Updated X-Plane SITL to pass local velocity as GPS NED velocity and derive fake barometer pressure from aircraft elevation via `altitudeToPressure()`, matching the RealFlight SITL pattern.
- Updated `inav/docs/SITL/X-Plane.md`, branch notes, branch changelog, and PR draft.
- Verification:
  - Initial `ninja -C cmake/build_SITL -j1` failed because sandboxed ccache tried to write under `~/.cache/ccache`.
  - `CCACHE_DIR=/tmp/inav_ccache ninja -C cmake/build_SITL -j1` completed all 450 steps and produced `cmake/build_SITL/inav_9.1.0_SITL`.

2026-07-10 11:57 EDT
- Added a temporary GCS PosHold loiter-radius override for fixed-wing guided/loiter control.
- MAVLink `MAV_CMD_DO_REPOSITION.param3` now updates that radius in meters when finite; `0` clears the override back to the configured `nav_fw_loiter_radius`, and `NaN` leaves the current override unchanged.
- MSP `MSP2_INAV_SET_GLOBAL_TARGET` now accepts an appended `int32_t loiterRadius` in centimeters. Existing 13-byte payloads still leave the radius untouched; new 17-byte payloads use `0` to clear the override.
- MSP `MSP2_INAV_NAV_TARGET` now appends the current temporary loiter-radius override in centimeters, reporting `0` when the configured default is active.
- The override is volatile, cleared on disarm/reboot, and applied only while the navigation FSM is in POSHOLD_3D so it does not silently change RTH, mission, or autoland loiter behavior.
- Extended MAVLink `MAV_CMD_DO_SET_MODE` compatibility beyond RTL/RTH to accept QGC/ArduPilot pause-style Loiter/PosHold custom modes (`PLANE_MODE_LOITER`, `COPTER_MODE_LOITER`, `COPTER_MODE_POSHOLD`, `COPTER_MODE_BRAKE`).
- Added `activatePositionHoldMode()`, which uses the normal RC mode-selector path with a temporary `BOXNAVPOSHOLD` source, then copies the current position/altitude/heading into the active position-hold target.
- Updated `inav/docs/Mavlink.md`, generated MSP documentation, branch notes, changelog, and PR draft.
- Verification: `git -C inav diff --check` passed. A SITL build was started in-place but interrupted at the user's request; no completed build result is claimed for this change.

2026-07-10 17:12 EDT
- Recorded the user-found SITL compile failure in `mavlink_command.c`: the loiter-radius bounds check used a double literal path and tripped `-Werror=double-promotion`.
- Kept the user's correction using a float `maxLoiterRadiusMeters = (float)(UINT32_MAX / 100U)` and float comparison.
- Reviewed the user/web-chat MAVLink mission upload translator patch.
- Mission upload now allows up to `NAV_MAX_WAYPOINTS * 4 + 1` MAVLink mission items, stages translated INAV waypoints, skips QGC planned home item 0, and commits only after the upload succeeds.
- Added mission modifier handling for QGC-style separate MAVLink items: delay modifiers update the previous waypoint into/onto POSHOLD_TIME, altitude modifiers update the previous applicable geographic waypoint altitude while preserving P3 bitfield semantics, and speed changes become pending INAV leg speed for following geographic waypoints.
- Updated `inav/docs/Mavlink.md`, branch notes, changelog, and PR draft with the protocol-aware mission translation model and the observed QGC pause-toast caveat.
- Verification: `git -C inav diff --check` passed. No build was run.

2026-07-10 17:43 EDT
- Added `mydev/tools/mavlink_mission_tester.py`, `mydev/tools/mavlink_mission_tester.ini`, and `mydev/tools/run_mavlink_mission_tester.sh`.
- The mission tester uploads raw MAVLink `MISSION_ITEM_INT` cases through MAVProxy UDP and verifies the resulting native INAV mission through `mspapi2` MSP waypoint readback.
- Covered QGC planned-home skip, normal waypoints + land, waypoint hold plus `CONDITION_DELAY`, `DO_CHANGE_SPEED`, altitude modifier item folding/P3 preservation, `DO_JUMP` remap after skipped home, and rejected `MAV_CMD_NAV_TAKEOFF` with no partial mission commit.
- Added a short README at `mydev/tools/README_mavlink_mission_tester.md`.
- First self-contained run passed all six cases using SITL TCP `5763` for MAVLink and MSP TCP `5760` for readback.
- Harness detail: MAVProxy needs `--nowait --daemon` in this non-interactive runner; `mspapi2` needs a short socket read timeout (`20 ms`), because a read timeout longer than its public request timeout can make valid MSP replies appear to time out.
- Generated report: `mydev/branch/mavlink_multiport2/mavlink_tests/mission_tester_report.json`.

2026-07-10 17:58 EDT
- Moved the MAVLink mission test harness into the INAV source tree under `inav/src/test/mavlink/` for eventual repo integration.
- Updated the default mission coordinate center to Sneedville, Tennessee: `36.530440`, `-83.216383`.
- Updated the runner to write current test artifacts under `inav/src/test/mavlink/results/`; added a results `.gitignore` so logs/reports are local runtime artifacts.
- Removed the scratch copies from `mydev/tools/`.
- Re-ran the relocated self-contained suite from `inav/src/test/mavlink/run_mavlink_mission_tester.sh`.
- Verification: all six mission cases passed again; report generated at `inav/src/test/mavlink/results/mission_tester_report.json`.

2026-07-10 18:02 EDT
- Moved the mission-specific MAVLink functional test suite one level deeper to `inav/src/test/mavlink/missions/`.
- Updated script usage text, config paths, runner path calculations, result log paths, and README references for the final `mavlink/missions/` location.
- Re-ran the final-location self-contained suite from `inav/src/test/mavlink/missions/run_mavlink_mission_tester.sh`.
- Verification: all six mission cases passed; report generated at `inav/src/test/mavlink/missions/results/mission_tester_report.json`.

2026-07-10 18:57 EDT
- Reviewed MAVLink mission handling against the MAVLink mission service and INAV's native MSP waypoint model.
- Tightened QGC planned-home detection so a real current first waypoint is preserved instead of being skipped.
- Made mission upload/download sequence handling recoverable: unexpected upload items re-request the expected item, valid out-of-order download requests are served, and explicit upload cancel ACKs return the transfer to idle.
- Changed legacy `MISSION_REQUEST` downloads to answer with `MISSION_ITEM_INT`, matching the current MAVLink mission service expectation.
- Added mission snapshot/restore around upload commits, `MISSION_CLEAR_ALL`, and zero-count uploads so a persistence failure restores the previous INAV waypoint list instead of leaving RAM cleared or half-written.
- Reworked altitude conversion to validate finite meters, round through `llrintf` into `int64_t`, and bound-check before casting to `int32_t`; this avoids undefined overflow and still passes SITL `-Wdouble-promotion` / warnings-as-errors.
- Expanded unit mission coverage for clear/zero persistence failure restore, upload cancel, upload out-of-sequence retry, first-current absolute waypoint preservation, legacy download as `MISSION_ITEM_INT`, and out-of-order download requests.
- Expanded the live mission tester cases for current first waypoint preservation, failed upload preserving an existing mission, and legacy `MISSION_REQUEST` download behavior.
- Documented that MAVLink mission translation is lossy and that MAVLink mission downloads are best-effort reconstruction, not a reliable canonical copy of the INAV mission, in `inav/docs/Mavlink.md` and `inav.wiki/MSP-Navigation-Messages.md`.
- Verification: Python mission tester `py_compile` and `--list-cases` passed; `mavlink_unittest --gtest_filter='MavlinkTelemetryTest.Mission*'` passed `22/22`; SITL rebuilt successfully with `ninja -C inav/cmake/build_SITL`.
- Verification caveat: full `mavlink_unittest` currently reports `84/86` because the unrelated OSD `STATUSTEXT` throttling tests fail even when run alone. The live mission harness could not run in this sandbox because SITL was denied localhost TCP socket creation and the required escalation was unavailable.

2026-07-10 23:43 EDT
- Re-ran the live SITL MAVLink mission rig from `inav/src/test/mavlink/missions/run_mavlink_mission_tester.sh` with localhost socket access.
- Verification: all eight mission cases passed, including current first waypoint preservation, legacy `MISSION_REQUEST` download returning `MISSION_ITEM_INT`, rejected takeoff without partial commit, and failed upload preserving the preloaded mission.
- Generated report: `inav/src/test/mavlink/missions/results/mission_tester_report.json`.
- Log scanner notes were non-blocking expected/ambient messages: arming-disabled/GPS statustext from SITL, expected `MISSION_UNSUPPORTED` ACKs for negative cases, and the configured `/dev/ttyUSB0` serial proxy not being present.

2026-07-11 11:53 EDT
- Added MAVLink `STATUSTEXT` notice broadcasts for INAV flight-mode transitions.
- Mode notices use the exact requested text shape, `Notice: INAV: Entering <mode name>`, with mode names taken from INAV's telemetry flight-mode selection.
- Added special GCS-assisted navigation transitions: `Notice: INAV: Entering GCS NAV mode` and `Notice: INAV: Exiting GCS NAV mode`.
- Reused the active-port notice sender for arming-disabled `STATUSTEXT` and mode-change notices, while preserving the existing wait-for-active-port behavior for arming-disabled messages.
- Fixed OSD-derived `STATUSTEXT` repeat handling so unchanged warnings wait for the configured warning repeat interval instead of being resent by the old stale-text shortcut.
- Verification: `cmake --build build/tests_mavrefactor --target mavlink_unittest -j4` passed after approved googletest/ccache access; `build/tests_mavrefactor/src/test/unit/mavlink_unittest` passed `86/86`; `inav/cmake/docker_build_sitl.sh` passed and produced `cmake/build_SITL/inav_9.1.0_SITL`.

2026-07-11 12:41 EDT
- Fixed `lib/main/MAVLink/generate.sh` and `generate.bat` to generate the STorM32 dialect (`storm32.xml`) that INAV actually includes, instead of the catch-all dialect.
- Expanded generator cleanup so a previous `all.xml` run removes the extra generated dialect directories before regeneration.
- Regenerated the MAVLink headers from the patched STorM32 generator path; `storm32.h` again contains the merged `MAV_CMD` enum used by command, routing, and mission code.
- Restored the build surface to the 337-message STorM32/ArduPilot/common set instead of the 391-message `all` set.
- Verification: `./build.sh SPEEDYBEEF405WING` passed; memory report was FLASH `663560 B / 896 KB` (`72.32%`), RAM `120772 B / 128 KB` (`92.14%`), CCM `25296 B / 64 KB` (`38.60%`).
