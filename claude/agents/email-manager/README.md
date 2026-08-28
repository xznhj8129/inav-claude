# email-manager Agent Tools

**Purpose:** Permanent tools and scripts for the `email-manager` agent (`.claude/agents/email-manager.md`).

## Scripts

### `claude/agents/email-manager/simhash.py` — shared near-match implementation
**Purpose:** Single source of truth for the 64-bit simhash + hamming-distance
helpers used by both `email_ops.py audit` (routine delivery audit) and
`scripts/near_match_audit.py` (investigation tool), so the two always agree
on what counts as a near-match. Stdlib only.

**Created:** 2026-08-26, with the near-match audit enhancement
(`undelivered-email-audit-2026-08-26` project).

### `claude/agents/email-manager/scripts/sync_sent_from_received.py` — resolve verified near-match pairs
**Purpose:** Copies the recipient's received copy over the sender's stale
`sent/` copy for a list of near-match pairs, making them byte-identical so
the routine audit stops flagging them. Direction is received → sent because
these pairs arise when the sender edited the message after send — the
recipient's copy is what was actually seen/acted on. Pre-overwrite `sent/`
copies are backed up (email dirs are gitignored, so this preserves them).

**Usage:**
```bash
python3 claude/agents/email-manager/scripts/sync_sent_from_received.py <pairs-file>
# pairs-file lines: "<sent-path>|<received-path>"
```

**Created:** 2026-08-26, used to resolve the 8 verified near-match pairs of
the undelivered-email audit (backups in
`claude/projects/active/undelivered-email-audit-2026-08-26/sent-backup-2026-08-26/`).

### `claude/agents/email-manager/scripts/near_match_audit.py` — near-match & reverse-direction audit
**Purpose:** Companion to `email_ops.py audit` for the Phase-0 sanity-check
of undelivered-mail findings (`undelivered-email-audit-2026-08-26` project).
`email_ops.py audit` matches by **exact SHA-256** — if a delivered copy was
slightly modified (archive stamp, header edit, revision update, whitespace/
line-ending change), it's flagged "undelivered" even though it WAS received.
This tool finds those hash-mismatch pairs and also answers the reverse
question: which received emails have no matching sent copy anywhere.

**What it reports:**
- **A. Sent w/o received, WITH near-match copy** — likely delivered-then-modified pairs (false positives of the exact audit)
- **B. Sent w/o received, NO near-match** — stronger candidates for genuinely never-received
- **C. REVERSE: received files with no matching sent copy anywhere** (incl. legacy `archive/`, `outbox-archive/`)

**Method:** dependency-free 64-bit **simhash** (SHA-256 token hashing) +
hamming distance (default ≤ 6) over whitespace-normalized lowercase text;
byte-hash lookups cached so it runs in seconds on the full tree.

**Usage:**
```bash
python3 claude/agents/email-manager/scripts/near_match_audit.py [--min-sim 6] [--limit N] [--no-reverse]
```

**Sample result (2026-08-26 run):** 8 of the 53 flagged emails had near-match
copies in the recipient's tree (e.g. `2026-02-14-0230-completed-discord-qa-kb-stage2.md`
byte-identical but for whitespace → pure false positive; `2026-08-26-1545-task-review-pr11785-terrain-agl-ram.md`
delivered as an older revision, since revised in `sent/`). Full output saved
to `claude/projects/active/undelivered-email-audit-2026-08-26/near-match-audit-output.txt`.

**Created:** 2026-08-26, for Phase 0 of the undelivered-email audit.

### `claude/agents/email-manager/email_ops.py` (lives there, not here)
**Purpose:** Atomic, verified `send` / `archive` / `audit` / `audit-if-due`
operations for the agent's "Send Email", "Archive Processed Message", and
"Periodic Delivery Audit" steps. Every write is re-read and hashed against
its source before the operation can report success.

