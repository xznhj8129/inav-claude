#!/usr/bin/env python3
"""AST-based audit for static-linkage data duplication in headers.

Every `.c` file that includes a header defining an internal-linkage
(`static`) function or object gets its own private copy — of the function
*and* of any local `static` array/struct/table inside it. The linker can't
merge them because each is a distinct internal-linkage symbol. A plain-text
grep for "static inline" misses this because the linkage often comes from a
macro (e.g. MAVLink's `MAVLINK_HELPER` expands to plain `static`, so the
literal string "static inline" never appears at the call site).

This tool parses translation units with libclang so macros expand, then:

  Part A (scanner):  for each function/object with internal linkage whose
      definition lives in a header, find local `static` variables (arrays,
      structs), compute their size via libclang's type layout, count how
      many TUs instantiate the header content, and report
      `size * (tu_count - 1)` as wasted bytes.
  Part B (safety):   for each flagged candidate, check whether it is used
      in a compile-time constant expression (array bound, _Static_assert,
      static initializer). If so, converting it to `extern` would break the
      build — the finding is flagged "keep, needs constant-expression"
      rather than "convert to extern".

Output is structured (JSON/CSV) so downstream triage can be automated.

Usage:
  # Full scan using a CMake-generated compile database:
  python3 audit_static_linkage.py --compile-db build_sitl_cc/compile_commands.json \
      --out findings.json --csv findings.csv

  # Scan specific files with explicit flags (no compile db needed):
  python3 audit_static_linkage.py --files lib/main/MAVLink/storm32/mavlink.h \
      --args "-Ilib/main/MAVLink" "-Isrc/main" --out findings.json

  # Only Part A (skip the constant-expression safety pass):
  python3 audit_static_linkage.py --compile-db build/compile_commands.json --no-safety

Requirements: pip package `libclang` (bundles its own libclang.so) — or a
system libclang matching the Python bindings' major version.
"""

import argparse
import csv
import json
import os
import re
import shlex
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# libclang setup
# ---------------------------------------------------------------------------

def _find_libclang():
    """Return a path to a libclang shared library, preferring the pip
    package's bundled copy (version-matched to the bindings)."""
    import clang.cindex as ci

    # 1. pip `libclang` bundles its own .so inside the package.
    bundled = Path(ci.__file__).parent / "native" / "libclang.so"
    if bundled.exists():
        return str(bundled)

    # 2. Common system locations, checked against the bindings' major version.
    ver = getattr(ci, "__version__", "") or ""
    major = ver.split(".")[0] if ver else ""
    for cand in (
        f"/usr/lib/x86_64-linux-gnu/libclang-{major}.so.1",
        f"/usr/lib/llvm-{major}/lib/libclang.so.1",
        "/usr/lib/x86_64-linux-gnu/libclang.so.1",
    ):
        if Path(cand).exists():
            return cand
    return None


def _init_cindex():
    import clang.cindex as ci

    lib = _find_libclang()
    if lib:
        ci.Config.set_library_file(lib)
    return ci


# ---------------------------------------------------------------------------
# Compile-database handling
# ---------------------------------------------------------------------------

# Flags that are meaningless (or harmful) to libclang on the host and safe
# to drop: machine-specific codegen, linker input, and a few GNU-isms that
# make clang emit hard errors instead of warnings.
_DROP_ARG_RE = re.compile(
    r"^("
    r"-mcpu=|-march=|-mthumb|-marm|-mfloat-abi=|-mfpu=|-mtune=|-mabi=|-mlittle-endian|-mbig-endian"
    r"|-specs=|-Wl,|-T\b|-T[0-9]"
    r"|-fno-.*|-f.*sections|-fstack-usage|-fconserve-stack"
    r"|-nostartfiles|-nodefaultlibs|-nostdlib|-lgcc|-lc"
    r"|-MMD|-MP|-MF|-MT"
    r")"
)


def sanitize_args(args):
    """Strip flags that make host libclang fail; keep -D/-I/-isystem/-std/
    -include/-f (warnings etc.) which it tolerates."""
    out = []
    skip_next = False
    for a in args:
        if skip_next:
            skip_next = False
            continue
        if a in ("-c", "-o", "-MF", "-MT", "-MQ", "-include", "-isystem", "-I", "-D", "-std"):
            # Single-letter forms with a separate value: keep value only for
            # -D/-I/-std/-include/-isystem; -c/-o are dropped along with
            # their value.
            if a in ("-c", "-o", "-MF", "-MT", "-MQ"):
                skip_next = True
                continue
            out.append(a)
            continue
        if _DROP_ARG_RE.match(a):
            continue
        out.append(a)
    # Silence noise from GCC-flavored flags clang doesn't recognize.
    out.append("-Wno-unknown-warning-option")
    return out


