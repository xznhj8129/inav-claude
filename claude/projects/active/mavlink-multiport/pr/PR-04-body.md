**Part 4/7 of the mavlink_multiport2 stack.**

Adds the protocol-service layer on the multi-port MAVLink core:

- **Protocol replies:** PING and TIMESYNC (monotonic nanosecond boot clock).
- **Stream/interval control:** `REQUEST_DATA_STREAM`, per-message `SET_MESSAGE_INTERVAL`/`GET_MESSAGE_INTERVAL` layered over the legacy stream-rate model, `MAV_CMD_REQUEST_MESSAGE` (incl. MESSAGE_INTERVAL query), `REQUEST_PROTOCOL_VERSION`, `REQUEST_AUTOPILOT_CAPABILITIES`, `GET_HOME_POSITION`.
- **GPS accuracy:** UBlox ellipsoid altitude, speed/heading accuracy retained in the GPS solution and emitted in `GPS_RAW_INT` when valid.
- **STATUSTEXT:** changed arming-disable reasons broadcast once a port is active; INAV flight-mode change notices (`Notice: INAV: Entering <mode>`, GCS NAV enter/exit); OSD system messages de-spammed per port (changed text immediately; unchanged notices repeat after 30 s, warnings 10 s, critical 5 s) instead of resending every EXTRA3 tick.
- The MAVLink Standard Modes microservice remains build-time optional behind `USE_MAVLINK_STANDARD_MODES`, off by default.

Verified: SITL warnings-as-errors clean; `mavlink_unittest` slice 38/38.
