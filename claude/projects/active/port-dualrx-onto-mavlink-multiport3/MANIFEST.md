# Manifest: port-dualrx-onto-mavlink-multiport3

Index of everything belonging to this project inside `inav-claude`. Material in `inav_development/` is referenced, never moved or modified.

**Verify with:** `python3 claude/projects/project_ops.py audit`

## In-repo

### Root

| Path | Purpose |
|------|---------|
| `summary.md` | Status, scope, port outcome |
| `todo.md` | Task list |
| `MANIFEST.md` | This index |

### `notes/`

| Path | Purpose |
|------|---------|
| `next-steps.md` | P1–P7 follow-up backlog from the 2026-07-24 review. **P1 is a live bug**, see below |
| `session-state.md` | Session handoff state at the end of the port |
| `apply.log` | Log of the port application |

### `pr/`

| Path | Purpose |
|------|---------|
| `dual_rx_pr.md` | Firmware PR body. **Marked WIP** pending elaboration on switchover states, hysteresis/dwell, receiver configs and telemetry (P2/P3) |
| `dual_rx_configurator_pr.md` | Configurator PR body |

### `artifacts/`

| Path | Purpose |
|------|---------|
| `dualrx-source.diff` | Source diff of the original `origin/dualrx` feature |

## Open work — not yet its own project

`notes/next-steps.md` holds seven follow-ups. **P1 is a defect in pushed code**, introduced by this port in `a97c7fb81`:

> MSP-over-CRSF replies go out the primary port regardless of ingress link. `crsfDataReceive()` handles MSP frames from either link, but `crsfRxSendTelemetryData()` writes to a single file-scope `serialPort` set to the primary. Requests arriving on the secondary receiver are answered on the primary port, silently crossing the two links.

P2–P7: telemetry on both links · switchover model (hysteresis, dwell, authority link, bumpless transfer) · `RX:1`/`RX:2` OSD rename · blackbox link-state logging · arming/config-divergence/RAM · remaining 7 serial drivers instance-safe.

**Nothing in this port is hardware-verified.**

## Inherited defect from the multiport restack

`mavlink-multiport`'s 2026-07-25 restack renumbered upstream logic conditions, taking ID 63. This project added `LOGIC_CONDITION_RX_SELECT_OVERRIDE = 63` and `63: "Select RX link"` in the configurator's `js/logicConditionOperators.js`. **Both must move to 64.**

## Git

| Repo | Branch | Tip | State |
|------|--------|-----|-------|
| `inav` | `feature/dualrx` (from `mavlink_multiport3`) | `c88d5a248` | pushed to fork, **no PR opened** — user sends manually |
| `inav-configurator` | `feature/dualrx` (from `mavlink_multiport2`) | `2daaffe7` | pushed to fork, no PR opened |
| `inav` | `origin/dualrx` | `95d968c8` | original 3-commit source branch |

Commits on `feature/dualrx`: `a245eadd0` feature port + drift · `a97c7fb81` review fixes (PG_RX_CONFIG 13→14, failsafe-override gate, CRSF+SBUS instance-safe) · `c88d5a248` driver-group-aware guard.

## Mail

Role mailboxes are the system of record. `claude/*/email/` is gitignored — these exist only on this machine.

| Path | What |
|------|------|
| `claude/manager/email/sent/2026-07-24-1430-task-port-dualrx-onto-mavlink-multiport3.md` | Assignment |
| `claude/manager/email/sent/2026-07-24-1530-amendment-port-dualrx-configurator-scope.md` | Scope amendment |
| `claude/developer/email/inbox/2026-07-24-1430-task-port-dualrx-onto-mavlink-multiport3.md` | Assignment (delivered copy) |
| `claude/developer/email/inbox/2026-07-24-1530-amendment-port-dualrx-configurator-scope.md` | Amendment (delivered copy) |
| `claude/developer/email/sent/2026-07-24-1430-completed-port-dualrx-mavlink_multiport3.md` | Completion report |
| `claude/manager/email/inbox/2026-07-24-1430-completed-port-dualrx-mavlink_multiport3.md` | Completion report (delivered copy) |

## Memory

Loaded from `~/.claude/projects/-media-anon-WD2TB-…-inav-claude/memory/`; cannot live in the repo.

- `mavlink-multiport2-branch` — records the LC-63→64 knock-on affecting this project

## External — reference only, do not modify

`inav_development/` is a separate working tree. Files there are **not** managed by this project and must not be moved or edited from here.

| Path | Note |
|------|------|
| `GitRepos/inav_development/mydev/branch/dualrx/` | Parallel working copy, 13 files. **Diverged** — its `next-steps.md`, `session-state.md` and `dual_rx_pr.md` are newer (2026-07-28 vs 07-25), and it additionally holds `changes.diff`, `DEVLOG.md` and `old_deprecated/`. Both copies retained deliberately; unreconciled. |
