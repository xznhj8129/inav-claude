# Dual RX: primary/secondary receivers with automatic failover

**WIP, requires more elaboration on switchover states, hysteresis and dwell time, receiver configurations and telemetry**

## Summary

Adds a second receiver that runs alongside the primary. Both links stay active for
telemetry, but only one drives RC control at a time. When the primary link enters
failsafe, control passes to the secondary; the main failsafe only triggers when
**both** links are down.

- Gated by `dual_rx_enabled` (default OFF); auto-disabled if either link is an MSP RX
  (MSP RC can arrive on any MSP port, so a dedicated secondary link makes no sense there).
- A second identical serial protocol can bind to its own UART via the new
  `FUNCTION_RX_SERIAL_SECONDARY` serial function.
- OSD gains an active-link indicator and a "primary in failsafe" warning.
- Unit tests cover primary→secondary failover, secondary-active startup, and
  main-failsafe-only-when-both-down.
- Based on the last stage of Mavlink_multiport branch

## Configuration / CLI

New gate and secondary receiver settings in `PG_RX_CONFIG`:

- `dual_rx_enabled` — bool, default OFF.
- `receiver_type_secondary` — default NONE.
- `serialrx_provider_secondary` — default per target.
- `serialrx_inverted_secondary` — default OFF.
- `serialrx_halfduplex_secondary` — default AUTO.
- `sbus_sync_interval_secondary` — default 3000 µs (range 500–10000).

Serial function masks (assigned with `serial <idx> <mask> ...`, additive when a port is shared):

- Primary: `FUNCTION_RX_SERIAL` (64)
- Secondary: `FUNCTION_RX_SERIAL_SECONDARY` (8192 = `1 << 13`, reusing the previously
  unused serial-function bit)

## Runtime / selection / failsafe

- `rxLink_e` abstraction with per-link runtime state (channels, link quality, stats,
  timing) maintained every cycle for both PRIMARY and SECONDARY, plus the APIs
  `rxGetActiveLink`, `rxSetActiveLink`, `rxIsLinkReceivingSignal`, `rxIsPrimaryFailsafe`.
- Selection: primary while it has a valid signal, else secondary; if neither is valid,
  primary stays selected but marked invalid. Main failsafe fires only when both links
  are down.
- Serial RX drivers take a port-function argument so they bind to the primary or
  secondary UART; CRSF writes link statistics through the per-link runtime pointer.
- `LOGIC_CONDITION_RX_SELECT_OVERRIDE` (operation 63) lets the programming framework
  force the active link (PRIMARY/SECONDARY) via the `OVERRIDE_RX_LINK` global flag.

## OSD / UI

- New `OSD_ACTIVE_RX_LINK` element (default position (3,5), CMS-exposed) showing `RX:1`
  or `RX:2`; blinks when running on the secondary link or when no link is valid.
- New multifunction warning "PRI RX FS" shown when the primary is in failsafe while the
  secondary still has signal. The multifunction warning bitfield was widened from 8 to
  16 bits to accommodate the added warning.

## MSP

- `MSP2_INAV_MISC` reply appends a trailing `activeRX` byte (`rxLink_e`) reporting the
  current active link; older clients that stop reading before it are unaffected.

## Known limitations

- **Two identical receivers work for CRSF and SBUS only (for now).** Those two drivers hold
  per-link parser/channel state, so a primary and secondary receiver of the same type run
  independently. The remaining serial drivers (Spektrum, SUMD, IBUS, JETI, FPORT/FPORT2,
  SRXL2, GHST) still keep parser state in shared module storage, so running the *same* one
  of those on both links would corrupt both. `rxInit()` therefore refuses dual RX only when
  both links are `SERIAL` with the same, not-yet-instance-safe `serialrx_provider` (it falls
  back to single-RX), mirroring the existing MSP guard. Two *different* providers always run
  independently. Making the remaining drivers instance-safe (same pattern as CRSF/SBUS) is a
  follow-up.
- **No fail-back hysteresis.** Selection returns to the primary as soon as it regains a
  valid signal, with no dwell time or blending across the switch. A marginal primary link
  can cause the active link to flap frame-to-frame; a hold-off timer is a sensible future
  refinement.
- `PG_RX_CONFIG` version bumped (13 → 14) because the new secondary fields change the
  stored `rxConfig_t` layout — RX config resets to defaults on upgrade.

## Docs

- `docs/Settings.md` and the MSP enum/message docs (`docs/development/msp/`) regenerated.

## Configurator companion

The INAV Configurator companion lives on `feature/dualrx` (based on `mavlink_multiport2`)
and adds the secondary-receiver UI, the RX_SERIAL_SECONDARY port function, the
`activeRX` MSP read, and the "Select RX link" programming operator (id 63).

## Tests / verification

- `rx_rx_unittest` (RxDualLinkTest) rewritten for the dual-link API — **3/3 pass**.
- SITL builds clean with warnings-as-errors.
- Hardware sanity: SPEEDYBEEF405WING builds and fits (FLASH 72.67%, RAM 93.01%).
- Full test pending

Build/run the unit test:

```
cmake -S . -B build_unit -DTOOLCHAIN=
cmake --build build_unit --target rx_rx_unittest
./build_unit/src/test/unit/rx_rx_unittest
```