**Near-match tolerance (2026-08-26):** `audit` now treats a message as
delivered — reporting it under `## Near-matches (presumed delivered,
hamming ≤ 6)` instead of flagging it — when no byte-identical copy exists
but a copy in the recipient's tree is within `NEAR_MATCH_MAX_HAMMING` (6)
simhash bits. This covers delivered-then-modified copies (archive stamp,
header edit, revision update, whitespace) without re-delivering them.
Imports simhash from `simhash.py` in the same directory (runs correctly
when invoked by path, e.g. `python3 claude/agents/email-manager/email_ops.py`).

**Usage:**
```bash
python3 claude/agents/email-manager/email_ops.py send <sender-role> <recipient-role> <filename>.md
python3 claude/agents/email-manager/email_ops.py archive <role> <filename>.md
python3 claude/agents/email-manager/email_ops.py audit [--fix]
python3 claude/agents/email-manager/email_ops.py audit-if-due [--fix]
```

Lives in `claude/projects/` (not here) so it can mirror `project_ops.py`'s
pattern and location. See its module docstring for full behavior.

**Created:** 2026-08-23, fixing `fix-email-outbox-not-cleared-after-delivery`.
A hand-chained, unverified version of the "Send Email" step produced two
independent bugs: stale duplicate drafts left in a since-removed `outbox/`
folder, and — far more seriously — several completion reports (one with a
CRITICAL flight-safety finding) that were recorded as sent in `sent/` but
silently never reached the recipient's `inbox/` at all, undetected for 2+
days. `email_ops.py` closes the whole failure class by making every
operation re-verify its own result and fail loudly instead of reporting
success on a partial sequence. See
`claude/projects/active/fix-email-outbox-not-cleared-after-delivery/summary.md`.

## Why there's no `outbox/` anymore

`outbox/` ("drafts awaiting delivery") modeled a real-email concept —
delivery that can be delayed or fail (network down, recipient's mail
server unreachable) — that doesn't exist in this system: delivery here is
just copying a file into a local directory that always exists. Nothing
was ever legitimately staged there; every outbox file found in practice
was either a stale leftover of a message already delivered, or a
genuinely-lost message, i.e. a bug artifact either way.

Worse, an outbox-based "check for undelivered mail" can only ever catch a
message that was staged in `outbox/` and then mishandled *from there*. The
more severe of the two bugs above never touched `outbox/` — it went
`sent/` straight to (missing) `inbox/` — so that whole check design was
structurally incapable of catching it. `outbox/` was removed 2026-08-23
and replaced with `email_ops.py audit`, which checks the thing that
actually matters: for every message in a role's `sent/`, does a
byte-identical copy exist anywhere in the recipient's email tree, parsed
from the message's own `**To:**` header? This catches both failure modes
and depends on nothing having been staged anywhere first.

## Weekly audit flag

`audit-if-due` only runs the actual audit if
`claude/local-data/email-manager/last-audit-timestamp.txt` is missing or
its recorded timestamp is more than 7 days old (`AUDIT_INTERVAL_DAYS` in
`email_ops.py`); otherwise it's a no-op that reports when the audit last
ran. The timestamp lives in the file's *content* (not its filesystem
mtime — mtime isn't reliable across git checkouts). Safe to call on every
email-manager invocation.

**On a first-ever or long-overdue audit run**, expect a backlog of older
undelivered mail to surface at once. **Do not blindly `--fix` a large
backlog** — some of it may predate the current inbox/inbox-archive
delivery convention, or already have been handled by some other means
(read directly from `sent/`, discussed live, etc.). Blindly re-delivering
old, already-resolved items into a live inbox is the exact shape of the
2026-08-02 incident this project exists to prevent (5 stale files nearly
re-triggered already-merged PRs). Investigate and fix recent/live findings
immediately; escalate an old backlog to the manager for case-by-case
triage rather than mass-`--fix`ing it. On routine weekly runs (a handful
of new issues since last week, all recent by definition), `--fix` is safe
and appropriate.
