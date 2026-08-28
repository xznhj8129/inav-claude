# static-linkage-audit

AST-based audit tool for **static-linkage data duplication in headers** —
the fifth sub-project of the RAM Reduction Program.

## The problem

When a header defines a function or object with internal (`static`)
linkage, every `.c` file that includes the header gets its own private copy:
of the function *and* of any local `static` array/struct/table inside it.
The linker can't merge these because each is a distinct internal-linkage
symbol. `inline` is not the cause — `static` is; `inline` is orthogonal and
usually harmless. A plain-text grep for `"static inline"` misses the worst
cases because the linkage often arrives through a macro:

```c
/* lib/main/MAVLink/protocol.h (normal build): */
#define MAVLINK_HELPER static      /* the literal string "static inline"
                                      never appears at the call site */
```

Confirmed real-world example this tool is built to catch:
`mavlink_get_msg_entry()` in `lib/main/MAVLink/mavlink_helpers.h` defines a
3,732-byte (312-entry) local CRC table with `static` linkage via the
`MAVLINK_HELPER` macro; it is included by two firmware translation units
(`mavlink_runtime.c`, `mavlink_routing.c`) that actually call it, so the
binary carries **2 × 3,732 = 7,464 duplicated bytes** on every
MAVLink-enabled board.

## What it does

The tool parses translation units with **libclang** (macro-aware), then:

- **Part A (scanner):** finds functions/objects with internal linkage whose
  definition lives in a header; walks each for local `static` variables and
  computes their byte size via libclang's type layout; cross-references how
  many translation units instantiate the header content (`tu_count`) and how
  many actually *reference* the symbol from their own code (`ref_tu_count`);
  reports `size × (ref_tu_count − 1)` as the realistic wasted bytes.
- **Part B (safety):** for each flagged candidate, checks whether it is used
  in a compile-time constant expression (static initializer, array bound,
  `_Static_assert`, enum constant). Those get `keep, needs
  constant-expression`; everything else is `safe to extern` — meaning the
  header declaration can be turned into an `extern` declaration with a
  single definition in a `.c` file.

`tu_count` vs `ref_tu_count` matters: a static function in a header is
compiled into every TU that includes it, but the linker (with
`-ffunction-sections`/`--gc-sections` and the compiler's unused-symbol
elimination) keeps a copy only in TUs whose own code actually uses it. The
manager's `arm-none-eabi-nm` measurement (2 copies of `mavlink_message_crcs`)
matches `ref_tu_count`, not `tu_count` (8 for the MAVLink helpers under
SITL).

## Requirements

- Python 3.9+
- `pip install libclang` (bundles a matching libclang shared library; the
  tool prefers the bundled one automatically)
- A `compile_commands.json` for the codebase you want to audit (CMake with
  `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`; for INAV SITL:
  `cmake -S . -B build_sitl_cc -DSITL=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON`).
  Build-time generated headers (e.g. `settings_generated.h`) must exist —
  run the project's own generator if configure alone doesn't create them.

## Usage

```bash
# Full scan from a compile database:
python3 audit_static_linkage.py \
    --compile-db inav2/build_sitl_cc/compile_commands.json \
    --out findings.json --csv findings.csv

# Scan a subset of TUs (fast iteration):
python3 audit_static_linkage.py \
    --compile-db inav2/build_sitl_cc/compile_commands.json \
    --only "/mavlink/" --out mavlink_findings.json

# Scan specific files with explicit flags (no compile db needed);
# --args must come LAST (everything after it is passed to clang verbatim):
python3 audit_static_linkage.py \
    --files src/main/mavlink/mavlink_runtime.c src/main/mavlink/mavlink_routing.c \
    --out manual.json --args -Isrc/main -Ilib/main/MAVLink

# Skip the (slower) Part B safety pass:
python3 audit_static_linkage.py --compile-db build/compile_commands.json --no-safety
```

Output columns (CSV/JSON):

| field | meaning |
|-------|---------|
| `header` | header the symbol is defined in |
| `symbol` | function or object name |
| `kind` | `function` or `object` |
| `decl_line` | definition line in the header |
| `local_static_bytes` | total size of local `static` data inside the symbol |
| `tu_count` | TUs whose compilation instantiates the header content |
| `ref_tu_count` | TUs whose own code references the symbol (linker-kept copies) |
| `wasted_bytes` | `local_static_bytes × (ref_tu_count − 1)` |
| `safety` | `safe to extern` or `keep, needs constant-expression` |

## Interpretation for the MAVLink fix

The top finding on a MAVLink-enabled build is:

```
wasted  size  TUs refTUs  header:symbol
 4044  4044    8      2  lib/main/MAVLink/mavlink_helpers.h:518  mavlink_get_msg_entry  [safe to extern]
```

- `size` (4,044 B here) is the compiled CRC table for the dialect set in
  the audited build (SITL pulls the storm32 dialect's 337-entry
  `MAVLINK_MESSAGE_CRCS`); the manager's board build measured 3,732 B for
  its 312-entry set — the tool reports what the given compile database
  actually compiles.
- `ref_tu_count = 2` matches the nm measurement of two
  `mavlink_message_crcs` symbols: only `mavlink_runtime.c` and
  `mavlink_routing.c` call `mavlink_get_msg_entry()` from their own code.
- `safety = safe to extern`: nothing uses the CRC table as a compile-time
  constant, so the upstream `MAVLINK_SEPARATE_HELPERS` mechanism (an extern
  declaration in `protocol.h` + one compiled `mavlink_helpers.c`) applies.

## Testing

```bash
python3 test/test_audit.py
```

Self-tests cover: macro-hidden `static` detection (`MAVLINK_HELPER`),
local-static byte accounting, duplication cost across 2 TUs, trivial
accessors reporting 0 bytes, and the constant-expression safety flag.
