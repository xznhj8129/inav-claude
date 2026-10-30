# JS (Configurator) vs C (Firmware) Output-Mapping Comparison — Findings

**Date:** 2026-08-28
**Context:** PR #11787 firmware fix (pwmEnsureEnoughtMotors pass 1) + requirement
that the Configurator's JavaScript implementation match the firmware's C.

## How the data flows

1. Firmware boots: `pwmBuildTimerOutputList()` (+ `pwmEnsureEnoughtMotors()`)
   MUTATES the global `timerHardware[].usageFlags` — claims sync every pad on
   a timer to one role, pass 2 promotes/demotes AUTO pads.
2. Configurator queries `MSP2_INAV_OUTPUT_MAPPING_EXT2` (0x210D) → receives
   those **post-resolution** flags (single-bit per pad, per-timer consistent),
   plus `MSP2_INAV_TIMER_OUTPUT_MODE` (0x200E) → the timer overrides.
3. `outputMapping.js` `getTimerMap()` re-derives the Mixer-tab table from the
   post-resolution flags + current mixer motor/servo counts.

## Method

- C reference: `simulate_pwm_roles.py` (faithful model of the fixed C
  algorithm), driven-semantics (only pads actually driven get labels).
- JS reference: the REAL `inav-configurator/js/outputMapping.js`, bundled with
  the configurator's esbuild and driven in Node with the post-resolution flags
  the C model produces.
- Harness: `claude/agents/target-developer/scripts/compare-js-c/`
  (`compare_js_c.py` + `drive.mjs`); run `python3 compare_js_c.py` from the repo root.

## Results

- All synthetic cases (all-motor-only group, mixed group, motor+servo same
  timer — the PR #11787 regression shapes): **JS matches C** after the pass-1
  fix, for the current-boot display. ✓
- Real targets (MATEKF405, AOCODARCF722AIO, FOXEERF405V2, SPRACINGF7DUAL):
  motor/servo labels match; LED cells do NOT.

## Divergences found

1. **LED bug (real, fixable in JS)** — `getTimerMap()`:
   `if (servosToGo > 0 && bit_check(flags, TIM_USE_LED))`.
   LED is gated on the SERVO budget: with no servos configured (typical MR),
   servosToGo == 0 → every LED pad renders "-" instead of "Led". Firmware
   drives LED via its own path (light_ws2811strip.c), independent of the
   servo budget. Affects AOCODARCF722AIO, FOXEERF405V2, SPRACINGF7DUAL, ...
   Fix: drop the `servosToGo > 0` gate.

2. **Conflicted pads mis-previewed (data-limited)** — pads the firmware skips
   (ADC-pin conflict, UART pin, LED-timer conflict) keep their declared flags
   in the MSP response, and the JS has no conflict info, so the preview can
   show e.g. FOXEERF405V2 output 4 as "Servo S3" while the firmware never
   drives it. Not fixable from current MSP data — this is exactly what the
   10.x firmware-authoritative API removes.

3. **Algorithm is not a C mirror (masked today)** — `getTimerMap()` is a
   per-pad greedy with no per-timer single-role enforcement, no claim-sync,
   no pass-1/pass-2 counting, no override-aware priority. Post-resolution
   flags are per-timer pre-unified, so the current-boot display happens to be
   right — but the per-timer rule ("a timer used for motors can't drive
   servos") is not implemented in the JS, and count/override changes can't be
   predicted (the preview can't re-run the C pipeline without raw flags).
   The reverted two-pass PR (#2596) added override priority; the 10.x
   MSP2_INAV_OUTPUT_ASSIGNMENT/QUERY_OUTPUT_ASSIGNMENT (0x210E/0x210F) API —
   already merged on maintenance-10.x per the May 2026 plan — eliminates the
   duplication entirely by making the firmware answer.

## Options discussed

- (a) Align the JS greedy to the C rules now (fix LED bug, enforce
      per-timer single-role, motor-first ordering) on the current branch.
- (b) Backport the 10.x output-assignment MSP API to release/9.1 + configurator
      master (firmware-authoritative; removes duplication for good).
- (c) Minimal: LED bug only.
