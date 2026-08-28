#!/usr/bin/env python3
"""
Email Operations - Atomic, verified email lifecycle operations

Prevents the email-manager agent's hand-chained cp/rm/mv steps from ever
reporting success on a write that didn't actually land, by performing each
operation and then re-reading and hashing the result before returning.

Written for fix-email-outbox-not-cleared-after-delivery. Two independent
bugs were traced to the same failure shape: an LLM agent (email-manager
runs on Haiku) hand-chaining filesystem operations across multiple
locations with no atomicity and no verification.
  - Bug 1 (2026-08-02): the old "Send Email" step never removed a delivered
    draft from the sender's outbox/, so every send that used outbox/ left a
    permanent orphan there, which the old undelivered-mail check then
    misreported as stuck mail.
  - Bug 2 (2026-08-23, more severe): 6 developer completion reports for
    review-pr11553-vtol-transition (one with a CRITICAL flight-safety
    finding) were recorded as sent (present in developer/email/sent/) but
    never reached the manager's inbox at all. The workflow had no step
    that verified the inbox copy actually landed before reporting
    "Status: DELIVERED", so a failed or skipped copy was indistinguishable
    from a real one.

outbox/ itself was removed 2026-08-23 (per Ray, mid-investigation): this
system delivers by copying a file into a directory that always exists
locally, so there is no real scenario where a message is "composed but
not yet deliverable" the way there is in real email (network down,
recipient's server unreachable) - outbox/ never modeled anything real.
Worse, an outbox-based check can only ever catch a message that was
staged in outbox/ and mishandled from there; Bug 2 never touched outbox/
at all, so that entire class of check structurally could not have caught
the more serious bug. `audit` replaces it with a check that actually
matches the real failure mode: for every message in a role's sent/, parse
who it was addressed to and confirm a byte-identical copy exists in that
recipient's inbox somewhere - independent of whether anything was ever
staged anywhere first.

See claude/projects/active/fix-email-outbox-not-cleared-after-delivery/
summary.md for the full investigation.

Commands:
    send <sender-role> <recipient-role> <filename>
        Requires the message already drafted at
        claude/<sender-role>/email/sent/<filename> (write it there first,
        e.g. with the Write tool). Copies it to the recipient's inbox/ and
        verifies the copy is byte-identical. Raises loudly and leaves no
        partial state on any failure. Idempotent: re-running against an
        already-delivered message is a no-op success, not an error.
        Refuses to overwrite an inbox file whose content differs from the
        sent copy (that is what `update` is for).

    update <sender-role> <recipient-role> <filename>
        Like `send`, but overwrites an existing inbox copy whose content
        differs from the sent copy — for amending an already-delivered
        message (e.g. a manager adding an UPDATE section to a task
        assignment after delivery). The sent copy is authoritative: this
        command is the only way a differing inbox copy gets replaced.
        Copies claude/<sender-role>/email/sent/<filename> over the
        recipient's inbox/<filename> and verifies the result is
        byte-identical, raising loudly and leaving no partial state on any
        failure. Idempotent: re-running against an already-current inbox
        copy is a no-op success, not an error.

    archive <role> <filename>
        Moves claude/<role>/email/inbox/<filename> to inbox-archive/,
        verified: copies, confirms the copy is byte-identical, only then
        removes the inbox original.

    audit [--fix]
        Runs the delivery audit now, regardless of when it last ran, and
        records the run time in the audit flag file (see audit-if-due).
        For every message in every role's sent/, parses its "**To:**"
        header and confirms a byte-identical copy exists in that
        recipient's inbox/ or inbox-archive/. A message whose only match
        is a NEAR copy (simhash hamming distance <= NEAR_MATCH_MAX_HAMMING
        — i.e. the recipient's copy was slightly modified after send, e.g.
        archive stamp, header edit, revision update) is presumed delivered
        and reported separately, not flagged as an issue. Only messages
        with no copy at all (exact or near) are reported as undelivered.
        With --fix, attempts to redeliver each truly-missing message via
        the same verified `send` path (safe: send() is idempotent) and
        reports what got fixed vs. what still needs manual attention (e.g.
        an unparseable/unknown recipient). Near-matches are never
        re-delivered — they are presumed already received.

    audit-if-due [--fix]
        Runs `audit` only if the audit flag file
        (claude/agents/email-manager/data/last-audit-timestamp.txt) is
        missing or older than AUDIT_INTERVAL_DAYS (7). Otherwise prints
        when the audit last ran and does nothing. Cheap to call on every
        email-manager invocation - it's a no-op the other 6 days a week.
"""

