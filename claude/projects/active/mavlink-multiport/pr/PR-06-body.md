**Part 6/7 of the mavlink_multiport2 stack.**

Command-control parity between MAVLink, MSP, and the Programming Framework, so GCS and companion software can arm, navigate, and land through standard commands.

## Arming
- `MAV_CMD_COMPONENT_ARM_DISARM` and `MSP2_INAV_ARM_DISARM` (0x2227) go through the normal INAV arming/disarming path and ACK success only when the requested state is actually reached.

## RTH
- `MAV_CMD_NAV_RETURN_TO_LAUNCH`, the ArduPilot-style `MAV_CMD_DO_SET_MODE` RTL request, `MSP2_INAV_ACTIVATE_RTH` (0x2225), and Programming Framework operation 61 all enter the **normal INAV RTH mode path** via `activateRTHMode()`, which adds a temporary `BOXNAVRTH` source to the RC mode selector. This deliberately does **not** use the failsafe/geozone forced-RTH latch — live testing showed `activateForcedRTH()` is not equivalent to switching into RTH mode. The temporary source clears on a pilot RC flight-mode change or disarm, so a command-triggered RTH cannot survive into a later arming attempt.

## Pause / position hold
- `MAV_CMD_DO_SET_MODE` also accepts ArduPilot pause-style modes (`PLANE_MODE_LOITER`, `COPTER_MODE_LOITER`, `COPTER_MODE_POSHOLD`, `COPTER_MODE_BRAKE`) and enters normal INAV PosHold at the current position/altitude/heading via a temporary `BOXNAVPOSHOLD` source (this is what QGC's Pause button sends). Other GCS mode changes remain `UNSUPPORTED`.

## Landing
- `MAV_CMD_NAV_LAND`, `MSP2_INAV_ACTIVATE_LANDING` (0x2224), and PF operation 62 perform a normal waypoint-style landing at the current position through a **transient** waypoint — the uploaded mission is not modified, and this is not emergency landing. Mission LAND items keep their supplied coordinates; direct LAND commands ignore coordinate fields.

## Home, time, guided
- `MAV_CMD_DO_SET_HOME` uses the existing waypoint-0 backend (`param1 = 1` = current GNSS position; explicit global location otherwise) and retains all native WP#0 safety gates. MSP set-home remains `MSP_SET_WP` waypoint 0 — no duplicate command added.
- `MSP2_INAV_TIMESYNC` (0x2228) returns the same monotonic nanosecond boot clock as MAVLink `TIMESYNC`.
- `SET_POSITION_TARGET_GLOBAL_INT` / `_LOCAL_NED` guided handling (waypoint 255 / altitude-only requests, gated on valid GCS navigation).
- `MAV_CMD_CONDITION_YAW` heading changes while the nav state has yaw control.
- Temporary fixed-wing PosHold loiter-radius override: `MAV_CMD_DO_REPOSITION.param3` in meters, or `int32 loiterRadius` (cm) appended to `MSP2_INAV_SET_GLOBAL_TARGET` (17-byte payload; 13-byte payload = no change; 0 clears). `MSP2_INAV_NAV_TARGET` reports the active override. Volatile: cleared on disarm/reboot, applied only while the nav FSM is in PosHold so RTH/mission/autoland loiter keeps configured defaults.
- Explicit `MAV_CMD_NAV_TAKEOFF` stub returning `UNSUPPORTED` (foundation for later takeoff work, no behavior introduced).
- OSD flight-mode element shows `GCSN` while GCS-assisted navigation is actually active.

All float command parameters are validated (finite/range) before integer conversion.

Companion PR: `mspapi2:mavlink_multiport2` (synchronized message metadata + arm/RTH/land/timesync helpers).

## Testing
- Unit slice: 81/81 passing (`mavlink_unittest`).
- Full SITL build, warnings-as-errors, clean. MSP dev docs regenerated.
- X-Plane + QGC SITl test successful
