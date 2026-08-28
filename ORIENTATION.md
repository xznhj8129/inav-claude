# Orientation

Start here if you've never seen this repo before. Written 2026-08-03.

`README.md` tells you how to *install* this thing. This file tells you what it *is*, what's actually in it right now, and the handful of non-obvious facts that will otherwise waste your first day.

---

## 1. What this repo is

`inav-claude` is a **tracking and workflow harness** for INAV development, not the place code gets written. It holds project records, task/role scaffolding, developer guides, skills and hooks. The firmware itself lives in sibling checkouts.

It was built by a previous owner (sensei-hacker) and inherited. That single fact explains most of the oddities you'll find — see §7.

## 2. The neighbourhood

Sibling directories, all under the same `GitRepos/` parent:

| Directory | What it is |
|-----------|-----------|
| `inav-claude/` | **This repo.** Tracking harness. Git. |
| `inav-claude/inav/` | INAV firmware checkout (C). Its own git repo. Where firmware branches live. |
| `inav-claude/inav-configurator/` | Configurator checkout (JS/Electron). Its own git repo. |
| `inav-claude/mspapi2/` | MSP protocol library used by test rigs. |
| `../inav_development/` | **A separate working tree.** Its own `inav/`, `inav-configurator/`, `inav-sitl-bench`, `docs/`, roadmaps, and a per-feature scratch area at `mydev/branch/<feature>/`. Not a git repo at top level. |

> **Rule: do not move, copy out of, or edit anything under `inav_development/`.** It holds overlapping copies of some project files that have diverged in *both* directions, so any automatic reconciliation destroys work. Reference it read-only. The divergences are documented per-project in the manifests.

## 3. What we actually have — three projects

All active work, as of 2026-08-03:

### `mavlink-multiport` — 🚧 in progress, the big one

Rebuilds INAV's MAVLink from a single-port telemetry emitter into a multi-port, multi-peer stack (per-port config, routing), then layers on message-interval streams, protocol/capability negotiation, mission transfer, command/guided control, and an MSP-over-MAVLink tunnel.

Shipped upstream as a **stack of PRs**, not one branch:

- **Merged:** #11712, #11713, #11714, #11715, #11716, plus SITL build fix #11738
- **Open, must merge in this order:** #11717 (6/7) → #11718 (7/7) → #11731 (reconnect refinement)

**`mavlink_multiport3` is the finalized state of `maintenance-10.x` after the complete merging of mavlink_multiport and all connex fixes.** It is an *integration base*, not a feature branch. Regenerate it with the project's own `scripts/regen-mavlink_multiport3.sh` — it's a static pointer and can't follow its inputs.

### `port-dualrx-onto-mavlink-multiport3` — 📋 branches pushed, no PR

Dual RX fallback: primary/secondary receiver with automatic failover. Ported across ~948 commits of drift onto `mavlink_multiport3`. Firmware and configurator branches are built, reviewed and pushed to the fork; **PRs deliberately not opened** — the owner sends those manually.

⚠️ Two live issues, both recorded in the project's `notes/next-steps.md`:
- **P1 is a real bug in pushed code** — MSP-over-CRSF replies go out the primary port regardless of which link the request arrived on, silently crossing the two links.
- Logic-condition ID **63 collides** with an upstream renumber and must move to 64.
- Nothing in this port is hardware-verified.

### `feature-rc-less-telemetry-control` — 📋 design only

A GCS/datalink-heartbeat failsafe on the PX4/ArduPilot `FS_GCS` model — a second, independent liveness source alongside RC-link failsafe. INAV has none today; failsafe is 100% RX-loss driven. Design is written; not started; gate is SITL failsafe testing.

## 4. The project system

**One directory per project. Everything project-specific lives in it.**

```
claude/projects/<status>/<project-name>/
├── MANIFEST.md      # index of EVERYTHING — mandatory
├── summary.md       # status, scope, current state
├── todo.md
├── notes/           # devlogs, design decisions, research
├── pr/              # PR bodies, specs
├── tests/           # project test scripts
├── scripts/         # project-specific tooling
└── artifacts/       # diffs, binaries, captured data
```

