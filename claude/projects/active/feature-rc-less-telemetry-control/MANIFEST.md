# Manifest: feature-rc-less-telemetry-control

Index of everything belonging to this project. Design-phase only — no code, no branch yet.

**Verify with:** `python3 claude/projects/project_ops.py audit`

## In-repo

| Path | Purpose |
|------|---------|
| `summary.md` | Status, scope, gate |
| `todo.md` | Task list |
| `design.md` | Full design: GCS/datalink-heartbeat failsafe on the PX4/ArduPilot `FS_GCS` model |
| `MANIFEST.md` | This index |

## Status

Design complete; **not yet assigned**, awaiting user go-ahead. The gate is SITL failsafe testing, not a security review — the security review request was cancelled (see Mail).

Confirmed finding behind the project: INAV has no GCS failsafe today; failsafe is 100% RX-loss driven.

## Git

None yet. When work starts, branch from the base given by `claude/developer/scripts/git/new-branch.sh` — do not hardcode a base branch.

## Upstream PRs

None.

## Mail

Role mailboxes are the system of record. `claude/*/email/` is gitignored — these exist only on this machine.

| Path | What |
|------|------|
| `claude/developer/email/sent/2026-07-22-1430-review-request-gcs-datalink-failsafe.md` | Security review request |
| `claude/security-analyst/email/inbox-archive/2026-07-22-1430-review-request-gcs-datalink-failsafe-CANCELLED.md` | Same request, cancelled |

## Memory

None specific to this project.

## External

None. This project does **not** have a counterpart under `inav_development/mydev/branch/`.

## Relationship to other projects

Builds on `mavlink_multiport3` as a base. Per the scope boundary recorded in `active/mavlink-multiport/summary.md`, that does **not** make it part of the multiport project.
