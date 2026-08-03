# MAVLink multiport changes

> Shipped upstream as a 7-part PR stack: iNavFlight/inav #11712-#11718 (2026-07-17).

## Betaflight parity follow-up

- Mission transfers now retain the initiating system, component, and ingress port. Upload requests retry every 1.5 seconds, abort after five retries, reject competing senders and invalid sequences, and persist accepted missions. Downloads require a request-list transaction, accept one-item retransmission, finish on `MISSION_ACK`, and expire after five seconds of inactivity.
- Mission clears now remove both runtime and nonvolatile waypoints. `MISSION_CURRENT` reports mission count, current item, execution mode, and state at 1 Hz; downloaded items identify the active item.
- Broadcast `PING` and local/broadcast `TIMESYNC` requests now receive protocol-correct replies.
- `MAV_CMD_REQUEST_MESSAGE` supports `MESSAGE_INTERVAL`. The MAVLink Standard Modes microservice (`AVAILABLE_MODES`, `AVAILABLE_MODES_MONITOR`, and `CURRENT_MODE`) is build-time optional behind `USE_MAVLINK_STANDARD_MODES` and is off by default for ArduPilot-style mode emulation.
- `COMMAND_LONG` float parameters are checked before integer conversion, including message IDs, frames, coordinates, altitudes, and headings.
- MAVLink RX work is capped per scheduler invocation and periodic stream deadlines are phased to avoid startup bursts.
- UBlox ellipsoid altitude, speed accuracy, and heading accuracy are retained in the GPS solution and emitted in `GPS_RAW_INT` when valid.
- Changed arming-disable reasons are broadcast as `STATUSTEXT` once an active MAVLink port is available.
- MAVLink `STATUSTEXT` now broadcasts INAV-specific notice messages when the selected INAV flight mode changes, including explicit enter/exit notices for GCS NAV mode.
- OSD-derived `STATUSTEXT` is now de-spammed per MAVLink port. Changed text is sent immediately, but unchanged notices repeat only after 30 seconds, warnings after 10 seconds, and critical messages after 5 seconds.
- SITL now explicitly builds MAVLink telemetry and MAVLink serial RX support, so `receiver_type = SERIAL` with `serialrx_provider = MAVLINK` is retained instead of being normalized back to `NONE`.
- SITL system load now excludes the intentional host sleep used by the simulator loop, preventing false `SYSTEM OVERLOADED` arming blocks during simulator and Configurator testing.
- X-Plane SITL now keeps sending INAV motor output to X-Plane throttle when the INAV-XITL plugin is detected. *(NOT carried into the upstream PR stack — suspected band-aid over a wrong `--chanmap`; commit `23465a0f0` if it needs reviving.)*
- X-Plane SITL pitch and yaw output signs are corrected so autopilot/stabilized corrections move the aircraft in the correct direction. *(NOT carried into the upstream PR stack — same chanmap suspicion; commit `d985111eb`.)*
- X-Plane SITL now feeds GPS NED velocity and fake barometer pressure from aircraft motion/elevation instead of zero vertical velocity and weather altimeter pressure, improving fixed-wing altitude hold/loiter behavior.
- MAVLink mission upload now tolerates QGC-style unused/NaN parameters on waypoint items, skips QGC planned-home item 0 instead of storing it as mission waypoint 1, stages translated INAV waypoints before committing them, and applies MAVLink mission modifier items such as delay, altitude, and speed changes to the appropriate INAV waypoint instead of blindly consuming waypoint slots.
- MAVLink mission transfers now recover from out-of-order upload/download requests where the protocol allows it, honor explicit upload cancellation, and respond to legacy `MISSION_REQUEST` downloads with `MISSION_ITEM_INT`.
- MAVLink mission upload, clear-all, and zero-count clear preserve the previous INAV mission in RAM if nonvolatile mission persistence fails.
- MAVLink mission documentation now warns that translation to INAV's MSP waypoint model is lossy and that MAVLink mission downloads are best-effort reconstruction, not a reliable canonical source for mission backups or full-fidelity editing.
- The OSD flight-mode element now shows `GCSN` when GCS-assisted navigation is actually active.

- `lib/main/MAVLink/generate.sh`/`generate.bat` now generate the STorM32 dialect (`storm32.xml`) that INAV actually includes, and the headers were regenerated: the build surface is the 337-message STorM32/ArduPilot/common set instead of the 391-message `all` set. The merged `MAV_CMD` enum moved from `common/common.h` to `storm32/storm32.h`, so the first MAVLink include (`rx/mavlink.h`) points at the storm32 dialect.

The mission transfer design is adapted from Betaflight's GPLv3 `mavlink_mission.c` at commit `87d4bd63` and reshaped for INAV's routed multiport runtime.

## Command-control parity

- `MAV_CMD_COMPONENT_ARM_DISARM` and `MSP2_INAV_ARM_DISARM` use the normal INAV arming/disarming path and succeed only when the requested state is reached.
- `MAV_CMD_NAV_RETURN_TO_LAUNCH`, `MSP2_INAV_ACTIVATE_RTH`, and Programming Framework operation `61` enter the normal INAV RTH mode path by adding a temporary `BOXNAVRTH` source to the RC mode selector instead of setting the failsafe/geozone forced-RTH latch. A later pilot RC flight-mode change or disarm clears the temporary source.
- `MAV_CMD_DO_SET_MODE` accepts the ArduPilot-style RTL/RTH custom-mode request as an alias for the same normal RTH mode path. It also accepts ArduPilot Loiter/PosHold pause modes and enters normal INAV PosHold at the current position and altitude. Other GCS mode changes remain unsupported.
- `MAV_CMD_NAV_LAND`, `MSP2_INAV_ACTIVATE_LANDING`, and Programming Framework operation `62` perform a normal waypoint-style landing at the current position. This is not emergency landing.
- Direct LAND uses a transient waypoint without modifying the uploaded mission. Mission LAND items continue to retain their supplied landing coordinates.
- `MAV_CMD_DO_SET_HOME` uses the existing waypoint `0` backend. It accepts an explicit global location or `param1 = 1` for the current GNSS position and retains the native waypoint `0` safety gates.
- MSP set-home remains the existing `MSP_SET_WP` waypoint `0` operation; no duplicate MSP command was introduced.
- `MSP2_INAV_TIMESYNC` returns the same monotonic nanosecond boot-time clock used by MAVLink `TIMESYNC`.
- `MAV_CMD_DO_REPOSITION.param3` and appended `MSP2_INAV_SET_GLOBAL_TARGET.loiterRadius` can temporarily override fixed-wing PosHold loiter radius. The override is volatile, clears on disarm/reboot, and `0` returns to configured `nav_fw_loiter_radius`.
- `MAV_CMD_NAV_TAKEOFF` now has an explicit `UNSUPPORTED` stub without introducing takeoff behavior.

The matching `mspapi2:mavlink_multiport2` branch includes synchronized message metadata and helpers for arm/disarm, RTH, landing, and timesync.
