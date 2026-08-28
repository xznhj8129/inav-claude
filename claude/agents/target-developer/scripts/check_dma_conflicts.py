#!/usr/bin/env python3
"""
check_dma_conflicts.py -- flags STM32H7 DMA stream (`dmaopt`) collisions in a
target's timerHardware[] table.

BACKGROUND
==========
On STM32H7, `dmaopt` in DEF_TIM(tim, ch, pin, usage, flags, dmaopt) is a flat
0-15 index (0-7 = DMA1 Stream0-7, 8-15 = DMA2 Stream0-7 -- see
drivers/timer_def_stm32h7xx.h's DEF_TIM_DMA_FULL macro) selecting which
physical DMA stream that timer channel uses. Two DMA-consuming timer channels
sharing a dmaopt silently fight over the same stream: whichever inits last
wins, the other's feature (usually LED strip or a motor/servo channel) just
never works, with no compile-time or boot-time error.

ADC1/ADC2/ADC3 are a separate, non-obvious case: their DMA stream is
hardcoded in adc_stm32h7xx.c's static adcHardware[] table (ADC1 -> DMA2
Stream0 = dmaopt 8, ADC2 -> DMA2 Stream1 = dmaopt 9, ADC3 -> DMA2 Stream2 =
dmaopt 10) -- NOT read from target.h at all, so there is no ADCn_DMA_OPT
macro to check for. A target that assigns dmaopt 8/9/10 (matching whichever
ADC instance it uses) to a timer channel silently collides with the ADC.

Two confirmed real incidents of this exact bug class motivated this script:
AEDROXH7 (LED strip vs motor M1, both dmaopt=0 -- see
claude/manager/email/archive/2026-06-07-0600-completed-aedroxh7-led-dma-fix.md)
and DAKEFPVH743PRO (LED strip vs ADC1, both dmaopt=8 -- see
claude/projects/INDEX.md). Both were only caught by hardware testing, and in
AEDROXH7's case only because DSHOT happened to be active during that specific
test run -- an earlier test without DSHOT active passed clean. This script
catches the same bug class statically, without needing hardware or a specific
runtime condition to trigger it.

SCOPE
=====
Only STM32H7 targets are checked (detected via CMakeLists.txt's
target_stm32h7*(...) cmake function). The flat 0-15 dmaopt addressing this
script relies on is H7-specific -- F4/F7/AT32 targets instead pick from a
small, per-timer-channel-specific set of hardware-fixed DMA options, so the
same numeric dmaopt on two different timers does NOT necessarily mean the
same physical stream on those chips. Other targets are reported as skipped
(when checked individually via --target), not silently treated as clean.

DSHOT_DMAR exception: if a target defines USE_DSHOT_DMAR, multiple channels
of the *same* timer are allowed to legitimately share one dmaopt -- that is
burst mode's entire point (one shared stream feeds all of a timer's channels
via the TIM_UP request). Only a shared dmaopt across *different* timers, or a
timer vs ADC's hardwired stream, is flagged.

CONFIRMED CORRECT DESPITE A REAL BUG FOUND IN THE F4/F7/AT32 SIBLING SCRIPT
==============================================================================
simulate_pwm_roles.py's DMAR model had a real bug (fixed 2026-08-20, see
claude/projects/active/investigate-shared-tim-dma-request-lines/phase1-findings.md):
it applied F4's free-ride shortcut (a later channel of an already-locked timer
never checks its own dmavar -- timer_impl_stdperiph.c) universally to F7
targets too, even though F7's backend (timer_impl_hal.c, SHARED with H7) runs
the dmaGetByTag()/ownership check UNCONDITIONALLY for every channel. This
script's per-channel dmaopt model does NOT have that bug, confirmed two ways:
(1) H7 shares the same unconditional-gate backend as F7, so 'every channel's
own dmaopt is always genuinely consulted' -- which is exactly what this
script already assumes (it groups by each entry's literal, already-resolved
dmaopt value, with no dmavar-style indirection or free-ride step to get
wrong); and (2) empirically, every real H7 USE_DSHOT_DMAR target checked
assigns each channel of a burst timer a genuinely DISTINCT dmaopt (e.g.
AXISFLYINGH743PRO's TIM4 CH1-4 use dmaopt 9, 10, 11, 12 -- not a shared
value), matching the DMAMUX-per-channel-request reality confirmed directly in
timer_def_stm32h7xx.h (DEF_TIM_DMA__BTCH_TIM4_CH1/CH2/CH3 each reference a
distinct DMA_REQUEST_TIM4_CHn, unlike F4's genuinely-shared combined-request
table). The 'same timer + USE_DSHOT_DMAR -> always skip' branch just above is
consequently DEAD CODE on every current H7 target (verified: zero same-timer
duplicate-dmaopt groups exist in the current target tree) -- it rests on an
F4-style shared-request-line mental model that doesn't strictly match H7's
DMAMUX reality, so if a future H7 target ever DOES give two channels of one
timer an identical dmaopt, this branch's blanket suppression should be
revisited with the same per-channel-always-checked reasoning used above,
rather than trusted at face value.

The TIM4_CH4 has_dma_request() special-case above (NONE unless USE_DSHOT_DMAR
is defined) is the H7-family equivalent of simulate_pwm_roles.py's
SILENT_DEAD_MOTOR family split for F7/H7: since H7 never gives a free pass to
a NONE-resolving channel regardless of its position in a burst timer group,
this script is right to gate purely on 'does target.h define USE_DSHOT_DMAR',
with no free-rider-position exception needed (there isn't one on this
family).

SEVERITY: CERTAIN vs NOTICE
============================
LED strip and ADC are always active whenever their feature is enabled, so a
collision touching either is CERTAIN regardless of what else the target is
configured for. A motor/servo channel is different: pwm_output.c only ever
claims DMA for a channel once it's an actual configured DSHOT motor
(gated on getMotorCount()/isMotorProtocolDshot() at runtime) -- the servo
path never touches DMA at all -- so a same-dmaopt collision among pure
MOTOR/SERVO/OUTPUT_AUTO entries depends on which positions end up as live
motors. Every quad -- the minimum-viable build for any target -- needs its
first 4 motor/servo positions (array order: position 0 = M1, etc) to have
working DMA, so a collision with 2+ entries in those first 4 positions is
CERTAIN too. A collision confined to position 4+ (S5, S6, ...) isn't required
for a quad, but it's still a real gap worth fixing -- a well-built target
should offer DShot on every output it can -- so it's reported as NOTICE:
lower priority, not a false alarm.

Usage: ./check_dma_conflicts.py <inav_checkout_root> [options]
Example: ./check_dma_conflicts.py ~/Documents/planes/inavflight/inav --target DAKEFPVH743PRO

Options:
  --target NAME   only check this target directory name

Findings are a checklist to verify by hand, not a pass/fail gate -- see the
target-developer README's "Patterns" section for related pitfalls (e.g. why a
pin/dmaopt matching other targets does not itself prove correctness).
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

DEF_TIM_RE = re.compile(
    r'DEF_TIM\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*,'
    r'\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*(\d+)\s*\)'
)

# Usages that pwm_mapping.c treats as mutually-exclusive DMA-driven outputs
# (TIM_USE_OUTPUT_AUTO == TIM_USE_MOTOR | TIM_USE_SERVO). TIM_USE_ANY,
# TIM_USE_PWM, TIM_USE_PPM, and TIM_USE_BEEPER are not DMA-driven on H7.
DMA_USAGE_TOKENS = ("TIM_USE_MOTOR", "TIM_USE_SERVO", "TIM_USE_LED", "TIM_USE_OUTPUT_AUTO")

# (tim, ch) pairs with NO DMA request line at all on H7 -- see the NONE
# entries in timer_def_stm32h7xx.h's DEF_TIM_DMA__BTCH_* table. Whatever
# dmaopt number a target writes for one of these is inert; it can never
# collide with anything because no DMA stream is ever actually claimed.
# (TIM4, CH4) is the one conditional case: it's NONE only when
# USE_DSHOT_DMAR is *not* defined -- with DMAR it's repointed at the TIM4_UP
# burst request table and becomes real (see target.h's own USE_DSHOT_DMAR
# comment on AXISFLYINGH743PRO for why: TIM4_CH4 has no per-channel DMAMUX
# request of its own, so DMAR is the only way to give it a DMA path at all).
#
# NOTE: TIM16_CH1N is deliberately NOT in this set even though
# timer_def_stm32h7xx.h defines DEF_TIM_DMA__BTCH_TIM16_CH1N as NONE --
# that definition is dead code. timer_def.h's non-AT32F43x branch aliases
# BTCH_TIM16_CH1N to BTCH_TIM16_CH1 *before* the DEF_TIM_DMA__ prefix is
# concatenated on (DEF_TIM_TCH2BTCH's CONCAT expands the alias on rescan),
# so TIM16_CH1N actually resolves to TIM16_CH1's full DMA-capable table.
# Confirmed via gcc -E: DEF_TIM_DMAMAP(0, TIM16_CH1N) expands to a real
# DMA_REQUEST_TIM16_CH1 tag, not DMA_NONE. TIM17_CH1N has no such alias
# and genuinely expands to DMA_NONE -- it stays in this set.
NO_DMA_CHANNELS = {
    ("TIM12", "CH1"), ("TIM12", "CH2"),
    ("TIM13", "CH1"),
    ("TIM14", "CH1"),
    ("TIM15", "CH2"),
    ("TIM17", "CH1N"),
}

# ADC instance -> dmaopt its DMA stream is hardcoded to in adc_stm32h7xx.c
ADC_RESERVED_DMAOPT = {"ADC1": 8, "ADC2": 9, "ADC3": 10}

H7_CMAKE_RE = re.compile(r'target_stm32h7\w*\s*\(')
ADC_INSTANCE_RE = re.compile(r'^\s*#\s*define\s+ADC_INSTANCE\s+(ADC\d)', re.M)


def consumes_dma(usage: str) -> bool:
    return any(tok in usage for tok in DMA_USAGE_TOKENS)


# Usage tokens that occupy a motor/servo *output position* -- INAV assigns
# motor indices to these in target.c array order (position 0 = M1, etc).
# TIM_USE_LED is excluded: LED strip is a separate physical output, not one
# of the numbered motor/servo positions, so it never counts toward "the
# first four outputs."
MOTOR_POSITION_TOKENS = ("TIM_USE_MOTOR", "TIM_USE_SERVO", "TIM_USE_OUTPUT_AUTO")

# Every quadcopter -- the minimum-viable build for any target -- needs its
# first 4 motor/servo output positions to have working, non-colliding DMA.
# A collision confined to position 4+ only affects builds with more outputs
# actually configured as concurrent DSHOT motors than a quad needs, so it's
# a notice, not a hard failure.
MIN_GUARANTEED_MOTOR_POSITIONS = 4


def stream_label(dmaopt: int) -> str:
    return f"DMA1 Stream{dmaopt}" if dmaopt < 8 else f"DMA2 Stream{dmaopt - 8}"


def parse_timer_hardware(target_c_text: str):
    entries = []
    motor_position = 0
    for line in target_c_text.splitlines():
        if line.strip().startswith("//"):
            continue
        m = DEF_TIM_RE.search(line)
        if not m:
            continue
        tim, ch, pin, usage, _flags, dmaopt = m.groups()
        usage = usage.strip()
        position = None
        if any(tok in usage for tok in MOTOR_POSITION_TOKENS):
            position = motor_position
            motor_position += 1
        entries.append({
            "tim": tim, "ch": ch, "pin": pin, "usage": usage,
            "dmaopt": int(dmaopt), "line": line.strip(), "motor_position": position,
        })
    return entries


def check_target(target_dir: Path):
    """Returns (findings: list[str], skip_reason: str | None)."""
    cmake = target_dir / "CMakeLists.txt"
    target_c = target_dir / "target.c"
    target_h = target_dir / "target.h"
    if not cmake.is_file() or not target_c.is_file():
        return [], "missing CMakeLists.txt or target.c"

    cmake_text = cmake.read_text(errors="ignore")
    if not H7_CMAKE_RE.search(cmake_text):
        return [], "not an STM32H7 target (dmaopt collision check is H7-only)"

    target_h_text = target_h.read_text(errors="ignore") if target_h.is_file() else ""
    has_dmar = "USE_DSHOT_DMAR" in target_h_text

    adc_instance = None
    if "USE_ADC" in target_h_text:
        m = ADC_INSTANCE_RE.search(target_h_text)
        if m:
            adc_instance = m.group(1)

    def has_dma_request(e):
        if (e["tim"], e["ch"]) == ("TIM4", "CH4"):
            return has_dmar  # only real with USE_DSHOT_DMAR; NONE otherwise
        return (e["tim"], e["ch"]) not in NO_DMA_CHANNELS

    entries = parse_timer_hardware(target_c.read_text(errors="ignore"))
    dma_entries = [e for e in entries if consumes_dma(e["usage"]) and has_dma_request(e)]

    by_opt = defaultdict(list)
    for e in dma_entries:
        by_opt[e["dmaopt"]].append(e)

    findings = []
    for opt, group in sorted(by_opt.items()):
        if len(group) < 2:
            continue
        timers_involved = {e["tim"] for e in group}
        if len(timers_involved) == 1 and has_dmar:
            continue  # legitimate DSHOT_DMAR burst sharing within one timer
        lines = "\n".join(f"      {e['line']}" for e in group)
        # TIM_USE_LED always claims its stream whenever USE_LED_STRIP is
        # active -- an unconditional collision regardless of motor count.
        # Pure MOTOR/SERVO/OUTPUT_AUTO entries only ever claim DMA for
        # whichever positions end up as actual DSHOT motors at runtime
        # (pwm_output.c only calls timerPWMConfigChannelDMA/DMABurst from
        # the motor path, gated on getMotorCount() and
        # isMotorProtocolDshot(); the servo path never touches DMA at all).
        # But every quad -- the minimum-viable build for any target -- needs
        # its first 4 motor/servo positions (array order: position 0 = M1,
        # etc) to have working DShot-over-DMA: that's a REQUIREMENT, and a
        # collision where 2+ of the group's entries fall within those first
        # 4 positions is just as certain as an LED collision. DMA on
        # position 4+ (S5, S6, ...) is not required for a quad, but it is
        # still a real, worth-fixing gap -- a well-built target should make
        # DShot available on every output it can, not just the first four --
        # so a collision confined to position 4+ is a genuine defect, just
        # lower priority than one touching the guaranteed positions.
        has_led = any("TIM_USE_LED" in e["usage"] for e in group)
        low_positions = [
            e for e in group
            if e["motor_position"] is not None
            and e["motor_position"] < MIN_GUARANTEED_MOTOR_POSITIONS
        ]
        is_certain = has_led or len(low_positions) >= 2
        severity = "CERTAIN" if is_certain else "NOTICE"
        note = (
            "" if is_certain else
            f"\n      (none of these fall within the first {MIN_GUARANTEED_MOTOR_POSITIONS} "
            f"positions a quad requires; still worth fixing so DShot works on this output too)"
        )
        findings.append({
            "severity": severity,
            "text": (
                f"  [{severity}] dmaopt {opt} ({stream_label(opt)}) used by {len(group)} "
                f"DMA-consuming timer entries across {len(timers_involved)} timer(s):\n"
                f"{lines}{note}"
            ),
        })

    if adc_instance and adc_instance in ADC_RESERVED_DMAOPT:
        reserved = ADC_RESERVED_DMAOPT[adc_instance]
        clashing = by_opt.get(reserved, [])
        if clashing:
            lines = "\n".join(f"      {e['line']}" for e in clashing)
            # ADC's VBAT/current sensing is active on virtually every real
            # build whenever USE_ADC is defined, and unlike motor DMA it
            # isn't gated by a configurable count -- so this is unconditional
            # regardless of what usage flags the clashing timer entries have.
            findings.append({
                "severity": "CERTAIN",
                "text": (
                    f"  [CERTAIN] dmaopt {reserved} ({stream_label(reserved)}) is hardwired "
                    f"to {adc_instance} (adc_stm32h7xx.c) but also claimed by:\n{lines}"
                ),
            })

    return findings, None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("inav_root", nargs="?", default=".", help="Path to an INAV checkout")
    ap.add_argument("--target", help="Only check this target directory name")
    args = ap.parse_args()

    root = Path(args.inav_root).expanduser().resolve()
    target_root = root / "src" / "main" / "target"
    if not target_root.is_dir():
        raise SystemExit(f"Can't find {target_root} -- pass the INAV checkout root")

    targets = sorted(d for d in target_root.iterdir() if d.is_dir())
    if args.target:
        targets = [d for d in targets if d.name == args.target]
        if not targets:
            raise SystemExit(f"No target named {args.target} under {target_root}")

    certain_count = 0
    notice_count = 0
    checked = 0
    for target_dir in targets:
        findings, skip_reason = check_target(target_dir)
        if skip_reason:
            if args.target:
                print(f"{target_dir.name}: skipped ({skip_reason})", file=sys.stderr)
            continue
        checked += 1
        if findings:
            # CERTAIN first -- these are the ones that need attention regardless
            # of build, so they shouldn't get buried under NOTICE-tier findings.
            findings.sort(key=lambda f: f["severity"] != "CERTAIN")
            certain_count += sum(1 for f in findings if f["severity"] == "CERTAIN")
            notice_count += sum(1 for f in findings if f["severity"] == "NOTICE")
            print(f"\n{target_dir.name}:")
            for f in findings:
                print(f["text"])

    print()
    if certain_count == 0 and notice_count == 0:
        print(f"No dmaopt collisions found ({checked} STM32H7 target(s) checked).")
    else:
        print(
            f"{certain_count} CERTAIN, {notice_count} NOTICE finding(s) across "
            f"{checked} STM32H7 target(s) checked. CERTAIN affects every build "
            "(a quad's first 4 outputs, or an always-active LED/ADC); NOTICE "
            "only affects outputs beyond position 4, which a quad doesn't need "
            "but a well-built target should still get right. Verify each by hand "
            "against adc_stm32h7xx.c and timer_def_stm32h7xx.h."
        )


if __name__ == "__main__":
    main()
