#!/usr/bin/env python3
"""
Brief: Shared simhash implementation for email near-match detection.
Usage: from simhash import simhash, hamming
What problem this solves: The exact-hash delivery audit (email_ops.py audit)
       flags a message as "undelivered" when the recipient's copy was
       slightly modified after send (archive stamp, header edit, revision
       update, whitespace change). A 64-bit simhash (SHA-256 token hashing)
       with hamming-distance comparison finds those near-identical pairs so
       the audit can treat them as delivered instead of flagging them.
When to use it: Imported by email_ops.py (routine audit) and
       scripts/near_match_audit.py (investigation tool). Stdlib only.
"""
import hashlib
import re

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def simhash(text: str, bits: int = 64) -> int:
    """64-bit simhash over whitespace-split lowercase tokens. Stdlib-only."""
    v = [0] * bits
    for tok in _TOKEN_RE.findall(text.lower()):
        h = int(hashlib.sha256(tok.encode()).hexdigest()[:16], 16)
        for i in range(bits):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(bits):
        if v[i] > 0:
            out |= 1 << i
    return out


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")
