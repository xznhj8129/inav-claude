#!/usr/bin/env python3
"""Self-tests for audit_static_linkage.py.

Run:  python3 test_audit.py   (from this directory)
Exit 0 on success, 1 on failure.

Validates the two core behaviors that matter for the INAV MAVLink bug:

1. The scanner sees through a macro-hidden `static` (MAVLINK_HELPER ->
   static) and finds a function defined in a header whose body carries a
   local static aggregate table, reporting the table's byte size.
2. Duplication cost = size * (TU_count - 1): two consumer TUs including
   the same header must be reported as one symbol with tu_count=2 and
   wasted_bytes == table size.
3. Trivial accessors with no local static data report 0 local static bytes.
4. The Part B safety pass flags a static object used in a compile-time
   constant context (array bound) as "keep, needs constant-expression".
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "audit_static_linkage.py")
FIXTURES = os.path.join(HERE, "fixtures")


def run_tool(files, args=None, out=None):
    cmd = [sys.executable, TOOL, "--files"] + files
    if out:
        cmd += ["--out", out]
    if args:
        cmd += ["--args"] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r


def main():
    failures = 0

    # ---- 1. scanner: mavlink-style pattern through macro ----
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "f1.json")
        r = run_tool(
            [os.path.join(FIXTURES, "consumer_a.c")],
            args=["-I" + FIXTURES, "-I" + FIXTURES],
            out=out,
        )
        if r.returncode != 0:
            print(f"FAIL: tool exited {r.returncode}\n{r.stderr}")
            failures += 1
        else:
            rows = json.load(open(out))
            entries = [x for x in rows if x["symbol"] == "mavlink_get_msg_entry"]
            if len(entries) != 1:
                print(f"FAIL: expected 1 mavlink_get_msg_entry, got {len(entries)}: {rows}")
                failures += 1
            else:
                e = entries[0]
                # 5 entries x sizeof(mavlink_msg_entry_t) = 5*12 = 60 bytes
                if e["local_static_bytes"] != 60:
                    print(f"FAIL: local_static_bytes={e['local_static_bytes']} (expected 60)")
                    failures += 1
                if e["tu_count"] != 1:
                    print(f"FAIL: single-TU run tu_count={e['tu_count']} (expected 1)")
                    failures += 1
                if e["wasted_bytes"] != 0:
                    print(f"FAIL: single-TU wasted={e['wasted_bytes']} (expected 0)")
                    failures += 1
                print(f"ok: scanner finds {e['symbol']} ({e['local_static_bytes']}B local static)")

        # ---- 2. duplication cost across 2 TUs ----
        out2 = os.path.join(tmp, "f2.json")
        r = run_tool(
            [
                os.path.join(FIXTURES, "consumer_a.c"),
                os.path.join(FIXTURES, "consumer_b.c"),
            ],
            args=["-I" + FIXTURES],
            out=out2,
        )
        if r.returncode != 0:
            print(f"FAIL: tool exited {r.returncode}\n{r.stderr}")
            failures += 1
        else:
            rows = json.load(open(out2))
            entries = [x for x in rows if x["symbol"] == "mavlink_get_msg_entry"]
            if len(entries) != 1:
                print(f"FAIL: expected 1 aggregated entry, got {len(entries)}: {rows}")
                failures += 1
            else:
                e = entries[0]
                if e["tu_count"] != 2:
                    print(f"FAIL: tu_count={e['tu_count']} (expected 2)")
                    failures += 1
                if e["local_static_bytes"] != 60 or e["wasted_bytes"] != 60:
                    print(
                        f"FAIL: bytes={e['local_static_bytes']} wasted={e['wasted_bytes']} "
                        "(expected 60/60)"
                    )
                    failures += 1
                else:
                    print(f"ok: 2-TU duplication = {e['wasted_bytes']}B (size {e['local_static_bytes']}B x1 extra copy)")

        # ---- 3. trivial accessors: no local static data ----
        out3 = os.path.join(tmp, "f3.json")
        r = run_tool(
            [os.path.join(FIXTURES, "consumer_b.c")],
            args=["-I" + FIXTURES],
            out=out3,
        )
        if r.returncode != 0:
            print(f"FAIL: tool exited {r.returncode}\n{r.stderr}")
            failures += 1
        else:
            rows = json.load(open(out3))
            trivial = [x for x in rows if x["symbol"] in ("cfgGetType", "cfgGetPosition", "cmp16", "cmp32")]
            if any(x["local_static_bytes"] != 0 for x in trivial):
                print(f"FAIL: trivial accessor reported local static data: {trivial}")
                failures += 1
            else:
                print(f"ok: {len(trivial)} trivial accessors report 0 local static bytes")

        # ---- 4. safety pass: constant-expression usage ----
        out4 = os.path.join(tmp, "f4.json")
        r = run_tool(
            [os.path.join(FIXTURES, "consumer_constexpr.c")],
            args=["-I" + FIXTURES],
            out=out4,
        )
        if r.returncode != 0:
            print(f"FAIL: tool exited {r.returncode}\n{r.stderr}")
            failures += 1
        else:
            rows = json.load(open(out4))
            lookup = [x for x in rows if x["symbol"] == "lookup_size"]
            if not lookup:
                print(f"FAIL: lookup_size not found: {rows}")
                failures += 1
            elif "keep, needs constant-expression" not in lookup[0].get("safety", ""):
                print(f"FAIL: lookup_size safety={lookup[0].get('safety')} (expected 'keep, needs constant-expression')")
                failures += 1
            else:
                print("ok: safety pass flags constant-expression usage as 'keep'")

    if failures:
        print(f"\n{failures} FAILURES")
        return 1
    print("\nAll audit tool self-tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
