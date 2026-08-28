#!/usr/bin/env python3
"""
Brief: Near-match email audit — finds approximate (hash-mismatched) copies
       and reverse-direction orphans in the internal email system.
Usage: python3 claude/agents/email-manager/scripts/near_match_audit.py
Example: python3 claude/agents/email-manager/scripts/near_match_audit.py --min-sim 6

What problem this solves: The delivery audit (email_ops.py audit) matches by
       exact SHA-256 content hash. If a delivered copy was slightly modified
       (archive stamp, header edit, whitespace, re-save), it is flagged
       "undelivered" even though it WAS received — a false positive. This
       tool finds those approximate-match pairs. It also answers the reverse
       question the exact audit cannot: which received emails have NO
       matching sent copy anywhere (orphan received mail).

When to use it: Phase 0 sanity-check of the undelivered-email audit; any
       time you suspect hash-mismatch pairs rather than true delivery drops.

Method:
  - Direction 1 (sent w/o received): for every sent/ message addressed to a
    role with no byte-identical copy in that role's email tree, compare its
    64-bit simhash against every .md in the recipient's tree and report
    near-duplicates (hamming distance <= threshold, default 6).
  - Direction 2 (received w/o sent): for every .md in each role's
    inbox/inbox-archive/etc., check whether a byte-identical sent copy
    exists anywhere; report those that don't (reverse orphans).

Dependencies: stdlib only (hashlib, re, difflib, argparse) + the shared
       simhash module at claude/agents/email-manager/simhash.py (imported
       by both this tool and email_ops.py so they agree on near-match
       detection).
"""
import argparse
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

# Shared simhash implementation lives one level up (claude/agents/email-manager/)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simhash import hamming, simhash  # noqa: E402

# Path: claude/agents/email-manager/scripts/near_match_audit.py
# parents[0]=scripts, [1]=email-manager, [2]=agents, [3]=claude, [4]=repo
REPO = Path(__file__).resolve().parents[4]
CLAUDE = REPO / "claude"
ROLES = ["manager", "developer", "release-manager", "security-analyst"]

HEADER_BLOCK_RE = re.compile(r"^(.*?)(?=^## )", re.M | re.S)
TO_HEADER_RE = re.compile(r"^\*\*To:\*\*\s*(.+)$", re.M)
DISPLAY = {
    "manager": "manager",
    "developer": "developer",
    "release-manager": "release-manager",
    "release manager": "release-manager",
    "security-analyst": "security-analyst",
    "security analyst": "security-analyst",
}

# ---------------- hashing / simhash ----------------

def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def title_of(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


# ---------------- recipient parsing (mirrors email_ops.py) ----------------

def header_block(text: str) -> str:
    m = HEADER_BLOCK_RE.search(text)
    return m.group(1) if m else text


def parse_recipients(text: str):
    m = TO_HEADER_RE.search(header_block(text))
    if not m:
        return None
    raw = re.sub(r"\s*\([^)]*\)\s*$", "", m.group(1)).strip()
    roles = [DISPLAY[t.strip().lower()] for t in re.split(r"\s*(?:,|/| and )\s*", raw)
             if t.strip().lower() in DISPLAY]
    return roles or None


# ---------------- main ----------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-sim", type=int, default=6,
                    help="max simhash hamming distance to count as near-match (default 6)")
    ap.add_argument("--limit", type=int, default=0,
                    help="only analyze the first N flagged messages (default: all)")
    ap.add_argument("--no-reverse", action="store_true",
                    help="skip the reverse-direction (received w/o sent) check")
    args = ap.parse_args()

    # ---- Precompute: all sent hashes (role -> set), all received hashes ----
    sent_hashes: dict[str, set[str]] = {r: set() for r in ROLES}
    for sender in ROLES:
        sdir = CLAUDE / sender / "email" / "sent"
        if sdir.is_dir():
            sent_hashes[sender] = {sha256(q) for q in sdir.glob("*.md")}

    received_files: dict[str, list[Path]] = {r: [] for r in ROLES}
    received_hashes: dict[str, set[str]] = {r: set() for r in ROLES}
    for role in ROLES:
        rdir = CLAUDE / role / "email"
        if rdir.is_dir():
            files = [p for p in rdir.rglob("*.md") if "sent" not in p.parts]
            received_files[role] = files
            received_hashes[role] = {sha256(p) for p in files}

    all_sent_hashes = set().union(*sent_hashes.values()) if sent_hashes else set()

    # ---- Direction 1: sent without byte-identical copy ----
    flagged = []
    for sender in ROLES:
        sent_dir = CLAUDE / sender / "email" / "sent"
        if not sent_dir.is_dir():
            continue
        for msg in sorted(sent_dir.glob("*.md")):
            text = msg.read_text(errors="replace")
            recipients = parse_recipients(text)
            if not recipients:
                continue
            h = sha256(msg)
            for recipient in recipients:
                if recipient == sender:
                    continue
                if h not in received_hashes.get(recipient, set()):
                    flagged.append((sender, recipient, msg, text))

    if args.limit:
        flagged = flagged[: args.limit]

    print(f"## Flagged by exact audit (no byte-identical copy): {len(flagged)}\n")

    # Cache simhash per path so files are hashed at most once
    sh_cache: dict[str, int] = {}

    def sh_of(path: Path) -> int:
        key = str(path)
        if key not in sh_cache:
            sh_cache[key] = simhash(path.read_text(errors="replace"))
        return sh_cache[key]

    near = []
    none = []
    for sender, recipient, msg, text in flagged:
        rdir = CLAUDE / recipient / "email"
        if not rdir.is_dir():
            none.append((sender, recipient, msg, []))
            continue
        sh = simhash(text)
        cands = []
        for p in received_files.get(recipient, []):
            d = hamming(sh, sh_of(p))
            if d <= args.min_sim:
                cands.append((p, d))
        cands.sort(key=lambda x: x[1])
        if cands:
            near.append((sender, recipient, msg, cands))
        else:
            none.append((sender, recipient, msg, []))

    print(f"## A. Sent w/o received, WITH near-match copy in recipient tree: {len(near)}")
    print("   (likely hash-mismatch pairs — delivered then slightly modified)\n")
    for sender, recipient, msg, cands in near:
        print(f"### {msg.relative_to(REPO)}")
        print(f"    sent by {sender} -> {recipient}")
        for p, d in cands[:4]:
            print(f"    NEAR hamming={d}: {p.relative_to(REPO)}")
        print()

    print(f"## B. Sent w/o received, NO near-match at all: {len(none)}")
    print("   (stronger candidates for genuinely never-received)\n")
    for sender, recipient, msg, _ in none:
        print(f"    {msg.relative_to(REPO)}  ({sender} -> {recipient})")
    print()

    if args.no_reverse:
        return 0

    # ---- Direction 2: received without any matching sent copy ----
    print("## C. REVERSE: received files with NO matching sent copy anywhere\n")
    for role in ROLES:
        files = received_files.get(role, [])
        orphan = [p for p in files if sha256(p) not in all_sent_hashes]
        print(f"  {role}: {len(files)} received files, {len(orphan)} with no matching sent copy")
        for p in orphan[:15]:
            print(f"      {p.relative_to(REPO)}")
        if len(orphan) > 15:
            print(f"      ... and {len(orphan) - 15} more")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
