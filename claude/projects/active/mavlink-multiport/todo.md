# Todo: MAVLink Multiport

## Phase 1: Reconcile the spec (do first — blocks planning the rest)

- [ ] Update `SPLIT_SPEC.md` §1 stack table from 6 PRs to the as-built 7 branches
- [ ] Correct the §2 file→PR map for the `02-headers` shift
- [ ] Record merged PR numbers (#11712–#11716) against their branches in the spec

## Phase 2: Land the remaining stack (PRs already open — shepherd, don't re-open)

- [ ] #11717 (6/7, `mav/06-command-guided`) — respond to review, get merged
- [ ] #11718 (7/7, `mav/07-tunnel`) — merge after 6/7
- [ ] #11731 (`mav/reconnect-refine`) — merge after 7/7
- [ ] Re-verify mergeability after each upstream trunk move; restack if a new enum/ID collision lands
- [ ] X-Plane live LAND-mission flight test (autoland approach path still untested)
- [ ] Regenerate `mavlink_multiport3` via `regen-mavlink_multiport3.sh` after each tip change

## Phase 2b: Unblock the SITL test rigs

- [ ] Fix `src/test/mavlink/sanity` + `ports` configs: `workdir: inav/cmake` doubles under repo-root `WORKSPACE_ROOT`
- [ ] Resync sanity harness to mspapi2 `mavlink_multiport2` API (`set_armed`, `activate_rth`, `activate_landing`; handle absent `set_home`/`get_nav_roi`/`set_nav_roi`)
- [ ] Re-run sanity + ports rigs once unblocked

## Phase 3: Companions

- [ ] Land inav-configurator companion changes
- [ ] Land mspapi2 companion changes

## Phase 4: Cleanup

- [ ] KEEP `mav/reconnect-statustext` — content folded into `mav/04` (`b88447c45`) and the PR comment links the branch
- [ ] Delete `backup/pre-*` checkpoint branches once their content is upstream
- [ ] Delete `mavlink_multiport2` once fully superseded
- [ ] Decide the fate of `artifacts/changes.diff` (4 MB) now that PRs 1–5 have merged
- [ ] Commit the multiport tooling scripts (`regen-mavlink_multiport3.sh`, `carve_gtest_cases.py`)

## Completion

- [ ] All stack PRs merged upstream
- [ ] Spec matches what was actually shipped
- [ ] Stale branches pruned