def load_compile_db(path):
    """Return a list of (source_file, args) tuples from a compile_commands.json."""
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)

    out = []
    for e in entries:
        directory = e.get("directory", "")
        file_ = e.get("file")
        if not file_:
            continue
        if "arguments" in e and e["arguments"]:
            args = list(e["arguments"])
            # [0] is the compiler binary; the rest are flags.
            args = args[1:]
        elif "command" in e:
            args = shlex.split(e["command"])[1:]
        else:
            continue
        if not file_.endswith((".c", ".cc", ".cpp", ".h", ".hpp")):
            continue
        abs_file = file_ if os.path.isabs(file_) else os.path.join(directory, file_)
        out.append((os.path.normpath(abs_file), args))
    return out


# ---------------------------------------------------------------------------
# AST scanning
# ---------------------------------------------------------------------------

def _is_header_path(path):
    return path is not None and path.lower().endswith((".h", ".hpp", ".hh"))


def _is_function_local(cursor):
    """True if `cursor` is a variable declared inside a function body."""
    cur = cursor.semantic_parent
    depth = 0
    while cur is not None and depth < 12:
        if cur.kind == _FUNCTION_DECL:
            return True
        if cur.kind == _TRANSLATION_UNIT:
            return False
        cur = cur.semantic_parent
        depth += 1
    return False


def _cursor_location_file(cursor):
    try:
        loc = cursor.location
        if loc and loc.file:
            return str(loc.file)
    except Exception:
        pass
    return None


def _static_data_size(cursor):
    """Total bytes of local `static` variables inside a function body."""
    total = 0
    for c in cursor.walk_preorder():
        if c.kind == _VAR_DECL and c.storage_class == _STATIC:
            try:
                size = c.type.get_size()
            except Exception:
                size = -1
            if size > 0:
                total += size
    return total


def _find_internal_linkage_in_header(tu, is_header_fn):
    """Part A core: find functions/objects with internal linkage whose
    definition lives in a header, with their local static data sizes.

    Returns a dict keyed by (header_path, spelling):
      { 'kind': 'function'|'object',
        'spelling': ...,
        'header': header_path,
        'tu': source file this TU parsed,
        'local_static_bytes': sum of local static aggregate sizes,
        'decl_line': int,
        'referenced': bool }   # any DECL_REF_EXPR to it in this TU
    """
    found = []
    seen = set()

    # Pass 1: collect referenced spellings — but only references whose
    # location is in the TU's own code (a non-header file). References
    # inside the header itself (e.g. one helper calling another) appear in
    # every TU that includes the header regardless of whether the TU uses
    # the symbol, which would over-count the duplication a linker keeps.
    refs = set()
    for c in tu.cursor.walk_preorder():
        if c.kind != _DECL_REF_EXPR:
            continue
        ref_loc = _cursor_location_file(c)
        if not ref_loc or _is_header_path(ref_loc):
            continue
        refs.add(c.spelling)

    # Pass 2: classify internal-linkage definitions located in headers.
    for c in tu.cursor.walk_preorder():
        if c.kind not in (_FUNCTION_DECL, _VAR_DECL):
            continue
        if c.storage_class != _STATIC:
            continue
        if not c.is_definition():
            continue
        loc_file = _cursor_location_file(c)
        if not is_header_fn(loc_file):
            continue
        if c.kind == _VAR_DECL and _is_function_local(c):
            # Local statics inside a header function are already counted
            # via the function's local_static_bytes — don't double-report.
            continue
        try:
            decl_line = c.location.line
        except Exception:
            decl_line = -1
        # A definition in a header with internal linkage: candidate.
        key = (loc_file, c.spelling, decl_line)
        if key in seen:
            continue
        seen.add(key)

        local_static = 0
        if c.kind == _FUNCTION_DECL:
            local_static = _static_data_size(c)
            kind = "function"
        else:
            try:
                size = c.type.get_size()
            except Exception:
                size = -1
            local_static = max(size, 0)
            kind = "object"

        found.append(
            {
                "kind": kind,
                "spelling": c.spelling,
                "header": loc_file,
                "tu": str(tu.spelling),
                "local_static_bytes": local_static,
                "decl_line": decl_line,
                "referenced": c.spelling in refs,
            }
        )
    return found


