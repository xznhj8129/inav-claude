#!/usr/bin/env python3
"""Carve TEST_F blocks out of a gtest .cc file by name pattern.

Used to stage mavlink_unittest.cc across the mavlink_multiport2 PR stack:
each PR's branch keeps only the test cases whose features exist at that
stack point. Keeps everything that is not a TEST_F block (fixtures,
helpers, stubs) untouched — those are cleaned up by compiler errors.

Usage:
  carve_gtest_cases.py <file> --keep <regex> [--keep <regex> ...] [--list]

A TEST_F is kept if any regex fully matches its case name. With --list,
prints kept/dropped names without modifying the file.
"""
import argparse
import re
import sys

def parse_blocks(text):
    """Yield (start, end, name) for each TEST_F block, brace-matched."""
    for m in re.finditer(r'^TEST(?:_F|_P)?\(\s*\w+\s*,\s*(\w+)\s*\)\s*\{', text, re.M):
        name = m.group(1)
        depth = 0
        i = text.index('{', m.start())
        for j in range(i, len(text)):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    # extend through trailing newline(s)
                    end = j + 1
                    while end < len(text) and text[end] == '\n':
                        end += 1
                        break
                    yield (m.start(), end, name)
                    break

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--keep', action='append', required=True)
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args()

    text = open(args.file).read()
    keep_res = [re.compile(p + r'\Z') for p in args.keep]

    kept, dropped, cuts = [], [], []
    for start, end, name in parse_blocks(text):
        if any(r.match(name) for r in keep_res):
            kept.append(name)
        else:
            dropped.append(name)
            cuts.append((start, end))

    if args.list:
        print("KEEP (%d):" % len(kept), *kept, sep='\n  ')
        print("DROP (%d):" % len(dropped), *dropped, sep='\n  ')
        return

    for start, end in reversed(cuts):
        text = text[:start] + text[end:]
    open(args.file, 'w').write(text)
    print(f"kept {len(kept)}, dropped {len(dropped)}")

if __name__ == '__main__':
    sys.exit(main())
