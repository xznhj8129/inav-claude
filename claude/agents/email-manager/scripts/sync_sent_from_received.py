#!/usr/bin/env python3
"""
Brief: Sync sender's sent/ copy to match the recipient's received copy for
       a list of near-match email pairs (received version is authoritative —
       the recipient saw/acted on it; the sent/ copy was edited after send).
Usage: python3 sync_sent_from_received.py <pairs-file>
       pairs-file lines: "<sent-path>|<received-path>"
What problem this solves: After the exact-hash audit flagged near-match
       pairs (same filename, slightly different content), the sent/ copy is
       stale vs. what was actually delivered. Copying received -> sent makes
       the pair byte-identical so future audits stop flagging it.
When to use it: Post-audit cleanup of verified near-match pairs. Only ever
       run on pairs explicitly confirmed as delivered-then-modified.
"""
import hashlib
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
BACKUP = REPO / "claude" / "projects" / "active" / "undelivered-email-audit-2026-08-26" / "sent-backup-2026-08-26"

def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: sync_sent_from_received.py <pairs-file>", file=sys.stderr)
        return 1
    pairs = []
    for line in Path(sys.argv[1]).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sent, received = line.split("|")
        pairs.append((REPO / sent.strip(), REPO / received.strip()))

    ok = fail = skipped = 0
    for sent, received in pairs:
        if not received.is_file():
            print(f"FAIL: received copy missing: {received.relative_to(REPO)}")
            fail += 1
            continue
        if not sent.is_file():
            print(f"FAIL: sent copy missing: {sent.relative_to(REPO)}")
            fail += 1
            continue
        if sha256(sent) == sha256(received):
            print(f"SKIP (already identical): {sent.relative_to(REPO)}")
            skipped += 1
            continue
        # Back up the pre-overwrite sent copy (email dirs are gitignored)
        rel = sent.relative_to(REPO)
        backup_dst = BACKUP / str(rel).replace("/", "__")
        backup_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sent, backup_dst)
        # Copy received -> sent, then verify byte-identical
        shutil.copy2(received, sent)
        if sha256(sent) != sha256(received):
            print(f"FAIL: verification mismatch after copy: {rel}")
            fail += 1
            continue
        print(f"OK: {rel}  <-  {received.relative_to(REPO)}  (backup: {backup_dst.relative_to(REPO)})")
        ok += 1

    print(f"\nResult: {ok} synced, {skipped} already identical, {fail} failed")
    return 1 if fail else 0

if __name__ == "__main__":
    sys.exit(main())
