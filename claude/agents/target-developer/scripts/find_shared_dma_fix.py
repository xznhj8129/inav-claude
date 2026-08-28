#!/usr/bin/env python3
"""find_shared_dma_fix.py -- given one or more targets, find a safe dmavar
reassignment that clears SHARED_TIMER_DMA_REQUEST hazards (see
simulate_pwm_roles.py's DmaResolver.is_shared_multichannel_request()
docstring for the underlying defect: a channel sitting on an F4/F7-style
"combined" CH1/CH2/CH3 DMA request line while a sibling channel of the same
physical timer is also genuinely driven, corrupting both channels' DSHOT
transfers).

WHY THIS EXISTS
================
A single flagged channel usually has more than one alternate `dmavar`
option in the header table (timer_def_stm32f4xx.h / timer_def_stm32f7xx.h),
but trying them ONE CHANNEL AT A TIME is misleading when a target has
MULTIPLE flagged siblings on the same combined-request group: fixing one
alone leaves the others still flagged (a channel that's still genuinely
driven keeps polluting the combined line regardless of which stream ITS
OWN dmaInit call ends up using -- see the docstring on
is_shared_multichannel_request() for why "active" doesn't care what stream
the active channel itself picked). This looks like "no fix available" if
you only ever test one channel's candidates in isolation. This tool
searches combinations of ALL flagged siblings on a target simultaneously
(smallest number of channels changed first), verifying each candidate
combination against the REAL constraint: every SHARED_TIMER_DMA_REQUEST hit
must clear AND no new DMA_STREAM_COLLISION/SILENT_DEAD_MOTOR hazard may
appear anywhere in the motorCount sweep, compared to baseline.

Some targets have a genuine, IRREDUCIBLE hardware DMA-topology conflict --
two outputs whose only non-combined routes are the identical physical DMA
stream (a channel whose header table lists the SAME stream number for
every option it has, e.g. TIM8_CH1 = D(2,2,0),D(2,2,7) -- both DMA2
Stream2). No dmavar combination can satisfy both simultaneously; this tool
reports the best PARTIAL fix (whichever channels DO have a clean escape)
and leaves the rest flagged rather than pretending a clean fix exists. When
that happens, prefer keeping an S1-S4 (position < 4) output working over a
higher-position one -- see investigate-shared-tim-dma-request-lines/
phase1-findings.md's "2026-08-23" update for two real, fully-worked
examples (BEEROTORF4, DALRCF722DUAL) of this exact tradeoff, including how
to read a resulting DMA_STREAM_COLLISION "who wins" outcome.

Usage
=====
  ./find_shared_dma_fix.py <inav_root> --target NAME [--target NAME ...]
  ./find_shared_dma_fix.py <inav_root> --targets-file FILE
      One target name per line.

  --apply    Actually rewrite the trailing dmavar argument of each affected
             DEF_TIM(...) line in target.c (only that one argument --
             everything else about the line, including comments and
             whitespace, is preserved byte-for-byte). Without --apply, only
             prints the proposed fix (dry run, default).

Output, per target: every currently-flagged (tim,ch), its position and
whether it's an S1-S4 (position < 4) output, and either the dmavar
reassignment found (all changed channels) or a note that no combination
clears everything, with whichever partial fix is safe to apply.
"""
import argparse
import itertools
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate_pwm_roles as sim  # noqa: E402
import classify_collisions as cc  # noqa: E402

HAZARD_RE = re.compile(r'^SHARED_TIMER_DMA_REQUEST: (\w+)_(\w+) \(([^)]*)\) dmavar=(\d+)')

DEF_TIM_LINE_RE = re.compile(
    r'^(?P<pre>.*DEF_TIM\(\s*(?P<tim>[A-Za-z0-9_]+)\s*,\s*(?P<ch>[A-Za-z0-9_]+)\s*,'
    r'\s*[^,]+?\s*,\s*[^,]+?\s*,\s*[^,]+?\s*,\s*)(?P<dmavar>\d+)(?P<post>\s*\).*)$'
)


def find_hits(root, target):
    cc.ROOT = root
    loaded = cc._load(target)
    if loaded is None:
        return None
    family, entries, adc_pins, led_strip, dshot_dmar, dma_resolver, max_mc = loaded
    hits = {}
    for mc in range(4, max_mc + 1):
        result = sim.simulate(entries, mc, None, adc_pins, led_strip, dma_resolver, True, {})
        pos_by_tc = {(row["entry"].tim, row["entry"].ch): row["position"] for row in result.rows}
        for h in result.hazards:
            m = HAZARD_RE.match(h)
            if not m:
                continue
            tim, ch, label, dmavar = m.groups()
            key = (tim, ch)
            if key not in hits:
                hits[key] = {"tim": tim, "ch": ch, "label": label, "dmavar": int(dmavar), "positions": set()}
            pos = pos_by_tc.get((tim, ch))
            if pos is not None:
                hits[key]["positions"].add(pos)
    return family, entries, adc_pins, led_strip, dshot_dmar, dma_resolver, hits, max_mc


