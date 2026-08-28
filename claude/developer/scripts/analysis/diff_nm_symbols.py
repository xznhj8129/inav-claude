#!/usr/bin/env python3
"""
Brief: Diff arm-none-eabi-nm --size-sort output between two firmware builds
Usage: arm-none-eabi-nm --size-sort -C before.elf > before.txt
       arm-none-eabi-nm --size-sort -C after.elf > after.txt
       python3 diff_nm_symbols.py before.txt after.txt

What problem this solves: attributing a flash/RAM size delta between two
builds (e.g. a PR's head vs. its merge-base) to specific symbols, instead of
guessing from line-count or trusting a single top-line size number. Matches
symbols by (demangled) name and reports new/removed/changed-size symbols,
largest growth first.

When to use it: investigating a PR's or change's flash/RAM cost. Build the
same target at both commits via the inav-builder agent, dump nm --size-sort
for each, then run this. Note: with LTO + -freorder-blocks-and-partition,
single-call-site static functions often get inlined into a caller's
hot/cold partition (a `<caller>.part.0` symbol) rather than staying as
separate symbols — a big new `.part.0` entry usually means "several new
static helpers got folded into this caller," not one giant new function.
"""
import sys


def load(path):
    syms = {}
    with open(path) as f:
        for line in f:
            parts = line.strip().split(None, 2)
            if len(parts) != 3:
                continue
            size_hex, typ, name = parts
            try:
                size = int(size_hex, 16)
            except ValueError:
                continue
            syms[name] = (size, typ)
    return syms


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <before-nm.txt> <after-nm.txt>", file=sys.stderr)
        return 1

    base = load(sys.argv[1])
    head = load(sys.argv[2])

    rows = []
    for name, (hsize, htyp) in head.items():
        if name in base:
            bsize, _ = base[name]
            delta = hsize - bsize
            if delta != 0:
                rows.append((delta, name, htyp, bsize, hsize, "changed"))
        else:
            rows.append((hsize, name, htyp, 0, hsize, "new"))

    for name, (bsize, btyp) in base.items():
        if name not in head:
            rows.append((-bsize, name, btyp, bsize, 0, "removed"))

    rows.sort(key=lambda r: -r[0])

    total = sum(r[0] for r in rows)
    print(f"Total symbol-level delta (sum of matched deltas): {total} bytes")
    print(f"{'delta':>8} {'type':>5} {'base':>8} {'head':>8}  status   name")
    for delta, name, typ, bsize, hsize, status in rows:
        print(f"{delta:8d} {typ:>5} {bsize:8d} {hsize:8d}  {status:8s} {name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
