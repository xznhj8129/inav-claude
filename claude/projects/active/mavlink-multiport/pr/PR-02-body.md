**Part 2/7 of the mavlink_multiport2 stack.**

**Why the STorM32 dialect?** It carries the mLRS-specific MAVLink messages
(`MLRS_RADIO_LINK_STATS`, `MLRS_RADIO_LINK_INFORMATION`, `MLRS_RADIO_LINK_FLOW_CONTROL`),
which OlliW defined under the STorM32 dialect, enabling experimental mLRS support in the
next PR. STorM32 is a superset dialect: it includes the full ArduPilot (ardupilotmega) and
common message sets, so every message INAV already used remains available.

172 of the changed files are **generated** — do not review them. The reviewable surface is:

- `lib/main/MAVLink/generate.sh` / `generate.bat`: generate the `storm32.xml` dialect that INAV actually includes (337-message STorM32/ArduPilot/common set) instead of the catch-all dialect, and clean stale dialect directories before regeneration.
- `src/main/rx/mavlink.h`: switch the MAVLink include to `storm32/mavlink.h`. The regenerated library moves the merged `MAV_CMD` enum out of `common/common.h` into `storm32/storm32.h`, and MAVLink's include guard means the first include wins — this header is that first include for every TU.
- `src/main/telemetry/mavlink.c`: drop the local `APM_PLANE_MODE`/`APM_COPTER_MODE` enum copies; the generated ArduPilot dialect provides `PLANE_MODE`/`COPTER_MODE`.

Provides the mLRS radio-link messages used by the next PR. Verified: full SITL build, warnings-as-errors, clean at this commit.