def _sweep_hazards(entries, overrides, adc_pins, led_strip, dma_resolver, max_mc):
    out = {}
    for mc in range(4, max_mc + 1):
        cloned = sim.clone_entries(entries)
        for e in cloned:
            if (e.tim, e.ch) in overrides:
                e.dmavar = overrides[(e.tim, e.ch)]
        result = sim.simulate(cloned, mc, None, adc_pins, led_strip, dma_resolver, True, {})
        out[mc] = set(result.hazards)
    return out


def find_group_fix(entries, hits, adc_pins, led_strip, dma_resolver, max_mc):
    """Search combinations of ALL flagged (tim,ch) keys simultaneously,
    smallest number of channels changed first. Returns (overrides, fully_ok)
    -- overrides is the best combination found (possibly partial, i.e. some
    hits remain unresolved); fully_ok is True iff it clears every hit with
    no new non-shared hazard anywhere in the sweep."""
    keys = list(hits.keys())
    candidates_per_key = []
    for (tim, ch) in keys:
        opts = dma_resolver._lookup(tim, ch)
        orig = hits[(tim, ch)]["dmavar"]
        cands = [orig] + [i for i in range(len(opts)) if i != orig] if opts else [orig]
        candidates_per_key.append(cands)

    baseline = _sweep_hazards(entries, {}, adc_pins, led_strip, dma_resolver, max_mc)
    baseline_non_shared = {mc: {h for h in hz if not h.startswith("SHARED_TIMER_DMA_REQUEST")}
                            for mc, hz in baseline.items()}

    all_combos = list(itertools.product(*candidates_per_key))

    def changes(combo):
        return sum(1 for k, v in zip(keys, combo) if v != hits[k]["dmavar"])
    all_combos.sort(key=changes)

    best_partial = None
    best_partial_remaining = None
    for combo in all_combos:
        if changes(combo) == 0:
            continue
        overrides = {k: v for k, v in zip(keys, combo)}
        trial = _sweep_hazards(entries, overrides, adc_pins, led_strip, dma_resolver, max_mc)
        remaining_shared = set()
        new_non_shared = False
        for mc in trial:
            shared = {h for h in trial[mc] if h.startswith("SHARED_TIMER_DMA_REQUEST")}
            remaining_shared |= shared
            non_shared = {h for h in trial[mc] if not h.startswith("SHARED_TIMER_DMA_REQUEST")}
            if non_shared - baseline_non_shared[mc]:
                new_non_shared = True
                break
        if new_non_shared:
            continue
        if not remaining_shared:
            return overrides, True
        if best_partial is None or len(remaining_shared) < best_partial_remaining:
            best_partial, best_partial_remaining = overrides, len(remaining_shared)
    return best_partial, False


def apply_fix(root, target, overrides):
    path = root / "src" / "main" / "target" / target / "target.c"
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    remaining = dict(overrides)
    out_lines = []
    for line in lines:
        newline = ""
        body = line
        if body.endswith("\r\n"):
            newline, body = "\r\n", body[:-2]
        elif body.endswith("\n"):
            newline, body = "\n", body[:-1]
        m = DEF_TIM_LINE_RE.match(body)
        if m and (m.group("tim"), m.group("ch")) in remaining:
            key = (m.group("tim"), m.group("ch"))
            new_dv = remaining.pop(key)
            new_line = m.group("pre") + str(new_dv) + m.group("post") + newline
            out_lines.append(new_line)
        else:
            out_lines.append(line)
    if remaining:
        print(f"  WARNING: could not find DEF_TIM line(s) for {list(remaining)}", file=sys.stderr)
        return False
    path.write_text("".join(out_lines))
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("--target", action="append", default=[])
    p.add_argument("--targets-file")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    root = Path(args.root)
    targets = list(args.target)
    if args.targets_file:
        targets += [t.strip() for t in Path(args.targets_file).read_text().splitlines() if t.strip()]
    if not targets:
        p.error("need --target or --targets-file")

    for t in targets:
        loaded = find_hits(root, t)
        print(f"\n=== {t} ===")
        if loaded is None:
            print("  could not load target (missing target.c/CMakeLists.txt, or unsupported family)")
            continue
        family, entries, adc_pins, led_strip, dshot_dmar, dma_resolver, hits, max_mc = loaded
        if not hits:
            print("  no SHARED_TIMER_DMA_REQUEST hits")
            continue
        for (tim, ch), hit in hits.items():
            min_pos = min(hit["positions"]) if hit["positions"] else None
            s14 = " S1-S4" if (min_pos is not None and min_pos < 4) else ""
            print(f"  {tim}_{ch} ({hit['label']}) pos={min_pos}{s14} dmavar={hit['dmavar']}")
        overrides, fully_ok = find_group_fix(entries, hits, adc_pins, led_strip, dma_resolver, max_mc)
        if overrides is None:
            print("  NO FIX: every candidate combination introduces a new hazard; "
                  "this target needs manual review (see module docstring)")
            continue
        label = "FULL FIX" if fully_ok else "PARTIAL FIX (some hits remain -- irreducible hardware conflict, see docstring)"
        print(f"  {label}: {overrides}")
        if args.apply:
            if apply_fix(root, t, overrides):
                print("  applied.")


if __name__ == "__main__":
    main()
