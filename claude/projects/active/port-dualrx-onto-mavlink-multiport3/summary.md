# Project: Port dualrx feature onto mavlink_multiport3

**Status:** 📋 TODO
**Priority:** MEDIUM
**Type:** Feature (port/refresh of stale experimental branch)
**Created:** 2026-07-24
**Estimated Effort:** 4-8 hours

## Overview

Refresh and port the experimental **Dual RX fallback** feature (primary/secondary
receiver with automatic failover) from a stale 3-commit branch onto the current
`mavlink_multiport3` integration base, get it building and passing its unit test,
and resolve the drift that has accumulated since it was branched.

## Problem

The feature was implemented on `codex-inav` and left approximately complete, but:
- It was never turned into a PR.
- It branched from a very old base and has drifted badly out of date.

The user wants it brought back to life on top of the current work.

## Feature (what dualrx does)

- Two receivers, **Primary** and **Secondary**, of any (non-MSP) type. Both stay
  active for telemetry; only one has RC control at a time.
- On primary-link failsafe, control passes to the secondary; **main failsafe only
  fires when both links are down**.
- Gated by CLI `dual_rx_enabled` (default OFF); auto-disabled if either link is MSP RX.
- New serial function `FUNCTION_RX_SERIAL_SECONDARY` reuses the unused
  `FUNCTION_UNUSED_1` bit (1 << 13 = 8192, former UAV_INTERCONNECT) so identical
  protocols can bind to distinct UARTs.
- New secondary `PG_RX_CONFIG` fields (`receiver_type_secondary`,
  `serialrx_provider_secondary`, `serialrx_inverted_secondary`,
  `serialrx_halfduplex_secondary`, `sbus_sync_interval_secondary`).
- `rxLink_e` runtime abstraction + APIs (`rxGetActiveLink`, `rxSetActiveLink`,
  `rxIsLinkReceivingSignal`, `rxIsPrimaryFailsafe`); per-link runtime state each cycle.
- OSD: new `OSD_ACTIVE_RX_LINK` element (`RX:P` / `RX:S`, blinks on secondary/no-link)
  and a "PRI RX FS" warning.
- Tests: `rx_rx_unittest` rewritten for the dual-link API (primary→secondary failover,
  secondary-active start, main-failsafe only when both down).

## Base branch reality — NOT a fast-forward

The user's hoped-for "pull dualrx and fast-forward" path does **not** apply:

- `origin/dualrx` (remote `origin` = git@github.com:xznhj8129/inav.git) is only
  **3 commits**: `373e73b7 first test` → `10b799c0 test 2` → `95d968c8 dual rx testable state`.
- Its merge-base with `mavlink_multiport3` is `27479930d` (PR #11042) — about
  **948 commits behind** the current base.
- `mavlink_multiport3` is the canonical "latest everything" integration branch
  (mav/07-tunnel + reconnect-refine #11731 + scheduler fix #11738), regenerable via
  `claude/developer/scripts/build/regen-mavlink_multiport3.sh`. It heavily reworked
  the MAVLink stack (split into `src/main/mavlink/`).

So this is a **re-port / rebase of the dualrx changes onto `mavlink_multiport3`**,
resolving conflicts — not a merge/fast-forward.

## Inputs / artifacts

Feature workspace (external, reference only): `inav_development/mydev/branch/dualrx/` — diverged from this silo, see `MANIFEST.md`
- `changes.diff` — full firmware diff (43 files, ~6000 lines; dated 2026-07-24 — verify what base it is against before trusting).
- `configurator.patch` — companion inav-configurator changes.
- `dual_rx_pr.md` — drafted PR description.
- `dualrx` — original feature/implementation plan.
- `DualRX.md` — design doc (symlink into Obsidian vault).

Also available directly: `origin/dualrx` in the `inav/` checkout.

## Expected conflict hotspots (drift)

- `src/main/rx/rx.c`, `src/main/rx/rx.h` — core runtime; touched by both sides.
- `src/main/rx/mavlink.c` / `mavlink.h` — multiport3 reworked MAVLink RX substantially.
- `src/main/fc/settings.yaml` — new PG_RX_CONFIG fields vs. multiport3 additions.
- `src/main/io/serial.h` — `FUNCTION_RX_SERIAL_SECONDARY` bit.
  ✅ Verified 2026-07-24: `FUNCTION_UNUSED_1 = (1 << 13)` is still free on `mavlink_multiport3`.
- All serial RX drivers (crsf/fport/fport2/ghst/ibus/jetiexbus/sbus/spektrum/srxl2/sumd)
  gained a port-function argument — re-apply against current driver signatures.
- Regenerated docs (`docs/Settings.md`, MSP enums/json) — regenerate, don't hand-merge.

## Solution (suggested approach)

1. Branch `feature/dualrx` from `mavlink_multiport3`.
2. Re-apply the dualrx changes (cherry-pick the 3 commits or apply `changes.diff`),
   resolving conflicts in the hotspots above.
3. Regenerate settings/docs/MSP artifacts rather than hand-merging them.
4. Build SITL warnings-as-errors; build one representative hardware target for flash/RAM.
5. Get `rx_rx_unittest` (RxDualLinkTest) green.

## Success Criteria

- [ ] `feature/dualrx` branch exists on top of `mavlink_multiport3`, conflicts resolved.
- [ ] SITL builds clean (warnings-as-errors).
- [ ] `rx_rx_unittest` passes (primary→secondary failover, secondary-active start, main-failsafe both-down).
- [ ] One hardware target builds and fits (flash/RAM reported).
- [ ] Generated docs/settings/MSP artifacts regenerated and consistent.
- [ ] `dual_rx_pr.md` finalized as a ready-to-send PR draft (diff re-read from new base).
- [ ] Configurator companion (`configurator.patch`) ported and building.
- [ ] Branch ready to push; **no PR opened** (user sends manually).

## Scope (decisions confirmed by user 2026-07-24)

**In scope:**
- Firmware port + drift fixes + unit test green + build verification.
- **Configurator companion** — port `configurator.patch` in the same effort.
- **PR draft, branch ready** — finalize `dual_rx_pr.md` as a ready-to-send PR draft and
  leave the branch ready to push. **Do NOT open a PR** — the user sends it manually.

**Out of scope:** actually opening/pushing a PR (user does this). Hardware/flight testing
of the failover behavior.

## Related

- **Branch base:** `mavlink_multiport3` (local + `origin/mavlink_multiport3`)
- **Source branch:** `origin/dualrx` (tip `95d968c8`)
- **Repository:** inav (fork `origin` = xznhj8129/inav)
- **Memory:** see mavlink-multiport2-branch / mavlink-multiport2-design-decisions