import hashlib
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from simhash import hamming, simhash

ROLES = ["manager", "developer", "release-manager", "security-analyst"]

# Near-match tolerance for the delivery audit. A sent message is treated as
# delivered (not flagged) if a copy in the recipient's email tree differs
# only by at most NEAR_MATCH_MAX_HAMMING bits in its 64-bit simhash — i.e.
# the recipient's copy was slightly modified after send (archive stamp,
# header edit, revision update, whitespace). Exact hash matches always win.
NEAR_MATCH_MAX_HAMMING = 6

# How role names appear in a message's "**To:**"/"**From:**" header text,
# mapped to the lowercase-hyphenated directory slug used in file paths.
DISPLAY_NAME_TO_ROLE = {
    "manager": "manager",
    "developer": "developer",
    "release manager": "release-manager",
    "release-manager": "release-manager",
    "security analyst": "security-analyst",
    "security-analyst": "security-analyst",
}

TO_HEADER_RE = re.compile(r"^\*\*To:\*\*\s*(.+?)\s*$", re.MULTILINE)

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_DIR = REPO_ROOT / "claude"

# Local per-user data lives under claude/local-data/ (gitignored)
AUDIT_FLAG_PATH = CLAUDE_DIR / "local-data" / "email-manager" / "last-audit-timestamp.txt"
AUDIT_INTERVAL_DAYS = 7


class EmailOpsError(RuntimeError):
    pass


def _validate_role(role: str) -> None:
    if role not in ROLES:
        raise EmailOpsError(f"unknown role {role!r} — must be one of {ROLES}")


def _validate_filename(filename: str) -> None:
    if "/" in filename or "\\" in filename or filename in ("", ".", ".."):
        raise EmailOpsError(f"invalid filename {filename!r} — must be a bare filename, no path separators")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _email_dir(role: str, folder: str) -> Path:
    return CLAUDE_DIR / role / "email" / folder


