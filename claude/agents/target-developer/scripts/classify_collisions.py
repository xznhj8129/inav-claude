#!/usr/bin/env python3
"""Classify DMA_STREAM_COLLISION hazards by severity.

Firmware ownership model (confirmed in timer_impl_stdperiph.c +
pwm_mapping.c:pwmInitMotors): motors are initialized strictly in position
order (idx = 0..motorCount-1); the FIRST entry to reach a shared DMA
descriptor claims it (dmaInit -> owner = OWNER_TIMER); every later entry
resolving to the same (dma,stream) tuple hits `owner != OWNER_FREE` and
silently fails to configure. So within one collision group, the LOWEST
position always wins and stays alive; every OTHER (higher) position in the
group is a loser and goes dead.

Severity is therefore about the losers, not the group as a whole:
  CERTAIN - the second-lowest position in the group (the best-case loser)
            is < 4, i.e. an S1-S4 output actually goes dead.
  NOTICE  - all losers are at position >= 4; the S1-S4 member of the group
            (if any) is the winner and keeps working fine.

On USE_DSHOT_DMAR targets, simulate_pwm_roles.py additionally emits
BURST_STREAM_COLLISION instead of (or alongside) DMA_STREAM_COLLISION for
groups affected by burst mode's per-PHYSICAL-TIMER (not per-channel) DMA
claim -- see that script's module docstring for the full model. This
script treats both hazard types identically for severity purposes (same
"loser position < 4" rule, same winner-always-lower-position guarantee),
since simulate_pwm_roles.py's BURST_STREAM_COLLISION text embeds the same
"TIM_CH" substrings this script matches positions against.

KNOWN BLIND SPOT, FIXED 2026-08-21: a MOTOR-vs-LED_STRIP collision can
NEVER be surfaced by the CERTAIN/NOTICE machinery above, structurally --
LED-strip rows never get a `position` (simulate_pwm_roles.py's per-row
loop only assigns `pos` for the MOTOR and SERVO buckets; the LED branch
leaves it None), and this function's `involved` list filters out any
tim_ch whose looked-up position is None before the `len(involved) < 2`
check even runs. So a real motor-vs-LED collision always collapses to a
1-element `involved` list and is silently dropped -- not misclassified,
just invisible, from every prior run of this tool. Found by hand while
using this script's output as a work list for Phase 2 step 3 of
investigate-shared-tim-dma-request-lines (AIKONF7's TIM3_CH2 vs TIM2_CH1
collision, where TIM2_CH1 is TIM_USE_LED, never appeared in any NOTICE
list despite firing at every motorCount from 4 up). A full re-sweep this
same pass found FURYF4OSD has the same previously-invisible pattern too
(TIM3_CH4 vs TIM5_CH1/LED_STRIP) -- both now correctly reported below by
`led_collisions()`, a structurally separate detection pass (LED-vs-motor
severity is always deterministic -- motors init before ledStripInit() in
fc_init.c, so a MOTOR side always wins and the LED silently just doesn't
light; never flight-critical, so there's no CERTAIN/NOTICE split to make
here, just a single LED_COLLISION bucket).

CONDITIONAL-COMPILATION BLIND SPOT, FIXED 2026-08-21: parser-gap targets
(conditional-compilation flattening -- see simulate_pwm_roles.py's
parse_target_c() docstring) used to silently surface same-(tim,ch)-twice
false hits here (or, worse on MAMBAF405US, silently mask a real hazard
behind a clean #ifdef branch) with no way to tell from this script's
output alone. parse_target_c() is now preprocessor-aware (entry.conditional
/ entry.conditional_expr); main() checks sim.has_conditional_tim() per
target before calling classify()/led_collisions() and reports those
targets in a separate N/A bucket instead of feeding them through the
CERTAIN/NOTICE/LED_COLLISION machinery.

Usage: python3 classify_collisions.py <inav-checkout-root> <targets-file>
<targets-file> lists one target name per line, F4/F7/AT32 only. Build it
with simulate_pwm_roles.detect_family() in ("F4","F7","AT32") to exclude
H7 (out of scope -- separate hazard model, handled by check_dma_conflicts.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate_pwm_roles as sim  # noqa: E402

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
TARGETS_FILE = Path(sys.argv[2]) if len(sys.argv) > 2 else None


def _load(target_name):
    """Shared parse/setup for one target. Returns None if not applicable,
    else (family, entries, adc_pins, led_strip, dshot_dmar, dma_resolver,
    max_mc)."""
    target_dir = ROOT / "src" / "main" / "target" / target_name
    target_c = target_dir / "target.c"
    target_h = target_dir / "target.h"
    cmake = target_dir / "CMakeLists.txt"
    if not target_c.is_file() or not cmake.is_file():
        return None
    family = sim.detect_family(cmake.read_text(errors="ignore"))
    if family is None:
        return None
    entries = sim.parse_target_c(target_c.read_text(errors="ignore"))
    if not entries:
        return None
    adc_pins, led_strip, dshot_dmar = (set(), False, False)
    if target_h.is_file():
        adc_pins, led_strip, dshot_dmar = sim.parse_target_h(target_h.read_text(errors="ignore"))
    dma_resolver = sim.DmaResolver(family, target_dir,
                                    target_h.read_text(errors="ignore") if target_h.is_file() else "",
                                    dshot_dmar)
    max_mc = max(12, len(entries))
    return family, entries, adc_pins, led_strip, dshot_dmar, dma_resolver, max_mc


def classify(target_name):
    loaded = _load(target_name)
    if loaded is None:
        return None
    _family, entries, adc_pins, led_strip, dshot_dmar, dma_resolver, max_mc = loaded

    worst = None  # None, "NOTICE", or "CERTAIN"
    detail = []
    for mc in range(4, max_mc + 1):
        result = sim.simulate(entries, mc, None, adc_pins, led_strip, dma_resolver, True, {})
        for h in result.hazards:
            if not (h.startswith("DMA_STREAM_COLLISION") or h.startswith("BURST_STREAM_COLLISION")):
                continue
            positions = {}
            for row in result.rows:
                e = row["entry"]
                if row["claims_dma"]:
                    positions[f"{e.tim}_{e.ch}"] = row["position"]
            involved = sorted((pos, tim_ch) for tim_ch, pos in positions.items() if tim_ch in h and pos is not None)
            if len(involved) < 2:
                continue  # need at least a winner + a loser to say anything
            losers = involved[1:]  # everything but the lowest position (the winner)
            worst_loser_pos = losers[0][0]  # best-case loser = lowest among losers
            sev = "CERTAIN" if worst_loser_pos < 4 else "NOTICE"
            if sev == "CERTAIN":
                worst = "CERTAIN"
            elif worst is None:
                worst = "NOTICE"
            detail.append((mc, sev, involved, dshot_dmar))
    return worst, detail, dshot_dmar


def led_collisions(target_name):
    """Detect MOTOR-vs-LED_STRIP DMA collisions -- structurally invisible to
    classify()'s CERTAIN/NOTICE machinery, see module docstring. Returns
    (first_mc, motor_tim_ch, led_tim_ch) for the first motorCount at which a
    real (non-parser-gap-duplicate) hit occurs, or None."""
    loaded = _load(target_name)
    if loaded is None:
        return None
    _family, entries, adc_pins, led_strip, dshot_dmar, dma_resolver, max_mc = loaded
    if not led_strip:
        return None  # target has no LED strip at all, can't collide with one

    for mc in range(4, max_mc + 1):
        result = sim.simulate(entries, mc, None, adc_pins, led_strip, dma_resolver, True, {})
        led_tim_ch = {row["entry"].tim + "_" + row["entry"].ch
                      for row in result.rows if "LED" in row["bucket"]}
        if not led_tim_ch:
            continue
        for h in result.hazards:
            if not (h.startswith("DMA_STREAM_COLLISION") or h.startswith("BURST_STREAM_COLLISION")):
                continue
            hit_led = [tc for tc in led_tim_ch if tc in h]
            if not hit_led:
                continue
            # Identify the non-LED (motor) participant for the report line.
            # Same-(tim,ch)-twice parser-gap duplicates show up as the LED
            # tim_ch appearing twice with different labels in the hazard
            # text; that's not a real motor partner, so guard against it.
            motor_tim_ch = None
            for row in result.rows:
                e = row["entry"]
                tc = f"{e.tim}_{e.ch}"
                if tc in hit_led:
                    continue
                if tc in h and row.get("claims_dma"):
                    motor_tim_ch = tc
                    break
            return (mc, motor_tim_ch, hit_led[0])
    return None


def main():
    certain, notice, led, conditional = [], [], [], []
    for line in TARGETS_FILE.read_text().splitlines():
        t = line.strip()
        if not t:
            continue
        loaded = _load(t)
        if loaded is not None and sim.has_conditional_tim(loaded[1]):
            # DEF_TIM lines guarded by #if/#ifdef/#ifndef: parse_target_c()
            # flattens every build variant into one array, so any verdict
            # derived from it here could be a self-collision false positive
            # or a hazard masked by another variant's clean line. Report
            # N/A instead of silently including or excluding this target --
            # see simulate_pwm_roles.py's parse_target_c() docstring.
            conditional.append(t)
            continue
        try:
            res = classify(t)
        except Exception as ex:
            print(f"ERROR {t}: {ex}", file=sys.stderr)
            continue
        if res is not None:
            worst, detail, dshot_dmar = res
            if worst == "CERTAIN":
                first = next(d for d in detail if d[1] == "CERTAIN")
                certain.append((t, first[0], first[2], dshot_dmar))
            elif worst == "NOTICE":
                first = detail[0]
                notice.append((t, first[0], first[2], dshot_dmar))
        try:
            led_hit = led_collisions(t)
        except Exception as ex:
            print(f"ERROR (LED check) {t}: {ex}", file=sys.stderr)
            led_hit = None
        if led_hit is not None:
            led.append((t,) + led_hit)

    def fmt(pairs):
        return ",".join(f"{tc}@pos{p}" for p, tc in pairs)

    print(f"=== CERTAIN (a loser sits at position < 4 -- a basic-quad output actually goes dead): {len(certain)} targets ===")
    for t, mc, pairs, dmar in certain:
        print(f"  {t}  (first at motorCount={mc})  {fmt(pairs)}{'  [USE_DSHOT_DMAR]' if dmar else ''}")
    print(f"\n=== NOTICE (all losers at position >= 4; any S1-S4 member wins and stays alive): {len(notice)} targets ===")
    for t, mc, pairs, dmar in notice:
        print(f"  {t}  (first at motorCount={mc})  {fmt(pairs)}{'  [USE_DSHOT_DMAR]' if dmar else ''}")
    print(f"\n=== LED_COLLISION (MOTOR always wins over LED strip specifically; LED silently doesn't light, never flight-critical): {len(led)} targets ===")
    for t, mc, motor_tc, led_tc in led:
        print(f"  {t}  (first at motorCount={mc})  motor={motor_tc} led={led_tc}")
    print(f"\n=== N/A (timerHardware[] has #if/#ifdef/#ifndef-guarded DEF_TIM lines -- needs manual per-build-variant review): {len(conditional)} targets ===")
    for t in conditional:
        print(f"  {t}")


if __name__ == "__main__":
    main()
