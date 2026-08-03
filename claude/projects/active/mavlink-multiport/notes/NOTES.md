- Tunnel replies are addressed back to the sender `sysid/compid`, but local delivery accepts `target_component = 0`.
- INAV multi-port routing still depends on unique per-port `mavlink_portN_compid` values.
- This implementation requires MAVLink2 end-to-end for the tunnel frames because `TUNNEL` is message `385`.

## Command parity decisions

- Direct LAND is normal mission-style LAND at the current position through `NAV_STATE_WAYPOINT_RTH_LAND`, not `activateForcedEmergLanding()` or another emergency landing helper.
- The transient command LAND waypoint is separate from `waypointList`, so it does not overwrite or append to the uploaded mission.
- A LAND item uploaded in a mission keeps its supplied coordinates. Direct MAVLink/MSP LAND commands ignore coordinates and use the current position.
- Direct RTH uses `activateRTHMode()`, which adds a temporary `BOXNAVRTH` source to the normal RC mode selector. It deliberately does not use `activateForcedRTH()`, because that path sets the failsafe/geozone forced-RTH latch and is not equivalent to switching into RTH mode. The temporary source clears when the pilot changes a real RC flight-mode selection or the FC disarms.
- MSP home-setting needs no new command: `MSP_SET_WP` waypoint `0` already exposes the native home path.
- MAVLink `MAV_CMD_DO_SET_HOME` adapts both explicit global coordinates and `param1 = 1` current GNSS position to waypoint `0`.
- Home updates retain exactly the existing waypoint `0` gates; there is no custom saved-`ARM_HOME` reset behavior in this slice.
- `MSP2_INAV_TIMESYNC` returns the same monotonic boot-time clock as MAVLink `TIMESYNC`.
- MSP command IDs are `0x2224` LAND, `0x2225` RTH, `0x2227` ARM/DISARM, and `0x2228` TIMESYNC. The unused `0x2222` and `0x2226` values remain gaps rather than restoring superseded custom commands.
- Programming Framework operation IDs `61` and `62` trigger RTH and LAND respectively. Configurator UI work is outside this scoped branch.
- `nav_roi`, `gcs_improve`, geopointing, and unrelated non-MAVLink features remain separate.

## SITL MAVLink RX feature gate

- SITL uses `TARGET_FLASH_SIZE`, while `target/common.h` gates the normal MAVLink telemetry and serial-RX feature defines behind `MCU_FLASH_SIZE > 512`.
- Because `target/common.h` is included before `target/SITL/target.h`, SITL did not inherit `USE_TELEMETRY_MAVLINK` or `USE_SERIALRX_MAVLINK` from that MCU flash-size block.
- The failure mode was confusing: `serialrx_provider = MAVLINK` remained visible in settings metadata, but `serialRxInit()` had no compiled `SERIALRX_MAVLINK` case. On reboot, `rxInit()` therefore treated `receiver_type = SERIAL` as failed receiver initialization and rewrote it to `RX_TYPE_NONE`.
- SITL now defines both `USE_TELEMETRY_MAVLINK` and `USE_SERIALRX_MAVLINK` explicitly in its target header.

## SITL scheduler load accounting

- The normal firmware `averageSystemLoadPercent` metric is based on waiting-task samples from a tight scheduler loop.
- SITL intentionally sleeps between due tasks so it does not burn a host CPU core. That sleep made most scheduler samples occur when a task was already due, causing false `SYSTEM OVERLOADED` arming blocks.
- SITL now reports load from scheduler busy time over elapsed wall time, excluding the intentional host sleep. Non-SITL firmware keeps the existing waiting-task metric.

## X-Plane SITL motor output

- X-Plane SITL motor output is derived from the `Mxx-yy` entry in `--chanmap`; if no motor mapping is supplied, `motorValue` stays zero.
- PR `#11566` added INAV-XITL plugin detection and heartbeat handling, but the plugin-detected branch skipped the normal `sim/cockpit2/engine/actuators/throttle_ratio_all` output.
- SITL now keeps the plugin heartbeat and still sends throttle from INAV motor output.
- X-Plane pitch and yaw outputs require sign inversion at the SITL output layer. The branch-specific channel order remains throttle, roll, pitch, yaw.

## Live X-Plane guided/loiter observations

- The live simulator was available on `localhost:5763`, but the execution sandbox rejected local TCP access. Diagnostics continued from source, fc diff, and existing test coverage.
- QGC showing GUIDED as `Position (1)` exposed a wrong premise: ArduCopter-compatible mode emulation should be the traditional ArduPilot heartbeat `custom_mode` path, not the MAVLink Standard Modes microservice. Standard Modes are now optional behind `USE_MAVLINK_STANDARD_MODES` and off by default; if enabled, GUIDED is a named non-standard mode because MAVLink common has no GUIDED standard enum.
- QGC vehicle-message spam from `LOITERING AROUND HOME` came from INAV sampling the persistent OSD system message into MAVLink `STATUSTEXT` every EXTRA3 tick. ArduPilot/PX4 treat `STATUSTEXT` as a queued/event-style feed, not a raw periodic status label. The branch now suppresses unchanged OSD-derived `STATUSTEXT` per MAVLink port and only re-announces persistent notices/warnings/critical messages at severity-based intervals.
- In fixed-wing POSHOLD/GCS-guided hold, INAV remains in `NAV_STATE_POSHOLD_3D_IN_PROGRESS`; MAVLink guided targets update the special waypoint `255`, which updates `posControl.desiredState.pos`.
- Since the violent yaw snap also appears in ACRO, navigation position/heading controllers are not the primary suspect. Leave navigation code untouched until SITL/X-Plane output, attitude injection, RC input, or logging evidence points back there.
- Blackbox in SITL: source has `BLACKBOX_DEVICE_FILE` behind `SITL_BUILD`, but the default remains `SERIAL` unless a target enables flash/SD defaults. Configurator may only show serial because `MSP2_BLACKBOX_CONFIG` returns the current device/config and not a supported-device list; verify CLI `blackbox_device = FILE` directly before depending on file-backed SITL logs.