def _verified_copy(src: Path, dst: Path) -> None:
    """Copy src -> dst, then re-read dst and confirm it is byte-identical to
    src. Raises EmailOpsError (removing any partial dst) on any mismatch —
    the check the old hand-chained cp/rm/mv steps never had, which let a
    failed or skipped copy be reported as a successful send.
    """
    if not src.is_file():
        raise EmailOpsError(f"source file not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    if not dst.is_file():
        raise EmailOpsError(f"copy silently failed — destination missing after write: {dst}")
    if _sha256(dst) != _sha256(src):
        dst.unlink(missing_ok=True)
        raise EmailOpsError(f"copy verification failed — content mismatch, removed bad copy: {dst}")


def cmd_send(sender: str, recipient: str, filename: str) -> int:
    _validate_role(sender)
    _validate_role(recipient)
    _validate_filename(filename)
    if sender == recipient:
        raise EmailOpsError("sender and recipient must differ")

    sent_path = _email_dir(sender, "sent") / filename
    inbox_path = _email_dir(recipient, "inbox") / filename

    if not sent_path.is_file():
        raise EmailOpsError(
            f"expected message already drafted at {sent_path} — "
            f"write it there first (e.g. with the Write tool), then call send"
        )

    if inbox_path.exists():
        if _sha256(inbox_path) == _sha256(sent_path):
            print(f"Already delivered (identical copy exists): {inbox_path}")
        else:
            raise EmailOpsError(
                f"refusing to overwrite existing inbox file with different content: {inbox_path}"
            )
    else:
        _verified_copy(sent_path, inbox_path)
        print(f"Delivered: {sent_path} -> {inbox_path}")

    # Final end-to-end verification before this can be reported as success.
    if _sha256(inbox_path) != _sha256(sent_path):
        raise EmailOpsError(f"post-send verification failed: {inbox_path} != {sent_path}")

    print("STATUS: DELIVERED")
    return 0


def cmd_update(sender: str, recipient: str, filename: str) -> int:
    """Overwrite the recipient's inbox copy with the sender's sent copy,
    verifying byte-identical afterwards. For amending an already-delivered
    message (e.g. a manager updating a task assignment after delivery).
    Unlike `send`, this may overwrite an existing inbox file whose content
    differs from the sent copy — the sent copy is authoritative. Idempotent:
    re-running against an already-current inbox copy is a no-op success.
    """
    _validate_role(sender)
    _validate_role(recipient)
    _validate_filename(filename)
    if sender == recipient:
        raise EmailOpsError("sender and recipient must differ")

    sent_path = _email_dir(sender, "sent") / filename
    inbox_path = _email_dir(recipient, "inbox") / filename

    if not sent_path.is_file():
        raise EmailOpsError(
            f"expected message already drafted at {sent_path} — "
            f"write it there first (e.g. with the Write tool), then call update"
        )

    if inbox_path.exists() and _sha256(inbox_path) == _sha256(sent_path):
        print(f"Already up to date (identical copy exists): {inbox_path}")
    else:
        _verified_copy(sent_path, inbox_path)
        print(f"Updated: {sent_path} -> {inbox_path}")

    # Final end-to-end verification before this can be reported as success.
    if _sha256(inbox_path) != _sha256(sent_path):
        raise EmailOpsError(f"post-update verification failed: {inbox_path} != {sent_path}")

    print("STATUS: UPDATED")
    return 0


def cmd_archive(role: str, filename: str) -> int:
    _validate_role(role)
    _validate_filename(filename)
    inbox_path = _email_dir(role, "inbox") / filename
    archive_path = _email_dir(role, "inbox-archive") / filename

    if not inbox_path.is_file():
        raise EmailOpsError(f"not found in inbox: {inbox_path}")
    if archive_path.exists():
        raise EmailOpsError(f"already exists in inbox-archive, refusing to overwrite: {archive_path}")

    _verified_copy(inbox_path, archive_path)
    inbox_path.unlink()
    if inbox_path.exists():
        raise EmailOpsError(
            f"archive succeeded but source removal failed — duplicate now exists: {inbox_path}"
        )

    print(f"Archived: {inbox_path} -> {archive_path}")
    print("STATUS: ARCHIVED")
    return 0


HEADER_BLOCK_RE = re.compile(r"^(.*?)(?=^##\s)", re.DOTALL | re.MULTILINE)


def _header_block(text: str) -> str:
    """The metadata block above the first '## ' section heading. Every
    template's real To:/From: fields live here; restricting the search to
    this block avoids matching an unrelated '**To:**' that happens to
    appear in a task's body (e.g. a file-move task with its own
    'Copy: .../ To: ...' pair deep in a subsection).
    """
    match = HEADER_BLOCK_RE.search(text)
    return match.group(1) if match else text


def _parse_recipients(text: str) -> list[str] | None:
    """Extract the role slug(s) a message is addressed to from its **To:**
    header (within the header block only). Returns None if there is no
    To: header at all (e.g. a Reminder — a note to self) or if none of
    the addressees are a recognized role (e.g. legacy free-text targets
    like "Project Records") — neither case is an audit finding, just not
    a role-routable message. Handles comma/slash/"and"-separated
    multi-recipients and strips a trailing parenthetical annotation
    (e.g. "Developer (timer output work)").
    """
    match = TO_HEADER_RE.search(_header_block(text))
    if not match:
        return None
    raw = re.sub(r"\s*\([^)]*\)\s*$", "", match.group(1)).strip()
    roles = [
        DISPLAY_NAME_TO_ROLE[token]
        for token in (t.strip().lower() for t in re.split(r"\s*(?:,|/| and )\s*", raw))
        if token in DISPLAY_NAME_TO_ROLE
    ]
    return roles or None


def _read_last_audit() -> datetime | None:
    if not AUDIT_FLAG_PATH.is_file():
        return None
    try:
        return datetime.fromisoformat(AUDIT_FLAG_PATH.read_text().strip())
    except ValueError:
        return None


def _write_last_audit(when: datetime) -> None:
    # Timestamp is stored in the file's *content*, not read back from its
    # mtime — mtime isn't reliable across git operations (checkout/clone
    # reset it to "now" regardless of when the content was last written).
    AUDIT_FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_FLAG_PATH.write_text(when.isoformat() + "\n")


def _build_recipient_index() -> dict[str, list]:
    """One pass over every role's email tree; returns role ->
    list of (path, sha256, simhash) for each .md file found (inbox/,
    inbox-archive/, and legacy archive/ + outbox-archive/ folders — a fixed
    folder list previously missed those and produced false "undelivered"
    positives on old mail). Built once per audit run so both the exact-hash
    and near-match checks are cheap lookups.
    """
    index: dict[str, list] = {}
    for role in ROLES:
        entries = []
        email_dir = CLAUDE_DIR / role / "email"
        if email_dir.is_dir():
            for p in email_dir.rglob("*.md"):
                data = p.read_bytes()
                entries.append((p, hashlib.sha256(data).hexdigest(),
                                simhash(data.decode(errors="replace"))))
        index[role] = entries
    return index


def cmd_audit(fix: bool) -> int:
    issues: list[str] = []
    fixed: list[str] = []
    near_matches: list[str] = []
    skipped_no_recipient = 0
    checked = 0

    recipient_index = _build_recipient_index()

    for sender in ROLES:
        sent_dir = _email_dir(sender, "sent")
        if not sent_dir.is_dir():
            continue
        for msg in sorted(sent_dir.glob("*.md")):
            text = msg.read_text(errors="replace")
            recipients = _parse_recipients(text)
            if recipients is None:
                skipped_no_recipient += 1  # no To: header, or none of its addressees are a known role
                continue

            msg_hash = _sha256(msg)
            msg_simhash = simhash(text)
            for recipient in recipients:
                if recipient == sender:
                    continue  # self-addressed (e.g. a note-to-self) — no cross-delivery expected

                checked += 1
                entries = recipient_index.get(recipient, [])

                # 1) Exact match: a byte-identical copy exists somewhere in
                #    the recipient's tree → delivered.
                if any(h == msg_hash for _, h, _ in entries):
                    continue

                # 2) Near match: a copy exists that differs only slightly
                #    (≤ NEAR_MATCH_MAX_HAMMING simhash bits) — recipient's
                #    copy was modified after send (archive stamp, header
                #    edit, revision update, whitespace). Presume delivered;
                #    report but don't flag, don't re-deliver.
                near = [p for p, _, s in entries
                        if hamming(msg_simhash, s) <= NEAR_MATCH_MAX_HAMMING]
                if near:
                    near_matches.append(
                        f"{msg.relative_to(REPO_ROOT)}: sent by {sender}, addressed to {recipient}, "
                        f"near-match (hamming ≤ {NEAR_MATCH_MAX_HAMMING}) in {recipient}'s tree: "
                        + ", ".join(str(p.relative_to(REPO_ROOT)) for p in near[:3])
                    )
                    continue

                description = (
                    f"{msg.relative_to(REPO_ROOT)}: sent by {sender}, addressed to {recipient}, "
                    f"no matching copy anywhere in {recipient}'s email tree"
                )
                if fix:
                    try:
                        cmd_send(sender, recipient, msg.name)
                        fixed.append(description)
                    except EmailOpsError as e:
                        issues.append(f"{description} — FIX FAILED: {e}")
                else:
                    issues.append(description)

    print(f"## Delivery audit: {checked} addressed messages checked "
          f"({skipped_no_recipient} skipped, no recipient header)")
    if near_matches:
        print(f"\n## Near-matches (presumed delivered, hamming ≤ {NEAR_MATCH_MAX_HAMMING}): {len(near_matches)}")
        for item in near_matches:
            print(f"  {item}")
    if fixed:
        print(f"\n## Fixed: {len(fixed)}")
        for item in fixed:
            print(f"  {item}")
    if issues:
        print(f"\n## ISSUES: {len(issues)}")
        for item in issues:
            print(f"  {item}")
    if not fixed and not issues:
        print("No delivery issues found.")

    _write_last_audit(datetime.now())
    return 1 if issues else 0


def cmd_audit_if_due(fix: bool) -> int:
    last = _read_last_audit()
    if last is not None:
        due_at = last + timedelta(days=AUDIT_INTERVAL_DAYS)
        if datetime.now() < due_at:
            print(f"Audit not due yet — last ran {last.isoformat()}, next due {due_at.isoformat()}.")
            return 0
    return cmd_audit(fix)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    command, *rest = args
    try:
        if command == "send":
            if len(rest) != 3:
                print("Usage: email_ops.py send <sender-role> <recipient-role> <filename>", file=sys.stderr)
                return 1
            return cmd_send(*rest)
        elif command == "update":
            if len(rest) != 3:
                print("Usage: email_ops.py update <sender-role> <recipient-role> <filename>", file=sys.stderr)
                return 1
            return cmd_update(*rest)
        elif command == "archive":
            if len(rest) != 2:
                print("Usage: email_ops.py archive <role> <filename>", file=sys.stderr)
                return 1
            return cmd_archive(*rest)
        elif command in ("audit", "audit-if-due"):
            if any(r != "--fix" for r in rest):
                print(f"Usage: email_ops.py {command} [--fix]", file=sys.stderr)
                return 1
            fix = "--fix" in rest
            return cmd_audit(fix) if command == "audit" else cmd_audit_if_due(fix)
        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            print(__doc__)
            return 1
    except EmailOpsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