# ---------------------------------------------------------------------------
# Part B: constant-expression safety check
# ---------------------------------------------------------------------------

_CONST_CONTEXT_KINDS = None  # filled after init


def _is_constant_context(cursor):
    """Walk up the ancestor chain: if this reference is part of a static
    initializer, array bound, or static assertion, it needs compile-time
    constness and cannot simply become `extern`."""
    cur = cursor
    depth = 0
    while cur is not None and depth < 12:
        k = cur.kind
        if k == _VAR_DECL:
            # static / file-scope variable whose initializer uses the symbol
            if cur.storage_class == _STATIC or cur.linkage == _EXTERNAL:
                return True
        if k == _STATIC_ASSERT:
            return True
        if k == _ARRAY_TYPE:
            return True
        if k == _ENUM_CONSTANT_DECL:
            return True
        cur = cur.semantic_parent
        depth += 1
    return False


def safety_check(tu, spelling):
    """Return True if `spelling` is referenced inside a compile-time
    constant context anywhere in `tu`."""
    for c in tu.cursor.walk_preorder():
        if c.kind == _DECL_REF_EXPR and c.spelling == spelling:
            if _is_constant_context(c):
                return True
    return False


def safety_scan_tu(tu, spellings):
    """Single-pass variant: return the subset of `spellings` referenced in a
    compile-time constant context anywhere in `tu`. One AST walk instead of
    one walk per symbol."""
    const_used = set()
    for c in tu.cursor.walk_preorder():
        if c.kind != _DECL_REF_EXPR:
            continue
        if c.spelling not in spellings:
            continue
        if _is_constant_context(c):
            const_used.add(c.spelling)
    return const_used


# ---------------------------------------------------------------------------
# Aggregation & reporting
# ---------------------------------------------------------------------------

