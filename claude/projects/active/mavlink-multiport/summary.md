# Project: MAVLink Multiport

**Status:** 🚧 IN PROGRESS
**Priority:** HIGH
**Type:** Feature (multi-PR upstream program)
**Created:** 2026-08-03 (work began 2026-07-11)
**Repository:** inav (fork `origin` = xznhj8129/inav, PR target `upstream` = iNavFlight/inav)

## Overview

Refactor INAV's MAVLink implementation from a single-port telemetry emitter into a multi-port, multi-peer stack with per-port configuration and routing, then build the feature set on top of it: message-interval streams, protocol/capability negotiation, mission transfer, command/guided control, and MSP-over-MAVLink tunneling.

Delivered upstream as a stack of chunky PRs rather than one branch, per `SPLIT_SPEC.md`.

## What `mavlink_multiport3` is

**`mavlink_multiport3` is the finalized state of `maintenance-10.x` after the complete merging of mavlink_multiport and all connex fixes.** It is an integration base, not a feature branch. Other projects branch from it; that does not make them part of this project.

Verified 2026-08-03: `mavlink_multiport3` = `upstream/maintenance-10.x` + the 8 commits still outstanding here (PR-6's 2, PR-7's 4, reconnect-refine's 1, and the SITL scheduler fix which has since merged).

## Scope

**In scope — everything mavlink_multiport and its connex fixes:**

- The `mav/01`–`mav/07` stacked PR program and its spec/PR bodies
- MAVLink reconnect/statustext detection work
- Connex fixes surfaced by this work (e.g. the SITL scheduler preprocessor fix)
- Companion changes in inav-configurator and mspapi2
- Source material in `notes/` and the PR program in `pr/`

**Out of scope — separate projects, even though they branch off `mavlink_multiport3`:**

- `port-dualrx-onto-mavlink-multiport3` (Dual RX fallback) and its P1–P7 follow-ups
- `feature-rc-less-telemetry-control` (GCS/datalink heartbeat failsafe)

Building on the integration base is not membership in this project.

## Current state (verified 2026-08-03)

### Merged upstream

| Branch | PR | Contents |
|--------|----|----|
| `mav/01-sitl-fixes` | [#11712](https://github.com/iNavFlight/inav/pull/11712) | SITL load accounting, MAVLink-RX feature gate, X-Plane fixes |
| `mav/02-headers` | [#11713](https://github.com/iNavFlight/inav/pull/11713) | Regenerated STorM32 headers + `generate.sh` |
| `mav/03-core` | [#11714](https://github.com/iNavFlight/inav/pull/11714) | Modular move, multi-port + per-port settings, routing, half-duplex etiquette |
| `mav/04-streams-protocol` | [#11715](https://github.com/iNavFlight/inav/pull/11715) | `SET_MESSAGE_INTERVAL`, `SYSTEM_TIME`, `REQUEST_MESSAGE`, PING/TIMESYNC, capability replies, HIGH_LATENCY2 |
| `mav/05-mission` | [#11716](https://github.com/iNavFlight/inav/pull/11716) | Mission transfer state machine, persistence/restore, `MISSION_CURRENT` |
| `fix/sitl-scheduler-dup-preprocessor` | [#11738](https://github.com/iNavFlight/inav/pull/11738) | Unbalanced `SITL_BUILD` block in `taskSystem()` breaking SITL build |

Earlier merged MAVLink groundwork (pre-split): #11060 lib update, #11061 gcs_nav, #11062 systemid, #11103 sitl_ports_cfg.

### Outstanding — all three have OPEN PRs awaiting review/merge

| PR | Branch | Tip | Ahead | Contents |
|----|--------|-----|-------|----------|
| [#11717](https://github.com/iNavFlight/inav/pull/11717) (6/7) | `mav/06-command-guided` | `3efee9d1b` | +2 | Arm/disarm, RTH via temporary `BOXNAVRTH` source, LAND, DO_SET_HOME via waypoint 0, DO_SET_MODE, guided position target, MSPv2 cmds, GCSN OSD |
| [#11718](https://github.com/iNavFlight/inav/pull/11718) (7/7) | `mav/07-tunnel` | `2a16c7861` | +6 | MSP-over-MAVLink TUNNEL + `msp_serial` seams, smoke test, user docs. Stacks on 06. |
| [#11731](https://github.com/iNavFlight/inav/pull/11731) | `mav/reconnect-refine` | `9a4d4197e` | +7 | Per-peer reconnect route-table tracking + 10s snapshot rate limit. Stacks on 07. |

All three OPEN and non-draft as of 2026-08-03, last touched 2026-07-26. All pushed to `origin`. Rebased 2026-07-25 onto trunk `bd8b9adfd` after the #11595 enum collision; range-diff clean apart from the renumber; all three MERGEABLE at that point.

**Merge order matters:** 6/7 → 7/7 → reconnect, in stack order.

### Verification at last rebase (2026-07-25)

- SITL links with `-Werror` at both stack levels
- Unit suite 222/222 at 6/7, 227/227 at 7/7 (`mavlink_unittest` 90/90)
- Still pending: X-Plane live LAND-mission flight (simple controller only; autoland approach path untested)

## Known issues

- **`SPLIT_SPEC.md` has drifted from reality.** The spec describes a **6**-PR stack (`02-core`, `03-streams-protocol`, `04-mission`, `05-command-guided`, `06-tunnel`); the branches actually built and merged are **7**, with `02-headers` split out and everything after it shifted down one. The file→PR map in §2 is stale. Reconcile before using the spec to plan the remaining PRs.
- **`mav/reconnect-statustext` (`0d5a7b8ce`) is superseded but must be kept** — its original content was folded into `mav/04` as `b88447c45`, and the PR comment links this branch. Do not delete; the refinement lives on as #11731.
- **Stale test harness blocks two SITL rigs.** `src/test/mavlink/sanity` + `ports` configs use `workdir: inav/cmake` (doubles under repo-root `WORKSPACE_ROOT`), and the sanity harness calls mspapi2 methods that were renamed or removed (`set_arm_state`→`set_armed`, `set_rth`→`activate_rth`, `set_land`→`activate_landing`; `set_home`/`get_nav_roi`/`set_nav_roi` absent). Sanity + ports rigs cannot run until the harness is resynced to mspapi2's `mavlink_multiport2` branch.
- `artifacts/changes.diff` is a 4 MB artifact; decide whether it is still needed now that PRs 1–5 have merged.

## Knock-on effect on a dependent project

The 2026-07-25 restack renumbered `LOGIC_CONDITION_ACTIVATE_RTH` 61→62 and `ACTIVATE_LANDING` 62→63 (yielding to upstream #11595, which took 61). This collides with the out-of-scope dualrx work: `port-dualrx-onto-mavlink-multiport3` added `LOGIC_CONDITION_RX_SELECT_OVERRIDE = 63` and `63: "Select RX link"` in the configurator's `js/logicConditionOperators.js`. **Both must move to 64.** Tracked there, not here — noted only because this project caused it.

## Artifacts

All project material lives in this directory. **See `MANIFEST.md` for the complete index**, including git branches, upstream PRs, memory files and external pointers.

- `notes/` — `DEVLOG.md` (64 KB), `NOTES.md` (design decisions), `CHANGELOG.md`, `MAVLINK_MULTIPORT2.md`, `MavlinkMulti.md` (symlink to the Obsidian plan note)
- `pr/` — `SPLIT_SPEC.md`, `PR-01`…`PR-07` (`.md` + `-body.md`), `PR_DRAFT.md`
- `tests/` — `test_land_mission.py`, `test_reconnect_{statustext,refinements}.py`
- `scripts/` — `regen-mavlink_multiport3.sh`, `carve_gtest_cases.py`
- `artifacts/` — `changes.diff` (4 MB), `configurator_changes.diff`, `mavlink_multiport2-eeprom.bin` (required by the reconnect rigs)
- **Historical branches:** `mavlink_multiport2` (`aaaa30848`, the pre-split monolith), 10 `backup/pre-*` checkpoints from the fold/fix5/5merge/11738 operations

## Success Criteria

- [ ] PR-6 (`mav/06-command-guided`) opened and merged upstream
- [ ] PR-7 (`mav/07-tunnel`) opened and merged upstream
- [ ] Reconnect refinement opened and merged upstream
- [ ] Companion inav-configurator and mspapi2 changes landed
- [ ] `SPLIT_SPEC.md` reconciled with the as-built 7-branch stack
- [ ] Stale branches pruned (`mav/reconnect-statustext`, `backup/pre-*`, `mavlink_multiport2`) once their content is upstream

## Related

- **Out-of-scope dependents:** `active/port-dualrx-onto-mavlink-multiport3/`, `active/feature-rc-less-telemetry-control/`
- **Base branch:** `mavlink_multiport3` (integration base, see definition above)
