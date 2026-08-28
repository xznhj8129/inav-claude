#!/usr/bin/env python3
"""
Brief: Resolve confirmed-received audit findings by copying the sender's
       sent/ copy into the recipient's email/inbox-archive/ (record copy).
Usage: python3 resolve_confirmed_received.py <pairs-file>
       pairs-file lines: "<sent-path>|<recipient-role>"  (blank/# = skipped)
What problem this solves: The delivery audit flags a sent message as
       "possibly undelivered" when no copy exists in the recipient's tree.
       When investigation confirms the recipient DID receive and act on it,
       the finding should be resolved by placing the archival copy in the
       recipient's inbox-archive/ (the audit scans that folder).
When to use it: After evidence-gathering confirms a flagged email was
       actually received and acted upon. Never use for unresolved/uncertain
       items — those stay flagged for case-by-case triage.
Safety: Refuses to overwrite an existing inbox-archive file whose content
       differs (a conflicting copy means the finding is not this simple).
       Every write is re-read and hash-verified before reporting success.
"""
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ROLES = {"manager", "developer", "release-manager", "security-analyst"}

def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: resolve_confirmed_received.py <pairs-file>", file=sys.stderr)
        return 1
    lines = [l.strip() for l in Path(sys.argv[1]).read_text().splitlines()
             if l.strip() and not l.strip().startswith("#")]
    ok = conflict = fail = already = 0
    for line in lines:
        if "|" not in line:
            print(f"SKIP (bad line): {line}")
            continue
        sent_part, recipient = (p.strip() for p in line.split("|", 1))
        if recipient not in ROLES:
            print(f"SKIP (unknown role): {line}")
            continue
        sent = REPO / sent_part
        if not sent.is_file():
            print(f"FAIL: sent copy missing: {sent_part}")
            fail += 1
            continue
        archive_dir = REPO / "claude" / recipient / "email" / "inbox-archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        dst = archive_dir / sent.name
        if dst.exists():
            if sha256(dst) == sha256(sent):
                print(f"ALREADY RESOLVED (identical copy present): {dst.relative_to(REPO)}")
                already += 1
                continue
            print(f"CONFLICT: differing file already in inbox-archive, refusing to overwrite: {dst.relative_to(REPO)}")
            conflict += 1
            continue
        dst.write_bytes(sent.read_bytes())
        if not dst.is_file() or sha256(dst) != sha256(sent):
            dst.unlink(missing_ok=True)
            print(f"FAIL: verification mismatch, removed bad copy: {dst.relative_to(REPO)}")
            fail += 1
            continue
        print(f"RESOLVED: {sent_part}  ->  {dst.relative_to(REPO)}")
        ok += 1
    print(f"\nResult: {ok} resolved, {already} already present, {conflict} conflicts, {fail} failed")
    return 1 if fail else 0

if __name__ == "__main__":
    sys.exit(main())
