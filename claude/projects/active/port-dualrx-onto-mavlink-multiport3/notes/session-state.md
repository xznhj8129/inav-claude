# Port dualrx onto mavlink_multiport3 — session state

Branch: `feature/dualrx` off `mavlink_multiport3` (inav repo). Lock held: inav.lock.

## Approach
- Source of truth = git range `merge-base(origin/dualrx, mavlink_multiport3)..origin/dualrx`,
  SOURCE files only (the 3 dualrx WIP commits also committed+deleted the whole
  `cmake/build_SITL/` tree — never cherry-pick them raw).
- Applied `dualrx-source.diff` with `git apply --3way`; regenerate docs/MSP/settings rather than merge.

## Conflicts resolved (7 files)
- `logic_condition.h`: `RX_SELECT_OVERRIDE` renumbered 57→**63** (57–62 taken on new base); global flag `OVERRIDE_RX_LINK = 1<<13` applied clean.
- `logic_condition.c`: kept ours' SET_ALTITUDE_TARGET/ACTIVATE_RTH/ACTIVATE_LANDING cases + added RX_SELECT_OVERRIDE case.
- `osd.h`: appended `OSD_ACTIVE_RX_LINK` after `OSD_GPS_EXTRA_STATS` (preserves existing indices).
- `osd.c`: reverted + re-applied 2 hunks by hand (OSD_ACTIVE_RX_LINK draw case; item_pos default). **Drift:** warnings machinery moved osd.c→`fc/multifunction.c`.
- `fc/multifunction.c` (NOT in original diff — drift target): added `#include "rx/rx.h"`, `messages[8]→[9]`, PRI RX FS warning. **Widened `osdWarningsFlags`/`warningFlagID`/`newWarningFlags` uint8_t→uint16_t** — 9th warning bit (256) overflows uint8_t otherwise.
- `fc/multifunction.h`: `osdWarningsFlags` uint8_t→uint16_t.
- `rx.h`: kept ours' rxMspAuxOverlaySet + theirs' link APIs.
- `rx.c`: kept ours' MSP aux overlay block; adopted theirs' dual-link failsafe condition.
- test `CMakeLists.txt`: discarded dualrx's old-base infra rewrite; kept ours + added rx_rx_unittest depends block only (auto-discovered via GLOB).

## Status (verified)
- Firmware committed **a245eadd0** on `feature/dualrx` (off mavlink_multiport3).
- SITL builds -Werror clean. rx_rx_unittest 3/3 green. HW SPEEDYBEEF405WING FLASH 72.67% / RAM 93.01%.
- Docs regenerated (Settings.md, MSP README.md/inav_enums*).
- Configurator committed **2daaffe7** on `feature/dualrx` (off mavlink_multiport2, user-confirmed base).
  - Fixed cross-repo: logic op "Select RX link" 57→**63**; removed duplicate id 56; RX_SERIAL_SECONDARY bit 13; MSP activeRX; i18n keys OK.
  - Stashed pre-existing ipf_trig yarn.lock deletion (restore for its owner later).
- rx_rx_unittest drift fixes: added `extra_includes ../../lib/main/MAVLink`; added driver-init + logicConditionValuesByType stubs; fixed latent uint32→uint64 stub type on logicConditionsGlobalFlags.
- dual_rx_pr.md finalized (workspace + artifacts dir).

## Done
- Review findings addressed; CRSF+SBUS made instance-safe; guard driver-group aware.
- Firmware tip `c88d5a248`, configurator tip `2daaffe7`, both pushed. No PRs opened.
- Both PR drafts written; completion report sent; locks released.

## Next
See **next-steps.md** — design decisions from the 2026-07-24 review discussion.
**P1 = MSP-over-CRSF replies go out the primary port regardless of ingress link
(bug I introduced in `a97c7fb81`). Fix first.**