## MAVLink mission translation

- QGC missions do not map 1:1 onto INAV waypoint slots. QGC planned home is skipped, so MAVLink sequence `1` becomes INAV waypoint `1`; home remains the native INAV home/waypoint `0` path.
- Uploads are staged first: receive the whole MAVLink mission, translate into a temporary INAV waypoint list, validate/remap, then commit to the live INAV mission at the end. Failed uploads should not leave half-written missions in the FC.
- Supported navigation translation: `MAV_CMD_NAV_WAYPOINT` becomes WAYPOINT or POSHOLD_TIME when hold time is set; `MAV_CMD_NAV_LOITER_TIME` becomes POSHOLD_TIME; `MAV_CMD_NAV_LAND` becomes LAND; `MAV_CMD_DO_JUMP` becomes JUMP with the target remapped after translation.
- Supported modifier translation: `MAV_CMD_DO_CHANGE_SPEED` becomes pending INAV leg speed; `MAV_CMD_CONDITION_DELAY` modifies the previous waypoint into/onto POSHOLD_TIME; altitude modifier commands update the previous applicable geographic waypoint altitude.
- MAVLink delay/altitude/speed modifier items are often displayed by QGC as attached to a waypoint but uploaded as separate mission items. The bridge must apply them to the correct INAV mission item instead of storing them blindly.
- P3 handling must preserve INAV's bitfield semantics: bit 0 is AMSL/sea-level reference, while bits 1-4 are INAV user actions. Altitude-mode updates should set/clear bit 0 without clobbering the rest of P3.
- MAVLink mission downloads are only a best-effort reconstruction from the stored MSP waypoint list. They should be treated as unreliable for backups or full-fidelity editing because sequence count, modifier placement, command shape, and MSP-specific fields can be lost in translation.
- Transfer robustness expectations from the MAVLink mission service: out-of-sequence upload/download frames are recoverable by re-requesting or serving the requested item; explicit `MAV_MISSION_OPERATION_CANCELLED` ACK returns the transfer to idle; legacy `MISSION_REQUEST` still expects `MISSION_ITEM_INT`.

## X-Plane SITL altitude hold sink

- Fixed-wing POSHOLD/loiter/post-RTH loiter altitude loss in X-Plane SITL was not necessarily MAVLink-specific.
- X-Plane SITL was passing `gpsFakeSet()` zero NED velocity even though `gpsFakeSet()` marks both horizontal and vertical velocity valid. The position estimator therefore accepted `velNED[Z] = 0` instead of deriving sink/climb from altitude changes.
- X-Plane SITL was also feeding fake barometer pressure from `sim/weather/barometer_current_inhg`, which is the weather/altimeter setting rather than aircraft pressure. RealFlight SITL uses `altitudeToPressure(altitude)`.
- X-Plane SITL now passes local velocity as NED (`N = -local_vz`, `E = local_vx`, `D = -local_vy`) and derives fake barometer pressure from aircraft elevation.
- The branch-local unconditional ALTHOLD Z capture was also reverted to the upstream gated behavior. It was not the primary X-Plane altitude-estimator bug, but it could move the altitude target to the current sagged altitude on certain mode-boundary refreshes.

## Guided loiter-radius and pause behavior

- MAVLink uses `MAV_CMD_DO_REPOSITION.param3` as the fixed-wing loiter radius, matching the current MAVLink definition and ArduPlane behavior. The value is meters; finite `0` clears INAV's temporary override back to `nav_fw_loiter_radius`, and `NaN` leaves the override untouched.
- MSP does not add a new command for radius. `MSP2_INAV_SET_GLOBAL_TARGET` accepts the original 13-byte payload unchanged, or a 17-byte payload with appended `int32_t loiterRadius` in centimeters. Appended `0` clears the override; omitted field means no change.
- `MSP2_INAV_NAV_TARGET` appends the temporary override value in centimeters. `0` means no override is active and the configured default radius is being used.
- The override lives in `posControl.gcsLoiterRadiusOverride`, is cleared by `navigationInit()` and disarm handling, and is only returned by `navigationGetLoiterRadius()` while the navigation FSM is in `NAV_STATE_POSHOLD_3D_INITIALIZE` or `NAV_STATE_POSHOLD_3D_IN_PROGRESS`. This keeps RTH/mission/autoland loiter behavior on configured defaults unless they enter normal PosHold.
- QGC Pause was sending an ArduPilot `MAV_CMD_DO_SET_MODE` custom-mode request, not `DO_REPOSITION`. INAV now accepts the Loiter/PosHold pause modes and enters normal PosHold through a temporary `BOXNAVPOSHOLD` RC-mode source, then sets the current local position/altitude/heading as the active hold target.
- If QGC shows an "unable to pause vehicle" toast even though the aircraft enters hold, the likely cause is mode-reporting semantics: with GCSNAV still active, INAV may continue reporting the ArduPilot-compatible GUIDED custom mode while holding the copied current-position target.
