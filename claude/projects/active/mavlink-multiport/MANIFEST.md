# Manifest: mavlink-multiport

Index of everything belonging to this project. Nothing project-specific lives outside this directory except the externals listed at the bottom, which structurally cannot.

**Verify with:** `python3 claude/projects/project_ops.py audit`

## In-repo

### Root

| Path | Purpose |
|------|---------|
| `summary.md` | Status, scope boundary, current PR state |
| `todo.md` | Phased task list |
| `MANIFEST.md` | This index |

### `notes/` — design record

| Path | Purpose |
|------|---------|
| `DEVLOG.md` | 64 KB running development log, the primary narrative record |
| `NOTES.md` | Locked design decisions (tunnel addressing, command parity, LAND/RTH semantics) |
| `CHANGELOG.md` | User-facing change summary |
| `MAVLINK_MULTIPORT2.md` | Feature overview |
| `MavlinkMulti.md` | **Symlink** into the Obsidian vault — see Externals |

### `pr/` — the stacked-PR program

| Path | Purpose |
|------|---------|
| `SPLIT_SPEC.md` | Split spec: stack base, PR table, file→PR map. **Stale — describes 6 PRs, 7 were built** |
| `PR-01.md` | PR-1 working notes and ready-to-run commands |
| `PR-02.md` | PR-2 working notes |
| `PR-03.md` | PR-3 working notes |
| `PR-04.md` | PR-4 working notes |
| `PR-05-06-07.md` | Combined working notes for the last three levels |
| `PR-01-body.md` | GitHub PR body as submitted (#11712) |
| `PR-02-body.md` | GitHub PR body as submitted (#11713) |
| `PR-03-body.md` | GitHub PR body as submitted (#11714) |
| `PR-04-body.md` | GitHub PR body as submitted (#11715) |
| `PR-05-body.md` | GitHub PR body as submitted (#11716) |
| `PR-06-body.md` | GitHub PR body as submitted (#11717) |
| `PR-07-body.md` | GitHub PR body as submitted (#11718) |
| `PR_DRAFT.md` | Original single-PR draft, pre-split |

### `tests/`

| Path | Purpose |
|------|---------|
| `test_land_mission.py` | Live SITL LAND-mission rig (PR-5) |
| `test_reconnect_statustext.py` | Reconnect STATUSTEXT rig — **requires `artifacts/mavlink_multiport2-eeprom.bin`**, TCP 5762/5763 |
| `test_reconnect_refinements.py` | Per-peer tracking + rate-limit rig, same eeprom |

### `scripts/`

| Path | Purpose |
|------|---------|
| `regen-mavlink_multiport3.sh` | Regenerates the `mavlink_multiport3` integration branch. Run after any change to 07/reconnect/scheduler inputs — the branch is a static pointer and cannot auto-follow. |
| `carve_gtest_cases.py` | Carves `TEST_F` blocks out of `mavlink_unittest.cc` to stage tests per stack level |

### `artifacts/`

| Path | Purpose |
|------|---------|
| `changes.diff` | 4 MB full diff of the pre-split monolith |
| `configurator_changes.diff` | Companion configurator diff |
| `mavlink_multiport2-eeprom.bin` | SITL eeprom the reconnect rigs boot against (was `mydev/branch/mavlink_multiport2/`) |

## Git — `inav` (fork `origin` = xznhj8129/inav)

| Branch | Tip | State |
|--------|-----|-------|
| `mav/01-sitl-fixes` | `4e215a92a` | merged (#11712) |
| `mav/02-headers` | `1938750f5` | merged (#11713) |
| `mav/03-core` | `4f1907e98` | merged (#11714) |
| `mav/04-streams-protocol` | `b88447c45` | merged (#11715) |
| `mav/05-mission` | `42dbfc518` | merged (#11716) |
| `fix/sitl-scheduler-dup-preprocessor` | `fb1f045ff` | merged (#11738) |
| `mav/06-command-guided` | `3efee9d1b` | open (#11717) |
| `mav/07-tunnel` | `2a16c7861` | open (#11718) |
| `mav/reconnect-refine` | `9a4d4197e` | open (#11731) |
| `mav/reconnect-statustext` | `0d5a7b8ce` | **keep** — folded into `mav/04` as `b88447c45`; PR comment links it |
| `mavlink_multiport2` | `aaaa30848` | historical pre-split monolith |
| `mavlink_multiport3` | `a3ee2454a` | integration base, regenerable via `scripts/regen-mavlink_multiport3.sh` |
| `backup/pre-fold-04…07`, `backup/pre-fix5-06/07`, `backup/pre-5merge-06/07`, `backup/pre-11738-06/07` | — | 10 checkpoints, prunable once content is upstream |

## Upstream PRs — iNavFlight/inav

- **Merged:** #11712, #11713, #11714, #11715, #11716, #11738
- **Open, merge in this order:** #11717 (6/7) → #11718 (7/7) → #11731 (reconnect)
- **Earlier groundwork:** #11060, #11061, #11062, #11103

## Mail

Role mailboxes remain the system of record; these are this project's messages. Note `claude/*/email/` is gitignored — these files exist only on this machine.

- *(none — the multiport program predates this project's filing and was never assigned by email)*

## Memory

Loaded automatically from `~/.claude/projects/-media-anon-WD2TB-…-inav-claude/memory/`. Cannot live in the repo; the harness reads that path.

- `mavlink-multiport2-branch` — branch state, PR progress, restack history
- `mavlink-multiport2-design-decisions` — non-obvious decisions and build gotchas
- `inav-cmake-breaks-in-git-worktrees` — build off-tree with a `--shared` clone, not a worktree

## Externals

`inav_development/` is a separate working tree. Files there are **not** managed by this project and must not be moved or edited from here.

| What | Where | Note |
|------|-------|------|
| Obsidian plan note | `~/Sync/Obsidian/AI_SHARED/projects/software/inav-development/plans/MavlinkMulti.md` | Symlinked as `notes/MavlinkMulti.md`. **Repointed 2026-08-03** — the old target (`Vault/Projects/Software Projects/INAV/NewFeatures/`) no longer exists; the link had been dangling. |
| Parallel working copy | `GitRepos/inav_development/mydev/branch/mavlink_multiport2/` | 38 files. **Diverged in both directions** — see table below. Reference only; both copies retained deliberately, unreconciled. |
| Live test rigs | `GitRepos/inav_development/mydev/branch/mavlink_multiport2/mavlink_tests/` | Sweep configs, benchmark and runtime logs, `.waypoints`, `mav_multi_sweep.py`. Referenced by `pr/SPLIT_SPEC.md` §"imported the forgotten live harnesses". Not duplicated here. |
| Sub-repo checkouts | `inav/`, `inav-configurator/`, `mspapi2/` | Branches listed above |
| Repo lock | `claude/locks/inav.lock` | Cross-project mutex, shared by design |

### Divergence against the sibling copy (unreconciled, 2026-08-03)

| File | This silo | `mydev/branch/mavlink_multiport2/` | Newer |
|------|-----------|-----------------------------------|-------|
| `DEVLOG.md` | 65684 B, 07-11 | 65944 B, 07-20 — verified continuation of this copy | **sibling** |
| `CHANGELOG.md` | 6795 B, 07-12 | 6064 B, 07-11 | **this silo** |
| `PR_DRAFT.md` | 15013 B, 07-12 | 14041 B, 07-10 | **this silo** |
| `changes.diff` | 4040296 B, 07-11 | 4040286 B, 07-20 | **ambiguous** — larger here, newer there |
| `NOTES.md` | identical | identical | — |

Sibling-only files not present here: `RAS_A.md`, `msp_serial.diff`, `fc_diff.txt`, `mav.tlog`, `mav.tlog.raw`, `done`, `mavlink_tests/`.

## Deliberately shared, not owned by this project

- `claude/developer/scripts/testing/jsbsim/*.py` — general SITL tooling (see `jsbsim-sitl-testing` skill)
- `claude/developer/docs/` — datasheets and reference indexes