def aggregate(findings_per_tu):
    """Cross-reference which TUs instantiate each header symbol.

    findings_per_tu: list of lists (one per TU) as returned by
    _find_internal_linkage_in_header.

    Two TU counts are reported:
      tu_count          — TUs whose compilation includes the header and
                          therefore instantiates a private copy.
      ref_tu_count      — TUs that actually *reference* the symbol. The
                          linker keeps a static copy only in TUs that use
                          it (unused statics are dropped), so the realistic
                          duplication is size * (ref_tu_count - 1).
    """
    # header -> spelling -> list of per-TU records
    by_symbol = defaultdict(lambda: defaultdict(list))
    for tu_findings in findings_per_tu:
        for rec in tu_findings:
            by_symbol[rec["header"]][rec["spelling"]].append(rec)

    rows = []
    for header, symbols in sorted(by_symbol.items()):
        for spelling, recs in sorted(symbols.items()):
            first = recs[0]
            local = first["local_static_bytes"]
            # distinct TUs that instantiate this symbol
            tus = sorted({r["tu"] for r in recs})
            tu_count = len(tus)
            ref_tus = sorted({r["tu"] for r in recs if r.get("referenced")})
            ref_tu_count = len(ref_tus)
            wasted = local * max(ref_tu_count - 1, 0) if local > 0 else 0
            rows.append(
                {
                    "header": header,
                    "symbol": spelling,
                    "kind": first["kind"],
                    "decl_line": first["decl_line"],
                    "local_static_bytes": local,
                    "tu_count": tu_count,
                    "ref_tu_count": ref_tu_count,
                    "tus": tus,
                    "ref_tus": ref_tus,
                    "wasted_bytes": wasted,
                }
            )

    rows.sort(key=lambda r: r["wasted_bytes"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    global _VAR_DECL, _STATIC, _FUNCTION_DECL, _DECL_REF_EXPR, _STATIC_ASSERT
    global _ARRAY_TYPE, _ENUM_CONSTANT_DECL, _EXTERNAL, _TRANSLATION_UNIT

    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--compile-db", metavar="PATH", help="compile_commands.json to scan")
    src.add_argument(
        "--files", nargs="+", metavar="FILE", help="specific files to scan (uses --args)"
    )
    ap.add_argument(
        "--args",
        nargs=argparse.REMAINDER,
        default=[],
        help="extra clang args for --files mode (put this LAST; everything after it is passed through)",
    )
    ap.add_argument("--out", default="", help="write findings JSON to PATH")
    ap.add_argument("--csv", default="", help="write findings CSV to PATH")
    ap.add_argument(
        "--no-safety", action="store_true", help="skip Part B constant-expression check"
    )
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument(
        "--only", metavar="SUBSTR", default="",
        help="only scan compile-db entries whose source path contains SUBSTR (case-sensitive)",
    )
    args = ap.parse_args()

    ci = _init_cindex()
    _VAR_DECL = ci.CursorKind.VAR_DECL
    _STATIC = ci.StorageClass.STATIC
    _FUNCTION_DECL = ci.CursorKind.FUNCTION_DECL
    _DECL_REF_EXPR = ci.CursorKind.DECL_REF_EXPR
    _STATIC_ASSERT = ci.CursorKind.STATIC_ASSERT
    _ARRAY_TYPE = ci.TypeKind.CONSTANTARRAY
    _ENUM_CONSTANT_DECL = ci.CursorKind.ENUM_CONSTANT_DECL
    _EXTERNAL = ci.LinkageKind.EXTERNAL
    _TRANSLATION_UNIT = ci.CursorKind.TRANSLATION_UNIT

    index = ci.Index.create()

    if args.compile_db:
        jobs = load_compile_db(args.compile_db)
        if not jobs:
            print("No usable entries in compile db", file=sys.stderr)
            return 1
        if args.only:
            jobs = [j for j in jobs if args.only in j[0]]
            if not jobs:
                print(f"--only '{args.only}' matched no entries", file=sys.stderr)
                return 1
        print(f"Loaded {len(jobs)} translation units from {args.compile_db}", file=sys.stderr)
    else:
        jobs = [(os.path.abspath(f), list(args.args)) for f in args.files]

    findings_per_tu = []
    parsed = 0
    for src_file, raw_args in jobs:
        if not os.path.exists(src_file):
            continue
        clang_args = sanitize_args(raw_args)
        try:
            tu = index.parse(src_file, args=clang_args)
        except Exception as e:
            if args.verbose:
                print(f"parse error {src_file}: {e}", file=sys.stderr)
            continue
        if not tu.cursor:
            continue
        parsed += 1
        # A header file is one that the source itself is a header; also flag
        # definitions located under lib/main (vendored) generically.
        def is_header_fn(loc):
            return _is_header_path(loc) or "/lib/main/" in (loc or "")

        findings_per_tu.append(_find_internal_linkage_in_header(tu, is_header_fn))
        if args.verbose and parsed % 50 == 0:
            print(f"parsed {parsed}/{len(jobs)}", file=sys.stderr)

    rows = aggregate(findings_per_tu)
    print(f"Parsed {parsed}/{len(jobs)} TUs; {len(rows)} internal-linkage-in-header symbols", file=sys.stderr)

    if args.no_safety:
        for r in rows:
            r["safety"] = "skipped"
    else:
        # Part B: for each flagged symbol, does any TU use it in a
        # constant-expression context? One AST walk per TU over the full
        # symbol set, rather than one walk per symbol.
        all_spellings = {r["symbol"] for r in rows}
        const_spellings = set()
        for src_file, raw_args in jobs:
            if not os.path.exists(src_file):
                continue
            clang_args = sanitize_args(raw_args)
            try:
                tu = index.parse(src_file, args=clang_args)
            except Exception:
                continue
            if not tu.cursor:
                continue
            const_spellings |= safety_scan_tu(tu, all_spellings)
        for r in rows:
            r["safety"] = (
                "keep, needs constant-expression"
                if r["symbol"] in const_spellings
                else "safe to extern"
            )

    # Report: worst offenders first, only ones with real size or any TU dup
    reportable = [r for r in rows if r["wasted_bytes"] > 0 or r["tu_count"] > 1]
    print("\n=== Static-linkage header duplication findings ===")
    print(f"{'wasted':>9} {'size':>7} {'TUs':>4} {'refTUs':>6}  header:symbol")
    for r in reportable[:60]:
        loc = f"{r['header']}:{r['decl_line']}"
        print(
            f"{r['wasted_bytes']:>9} {r['local_static_bytes']:>7} {r['tu_count']:>4} {r['ref_tu_count']:>6}  "
            f"{loc}  {r['symbol']}  [{r['safety']}]"
        )
    if len(reportable) > 60:
        print(f"... {len(reportable) - 60} more (see --out for all)")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)
        print(f"Wrote {args.out}", file=sys.stderr)
    if args.csv:
        with open(args.csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "header", "symbol", "kind", "decl_line",
                    "local_static_bytes", "tu_count", "ref_tu_count",
                    "wasted_bytes", "safety",
                ],
            )
            w.writeheader()
            for r in rows:
                row = {k: r[k] for k in w.fieldnames}
                w.writerow(row)
        print(f"Wrote {args.csv}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
