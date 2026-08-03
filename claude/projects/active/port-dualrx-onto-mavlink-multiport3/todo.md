# Todo: Port dualrx onto mavlink_multiport3

## Phase 1: Set up base and survey drift

- [x] Branch `feature/dualrx` from `mavlink_multiport3`
- [x] Confirm base: used git range merge-base(origin/dualrx,mm3)..origin/dualrx, SOURCE files only (the 3 WIP commits also commit+delete the whole build tree — never cherry-pick raw)
- [x] Range-diff `origin/dualrx` (3 commits) vs. current base to map conflicts
- [x] Confirm `FUNCTION_UNUSED_1` (bit 13) still free — re-confirmed

## Phase 2: Re-apply the feature

- [x] Apply dualrx source diff via `git apply --3way`
- [x] Resolve `rx.c` / `rx.h` runtime conflicts (kept ours' MSP overlay + theirs' dual-link failsafe)
- [x] `rx/mavlink.c` / `mavlink.h` applied clean (portFunction arg, UNUSED)
- [x] Per-driver port-function arg applied clean across all serial RX drivers
- [x] Merge `settings.yaml` secondary PG_RX_CONFIG fields
- [x] Wire `FUNCTION_RX_SERIAL_SECONDARY` in `serial.h`
- [x] OSD element (osd.c/osd.h, cms_menu_osd.c) + warning — warning relocated to fc/multifunction.c (drift), widened warning bitfield uint8→uint16
- [x] logic_condition RX_SELECT_OVERRIDE renumbered 57→63 (drift)

## Phase 3: Regenerate + build

- [x] Regenerated `docs/Settings.md` + MSP docs (README.md/inav_enums*) via generators
- [x] SITL builds warnings-as-errors (clean)
- [x] Hardware: SPEEDYBEEF405WING builds, FLASH 72.67%, RAM 93.01%

## Phase 4: Configurator + verify

- [x] Ported configurator onto `mavlink_multiport2` (user-confirmed base); fixed logic op id 57→63 + removed dup id 56; JSON/JS/i18n verified
- [x] `rx_rx_unittest` (RxDualLinkTest) green — 3/3 (added MAVLink include + driver stubs; fixed latent uint32→uint64 stub bug)
- [x] Finalized `dual_rx_pr.md`

## Completion

- [x] firmware committed a245eadd0 (feature/dualrx), configurator committed 2daaffe7 (feature/dualrx)
- [ ] Code review findings addressed (review in progress)
- [ ] Branch ready to push; **no PR opened** (user sends manually)
- [ ] Send completion report to manager
