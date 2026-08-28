# Active Projects Index

This file tracks **active** projects only (TODO, IN PROGRESS, BACKBURNER, BLOCKED).

**Last Updated:** 2026-08-26
**Active:** 3 | **Backburner:** 0 | **Blocked:** 0

> **Completed projects:** See [completed/INDEX.md](completed/INDEX.md) — this archive is inherited from the previous owner (sensei-hacker) and predates this checkout.
> **Blocked projects:** See `blocked/` directory
>
> **When completing a project:**
> 1. Move directory from `active/` to `completed/`
> 2. Remove entry from this file
> 3. Add entry to `completed/INDEX.md`
>
> **When blocking a project:**
> 1. Move directory from `active/` to `blocked/`
> 2. Update entry in this file with 🚫 BLOCKED status
> 3. Note what is blocking progress

---

## Status Definitions

| Status | Description |
|--------|-------------|
| 📋 **TODO** | Project defined but work not started |
| 🚧 **IN PROGRESS** | Actively being worked on |
| 🚫 **BLOCKED** | Waiting on external dependency (user reproduction, hardware, etc.) |
| ⏸️ **BACKBURNER** | Paused, will resume later (internal decision) |
| ❌ **CANCELLED** | Abandoned, not pursuing |

| Indicator | Meaning |
|-----------|---------|
| ✉️ **Assigned** | Developer has been notified via email |
| 📝 **Planned** | Project created but developer not yet notified |

---

> **New here?** See [../../ORIENTATION.md](../../ORIENTATION.md) for the project system, layout and gotchas.

## Active Projects

### 📋 no-rc-control-program

**Status:** TODO (planning only) | **Type:** Feature | **Priority:** MEDIUM
**Created:** 2026-08-23 | **Assignee:** Developer 📝

No-RC (nav-only / headless) control for INAV: Pilot vs Command control mode, telemetry-link heartbeat failsafe, MC autolaunch, mode-availability rules. Single design doc covers everything.

**Directory:** `active/no-rc-control-program/`
**Design:** `design.md`

---

### 🚧 mavlink-multiport

**Status:** IN PROGRESS | **Type:** Feature (multi-PR upstream program) | **Priority:** HIGH
**Created:** 2026-08-03 (work began 2026-07-11) | **Assignee:** Developer

Refactor INAV MAVLink from a single-port telemetry emitter into a multi-port, multi-peer stack with per-port config and routing, plus the feature set on top: message-interval streams, protocol/capability negotiation, mission transfer, command/guided control, MSP-over-MAVLink tunnel. Shipped upstream as a stacked PR program.

**Base definition:** `mavlink_multiport3` is the finalized state of `maintenance-10.x` after complete merging of mavlink_multiport and all connex fixes — an integration base, not a feature branch. Projects that branch from it are **not** part of this project.

**Merged:** [#11712](https://github.com/iNavFlight/inav/pull/11712) · [#11713](https://github.com/iNavFlight/inav/pull/11713) · [#11714](https://github.com/iNavFlight/inav/pull/11714) · [#11715](https://github.com/iNavFlight/inav/pull/11715) · [#11716](https://github.com/iNavFlight/inav/pull/11716) · [#11738](https://github.com/iNavFlight/inav/pull/11738)
**Open, awaiting merge (in stack order):** [#11717](https://github.com/iNavFlight/inav/pull/11717) 6/7 → [#11718](https://github.com/iNavFlight/inav/pull/11718) 7/7 → [#11731](https://github.com/iNavFlight/inav/pull/11731) reconnect-refine

**Directory:** `active/mavlink-multiport/`
**Repository:** inav (fork `origin`=xznhj8129/inav) | **Spec:** `active/mavlink-multiport/pr/SPLIT_SPEC.md` (stale — describes 6 PRs, 7 were built)

---

### 📋 port-dualrx-onto-mavlink-multiport3

**Status:** TODO | **Type:** Feature (port/refresh of stale branch) | **Priority:** MEDIUM
**Created:** 2026-07-24 | **Assignee:** Developer 📝

Port the experimental **Dual RX fallback** feature (primary/secondary receiver, automatic failover, OSD indicator, failsafe-aware selection) onto the current `mavlink_multiport3` base. Source `origin/dualrx` is only 3 commits on a ~948-commit-stale merge-base, so this is a **re-port/rebase with conflict resolution, not a fast-forward**. Firmware + configurator port; deliverable is branch builds + `rx_rx_unittest` green + finalized PR **draft** and branch ready to push — **no PR opened** (user sends manually).

**Note:** Developer filed a completion report on 2026-07-24 (`manager/email/inbox/2026-07-24-1430-completed-port-dualrx-mavlink_multiport3.md`) — branches built, reviewed and pushed to the fork. Status above not yet advanced pending user confirmation.

**Directory:** `active/port-dualrx-onto-mavlink-multiport3/`
**Repository:** inav (fork `origin`=xznhj8129/inav) | **Branch:** `feature/dualrx` from `mavlink_multiport3`
**Source:** `origin/dualrx` (tip `95d968c8`) + artifacts also in `inav_development/mydev/branch/dualrx/` (external, diverged — see MANIFEST)

---

---
