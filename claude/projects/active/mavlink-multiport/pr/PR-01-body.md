**Part 1/7 of the mavlink_multiport2 stack.**

Three self-contained SITL/simulator fixes, independent of any MAVLink feature work. First PR in a stack splitting the `mavlink_multiport2` branch (see stack overview in the final PR).

## Enable MAVLink RX in SITL

On current `maintenance-10.x` these defines are inherited unconditionally from `target/common.h`, so this commit is a no-op today. It exists for part 3/7 of this series (#11714), which moves `USE_TELEMETRY_MAVLINK` / `USE_SERIALRX_MAVLINK` behind the `MCU_FLASH_SIZE > 512` block to recover flash on small targets. `target/common.h` is evaluated before `target/SITL/target.h`, and SITL sets `TARGET_FLASH_SIZE` rather than `MCU_FLASH_SIZE` — so from part 3 onward, SITL silently loses MAVLink serial RX without explicit defines. The failure mode (observed live on the development branch): `serialrx_provider = MAVLINK` stays visible in settings metadata, but `serialRxInit()` has no compiled `SERIALRX_MAVLINK` case, so on reboot `rxInit()` treats `receiver_type = SERIAL` as failed receiver init and silently rewrites it to `NONE`. Defining both in the SITL target keeps its MAVLink support explicit and independent of `common.h` ordering.

## Fix SITL system load accounting

`averageSystemLoadPercent` is based on waiting-task samples from a tight scheduler loop. SITL deliberately sleeps between due tasks to avoid pegging a host core, so most samples occurred when work was already due — the metric sat at/above 100 and armed with false `SYSTEM OVERLOADED` blocks during simulator and Configurator testing. SITL now reports scheduler busy time over elapsed wall time, excluding the intentional host sleep. Hardware builds keep the existing metric (change is `SITL_BUILD`-gated).

## Fix X-Plane SITL altitude inputs

Two bad sensor feeds caused slow altitude loss in fixed-wing POSHOLD/loiter:
- X-Plane passed zero GPS NED velocity while `gpsFakeSet()` marks vertical velocity valid, so the position estimator accepted `velNED[Z] = 0` instead of deriving climb/sink.
- Fake barometer pressure came from `sim/weather/barometer_current_inhg` (the weather/altimeter setting), not aircraft altitude.

Now passes X-Plane local velocity as NED (`N = -local_vz`, `E = local_vx`, `D = -local_vy`) and derives fake baro pressure from aircraft elevation via `altitudeToPressure()`, matching the RealFlight SITL pattern.

## Testing

- Full SITL build with `WARNINGS_AS_ERRORS=ON`: clean.
- Live X-Plane SITL sessions (fixed-wing): altitude hold no longer sinks in loiter; `SYSTEM OVERLOADED` arming block no longer appears.
- No hardware-target impact: all changes are SITL/simulator-gated.