Subdirectories exist only when the project has that kind of content.

`<status>` is one of `active/`, `blocked/`, `backburner/`, `completed/` — a project's directory **moves** between them as its status changes. That's why the manifest matters more than the path.

### MANIFEST.md is the thing to read

It indexes every file in the directory *plus everything a directory can't hold*:

- git branches, per repo, with tip commits and merged/outstanding state
- upstream PR numbers and status
- mail paths
- memory slugs
- external references (including the `inav_development/` counterparts and how they diverge)

If you want to know "what is there and where," this is the file. One per project.

### The guarantee

```bash
python3 claude/projects/project_ops.py audit
```

Prints `ALL CLEAN` or names the problem. It enforces:

- every file in a project dir is listed in that project's `MANIFEST.md`
- every project has a manifest
- no directory sits in `claude/developer/workspace/` without an owning project
- INDEX.md entries, directories and counts all agree

Use `project_ops.py` for lifecycle changes (`complete`, `block`, `backburner`, `resume`, `cancel`) — it moves the directory and updates both indexes atomically. Doing it by hand causes drift.

## 5. Things that deliberately live outside project directories

Not everything can be siloed. Each is pointed to from the manifests.

| What | Where | Why it can't move |
|------|-------|-------------------|
| Memory | `~/.claude/projects/<slug>/memory/` | The harness loads it from that path each session |
| Mail | `claude/<role>/email/{inbox,sent,inbox-archive}/` | Role mailbox system. **Gitignored** — local to one machine only |
| Repo locks | `claude/locks/` | Cross-project mutex by design |
| Reference docs | `claude/developer/docs/` | Datasheets and indexes serving many projects |
| Shared tooling | `claude/developer/scripts/` | e.g. JSBSim SITL scripts used by any project |
| Branches | `inav/`, `inav-configurator/` | They're git refs, not files |

`claude/developer/workspace/` is **scratch only**. Anything left there without an owning project gets reported as an orphan.

## 6. Day one

```bash
# What exists
cat claude/projects/INDEX.md

# Everything about one project
cat claude/projects/active/mavlink-multiport/MANIFEST.md

# Prove nothing is missing
python3 claude/projects/project_ops.py audit

# Query project status
python3 claude/projects/project_manager.py stats
```

The harness asks you to pick a role (Manager / Developer / Release Manager / Security Analyst) and read that role's README under `claude/<role>/`. Manager tracks and assigns; Developer implements. In practice this is a single-user setup now, so the role split is lighter than the docs imply.

## 7. Non-obvious things that will bite you

**Ownership.** The repo has ~435 commits, none by the current owner. **Anything in git HEAD is the previous owner's; anything untracked is the current owner's.** Do not judge by dates in filenames — inherited files all share one clone-time mtime, and the harness backdates document names.

**`claude/projects/completed/`** holds 110 archived projects and 242 index entries. They are **all inherited**, kept deliberately as a frozen historical archive. They are not this owner's work and are not maintained. Don't mine them for current state.

**Mail is gitignored.** `claude/*/email/` never leaves the machine it was written on. Manifest mail references are local paths, not durable artifacts.

**Two trees, diverged.** See §2. `inav_development/mydev/branch/<feature>/` mirrors some project material with newer edits in places. Never auto-merge.

**INAV's cmake breaks in git worktrees.** Build off-tree using a `--shared` clone instead.

**Docs drift.** Several guides described a layout that hadn't existed for months. If a doc and the filesystem disagree, trust the filesystem and fix the doc.

## 8. What's not done

- Three upstream PRs awaiting review/merge, strictly ordered (§3)
- The dualrx P1 bug and the LC-63→64 renumber, unfiled as their own projects
- `pr/SPLIT_SPEC.md` is **stale** — it describes a 6-PR stack; 7 branches were actually built, with `02-headers` split out shifting everything after it
- Two SITL test rigs (`sanity`, `ports`) are blocked by a stale harness: wrong `workdir` and renamed mspapi2 methods
- The dualrx port has had no hardware verification
- Nothing from the recent reorganisation is committed
