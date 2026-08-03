# mavlink_multiport2 → stacked PR split spec

**Date:** 2026-07-11
**Source branch:** `inav:mavlink_multiport2` @ `aaaa30848`
**Diff base used for all file lists:** `70af840d6` (the `maintenance-10.x` tip merged on 2026-06-08 — second parent of merge `dae745b18`)
**Decisions locked:** stage on xznhj8129 fork · stacked PRs opened together · ~6 chunky PRs · refactor bundled into PR-2 but isolated as its own first commit

---

## 0. Stack base

`origin/maintenance-10.x` has moved **47 commits** past `70af840` (buzzer unified output,
SITL Mac VLA fix, 9.1 merge-back, ADSB.md conflict-marker fix, ICM-42688P AAF fix, ...).

**Decision: base the stack on current `origin/maintenance-10.x`.** Drift is small and
unrelated to MAVLink; absorbing it now avoids an awkward re-merge after six PRs exist.
Known collision points with the drift: `docs/ADSB.md` (both sides fixed the same stale
conflict markers) and possibly `src/test/unit/platform.h`. Everything else transplants clean.

```bash
git fetch origin maintenance-10.x
STACK_BASE=origin/maintenance-10.x
```

## 1. The stack

| PR | Branch | Contents | Stacks on |
|----|--------|----------|-----------|
| 1 | `mav/01-sitl-fixes` | SITL load accounting, SITL MAVLink-RX feature gate, X-Plane motor/pitch-yaw/altitude fixes | base |
| 2 | `mav/02-core` | c1: **pure modular move** · c2: regenerated STorM32 headers + `generate.sh` · c3: multi-port + per-port settings · c4: routing + fixed AUTOPILOT1 identity · c5: half-duplex etiquette + MLRS/radio-status per-port handling | 1 |
| 3 | `mav/03-streams-protocol` | per-message `SET_MESSAGE_INTERVAL`, `SYSTEM_TIME`, `REQUEST_MESSAGE`, PING/TIMESYNC, protocol/capability replies, optional Standard Modes (`USE_MAVLINK_STANDARD_MODES`), HIGH_LATENCY2, GPS accuracy → `GPS_RAW_INT`, arming-disable + OSD STATUSTEXT de-spam | 2 |
| 4 | `mav/04-mission` | mission transfer state machine, staged upload/translation, persistence+restore, `MISSION_CURRENT`, `MISSION_ITEM_REACHED`, live mission tester | 3 |
| 5 | `mav/05-command-guided` | arm/disarm, RTH via `BOXNAVRTH`, LAND, DO_SET_HOME, DO_SET_MODE (RTL/pause), guided SET_POSITION_TARGET, loiter-radius override, MSPv2 cmds, PF ops 61/62, GCSN OSD, mode-change STATUSTEXT | 4 |
| 6 | `mav/06-tunnel` | MSP-over-MAVLink TUNNEL + `msp_serial` seams | 5 |

Companion PRs (separate repos, reference PR-5/PR-6): `mspapi2:mavlink_multiport2`,
`inav-configurator:mavlink_multiport2` (13 files).

Rule for every internal commit: **one concern per commit** — future upstream re-splitting
must be a cherry-pick, not surgery.

---

## 2. File → PR map (all 61 non-generated files + generated set)

Legend: `W` = whole file via `git checkout mavlink_multiport2 -- <path>` · `H` = hunk-level
carve via `git checkout -p` (or manual edit) · `S` = staged/cut-down version in this PR,
completed by later PR(s).

### PR-1 `mav/01-sitl-fixes`
| File | How | Notes |
|------|-----|-------|
| `src/main/scheduler/scheduler.c` | W | SITL busy/wall load accounting (SITL_BUILD-gated) |
| `src/main/target/SITL/target.h` | W | `USE_TELEMETRY_MAVLINK` + `USE_SERIALRX_MAVLINK` defines |
| `src/main/target/common.h` | H | only the SITL/flash-gate hunk; inspect — may also carry MAVLink defines belonging to PR-2 |
| `src/main/target/SITL/sim/xplane.c` | W | motor output w/ XITL, pitch/yaw signs, NED velocity, fake baro |
| `docs/SITL/SITL.md`, `docs/SITL/X-Plane.md` | W | |

### PR-2 `mav/02-core` (modularize → multiport → routing)
| File | How | Notes |
|------|-----|-------|
| `src/main/mavlink/mavlink_types.h` | S | strip mission/tunnel-facing types if any leak in |
| `src/main/mavlink/mavlink_internal.h` | S | **amputate** — see §3 |
| `src/main/mavlink/mavlink_runtime.c/.h` | S | **amputate** — see §3 |
| `src/main/mavlink/mavlink_ports.c/.h` | S | **amputate** tunnel resets — see §3 |
| `src/main/mavlink/mavlink_routing.c/.h` | W | clean, no forward refs found |
| `src/main/mavlink/mavlink_streams.c/.h` | S | keep streams/heartbeat/telemetry senders; defer interval-override + SYSTEM_TIME + STATUSTEXT-despam + HIGH_LAT internals to PR-3 |
| `src/main/mavlink/mavlink_modes.c/.h` | S | upstream mode tables move here (part of c1); Standard-Modes emission block deferred to PR-3 |
| `src/main/fc/fc_mavlink.c/.h` | S | dispatch skeleton; **amputate** cases — see §3 |
| `src/main/telemetry/mavlink.c/.h` | W | thin adapter (this is the -1468 file) |
| `src/main/telemetry/telemetry.c/.h` | H | multi-port claiming/iteration hunks |
| `src/main/rx/mavlink.h` | W | shared RX surface |
| `src/main/fc/settings.yaml` | H | `mavlink_port{1-4}_*` block only; later PRs add their settings hunks |
| `src/main/CMakeLists.txt` | H | add only the modules present at this level |
| `lib/main/MAVLink/**` (172 files) | W | own commit c2 "regenerate with STorM32 dialect"; needed for MLRS msg IDs |
| `lib/main/MAVLink/generate.sh` + `generate.bat` | W | same commit |
| `docs/Mavlink.md` | S | routing/multiport/half-duplex sections only |
| `docs/Settings.md` | H | regenerate per-PR from settings.yaml (don't carve by hand) |

### PR-3 `mav/03-streams-protocol`
| File | How | Notes |
|------|-----|-------|
| `src/main/mavlink/mavlink_streams.c` | S→complete | interval overrides, SYSTEM_TIME, PING/TIMESYNC handlers, STATUSTEXT de-spam state, HIGH_LATENCY2 |
| `src/main/mavlink/mavlink_modes.c` | S→complete | `USE_MAVLINK_STANDARD_MODES` block |
| `src/main/fc/fc_mavlink.c` | S→+cases | `PING`, `TIMESYNC`, `REQUEST_MESSAGE`/interval cases |
| `src/main/io/gps.c/.h`, `src/main/io/gps_ublox.c` | W | ellipsoid alt + speed/heading accuracy retention |
| `src/main/fc/settings.yaml` | H | high-latency / standard-modes settings hunks |
| `docs/Mavlink.md` | S→more | streams/intervals/high-latency sections |

### PR-4 `mav/04-mission`
| File | How | Notes |
|------|-----|-------|
| `src/main/mavlink/mavlink_mission.c/.h` | W | the 1317-line module, lands whole |
| `src/main/mavlink/mavlink_internal.h` | S→+fields | re-add `missionTransfer`, `lastMissionCurrentMs`, `missionCompleted`, `mavMissionTransfer` macro |
| `src/main/mavlink/mavlink_runtime.c` | S→+call | re-add `mavlinkMissionUpdate()` (was line 283) + include |
| `src/main/fc/fc_mavlink.c` | S→+cases | all `MISSION_*` dispatch cases |
| `src/main/navigation/navigation.c/.h` | H | ONLY `navigationConsumeWaypointReached()` + reached-latch hunks; rest is PR-5 |
| `src/main/CMakeLists.txt`, `src/test/unit/CMakeLists.txt` | H | |
| `src/test/mavlink/missions/**` (5 files) | W | live tester |
| `.gitignore` | W | results dir entry |
| `docs/Mavlink.md` | S→more | mission translation + lossiness warning |

### PR-5 `mav/05-command-guided`
| File | How | Notes |
|------|-----|-------|
| `src/main/mavlink/mavlink_command.c/.h` | W | 433-line command module |
| `src/main/mavlink/mavlink_guided.c/.h` | W | |
| `src/main/fc/fc_mavlink.c` | S→+cases | `COMMAND_LONG/INT` beyond upstream parity, `SET_POSITION_TARGET_*` |
| `src/main/fc/rc_modes.c/.h` | H | temporary box-source machinery (`BOXNAVRTH`/`BOXNAVPOSHOLD`) |
| `src/main/fc/fc_core.c/.h` | H | shared arming helpers |
| `src/main/navigation/navigation.c/.h` | H | `activateRTHMode()`, `activatePositionHoldMode()`, transient LAND, radius override |
| `src/main/navigation/navigation_private.h` | W | `gcsLoiterRadiusOverride` |
| `src/main/navigation/navigation_fixedwing.c` | W | 1-line radius consumer |
| `src/main/fc/fc_msp.c` | H | MSPv2 LAND/RTH/ARM/TIMESYNC + `SET_GLOBAL_TARGET` radius append |
| `src/main/msp/msp_protocol_v2_inav.h` | W | `0x2224/0x2225/0x2227/0x2228` |
| `src/main/programming/logic_condition.c/.h` | W | PF ops 61/62 |
| `src/main/io/osd.c` | W | GCSN flight-mode element |
| `src/main/fc/settings.yaml` | H | remaining hunks |
| `src/test/unit/rcdevice_unittest.cc` | W | +80 lines — verify why it changed (likely box-ID/rc_modes fallout); belongs with rc_modes change |
| `docs/Mavlink.md`, `docs/Programming Framework.md`, `docs/development/msp/**` | W/H | MSP docs regenerate |

### PR-6 `mav/06-tunnel`
| File | How | Notes |
|------|-----|-------|
| `src/main/fc/fc_mavlink.c` | S→complete | tunnel helpers (final lines ~13–133) + `TUNNEL` dispatch case |
| `src/main/mavlink/mavlink_internal.h` | S→complete | tunnel buffers/ports/ids fields + `mavTunnel*` macros |
| `src/main/mavlink/mavlink_ports.c` | S→complete | re-add tunnel state resets in configure/free |
| `src/main/msp/msp_serial.c/.h` | W | parser/encode/process seams (+111 lines) |
| `docs/Mavlink.md` | S→complete | tunnel section |

### Deliberately dropped from all PRs
`docs/ADSB.md` (−42: superseded by upstream drift commit `4ab116d22`).

---

## 3. PR-2 amputation list (the compilability contract)

**Invariant for PR-2 c1 (pure move):** the modular tree handles exactly the incoming-message
set and emits exactly the outgoing-message set that upstream `telemetry/mavlink.c` @
`70af840` did. Anything not in upstream's monolith gets amputated here and re-added by its
feature PR. Verify by diffing symbol lists:
`nm` both SITL builds → the MAVLink-related extern surface should match modulo renames.

Concrete cuts (line refs from `mavlink_multiport2` final tree):

1. **`mavlink_internal.h`**
   - cut lines ~105–107: `missionTransfer`, `lastMissionCurrentMs`, `missionCompleted` → PR-4
   - cut lines ~120–133: `mavTunnelMspPorts/RemoteSystemIds/RemoteComponentIds/ReplyPayloadBuf/FrameBuf` macros + backing fields, `mavMissionTransfer` macro → PR-6 / PR-4
2. **`mavlink_ports.c`**
   - cut lines ~33–35 and ~72–74 (tunnel `resetMspPort` + id resets in configure/free) → PR-6
3. **`mavlink_runtime.c`**
   - cut line ~283 `mavlinkMissionUpdate(...)` + `#include "mavlink/mavlink_mission.h"` → PR-4
4. **`fc_mavlink.c`**
   - cut tunnel helper block (lines ~13–133) + `case MAVLINK_MSG_ID_TUNNEL` (~428) → PR-6
   - cut `case MAVLINK_MSG_ID_MISSION_{CLEAR_ALL,COUNT,ITEM,ITEM_INT,REQUEST,REQUEST_INT,REQUEST_LIST,ACK}` (~386–405) → PR-4
   - cut `case MAVLINK_MSG_ID_SET_POSITION_TARGET_{LOCAL_NED,GLOBAL_INT}` (~411–414) → PR-5 (unless upstream monolith handled them — check base; if yes they stay with upstream behavior)
   - cut `#include mavlink_command.h / mavlink_guided.h` → PR-5
   - `COMMAND_LONG/INT` cases stay, but the command tables inside must be reduced to upstream parity; new commands arrive with PR-3 (intervals) and PR-5 (arm/RTH/LAND/home/mode)
   - cut `case MAVLINK_MSG_ID_PING` / `TIMESYNC` (~380–383) → PR-3
5. **`mavlink_streams.c`**
   - keep `mavlinkHandleIncomingHeartbeat` (~1209) and `mavlinkHandleIncomingRequestDataStream` (~1356) — upstream behavior
   - cut `mavlinkHandleIncomingPing` (~1226) / `mavlinkHandleIncomingTimesync` (~1247) → PR-3
   - cut interval-override table, SYSTEM_TIME sender, STATUSTEXT de-spam state, HIGH_LATENCY2 → PR-3
6. **`mavlink_modes.c`** — keep the moved upstream ArduPlane/Copter custom-mode maps; cut the
   `USE_MAVLINK_STANDARD_MODES` emission block → PR-3

**Watch for the reverse tendril:** anything in c3/c4 (multiport/routing) that only exists to
serve a later feature (e.g. per-port STATUSTEXT suppression state in the port struct) moves
with its feature, not with the struct. When amputating a struct field, grep the whole tree
for its name before deciding which PR re-adds it.

---

## 4. Test → PR map (`src/test/unit/mavlink_unittest.cc`, 3623 lines, ~90 cases)

The unittest file is **staged cumulatively**: each PR ships a version containing its own +
all prior sections. A test lands in the PR where the *last* of its dependencies lands.
`src/test/unit/CMakeLists.txt` and `platform.h` land at PR-2 with the harness.

| PR | Test cases (prefix match) |
|----|--------------------------|
| 2 | `SameSystemDifferentComponent*`, `RcChannelsOverride*`, `Mlrs*`, `RadioStatus*`, `AttitudeUsesRadians*`, `PositionReportsPositiveDown*`, `BatteryStatusDoesNotSend*`, `ParamRequestList*`, `BroadcastParamRequestList*`, `RequestDataStreamStopsStream`, `BroadcastRequestDataStream*` |
| 3 | `SetMessageInterval*`, `RequestMessage*`, `SystemTime*`, `PingRequest*`, `TimesyncRequest*`, `HeartbeatIntervalIsIndependent*`, `GpsRawReportsNativeAccuracy*`, `StatusText*`, `ArmingDisable*`, `GuidedAvailableModeIsNamedNonStandard`, `RequestProtocolVersion*`, `RequestAutopilotCapabilities*` |
| 4 | `Mission*` EXCEPT `MissionItemIntGuided*` and `LegacyGuidedMissionItem*` (incl. `MissionLandRetainsSuppliedPosition`, all upload/download/persist/cancel/out-of-order cases, `MissionItemReached*`, `MissionCurrent*`) |
| 5 | `ComponentArmDisarm*`, `DoSetMode*`, `ReturnToLaunch*`, `LandUsesNormal*`, `SetHome*`, `Takeoff*`, `CommandIntReposition*`, `CommandLongReposition*`, `BroadcastCommandLongReposition*`, `SetPositionTarget*`, `Broadcast*SetPositionTarget*`, `HeartbeatGuidedFlagRequiresValidGcs*`, `MissionItemIntGuided*`, `LegacyGuidedMissionItem*`, `CommandIntUnsupportedFrame*` |
| 6 | `Tunnel*` (5 cases) |

Per-level gtest filters:
```
PR2: --gtest_filter='*SameSystem*:*RcChannels*:*Mlrs*:*RadioStatus*:*Attitude*:*PositionReports*:*BatteryStatusDoes*:*ParamRequestList*:*RequestDataStream*'
PR3: PR2 + ':*Interval*:*RequestMessage*:*SystemTime*:*Ping*:*Timesync*:*GpsRaw*:*StatusText*:*ArmingDisable*:*ProtocolVersion*:*Capabilities*:*AvailableMode*'
PR4: PR3 + ':MavlinkTelemetryTest.Mission*' minus guided (use explicit list)
PR5: everything except Tunnel*
PR6: '*' (all 86+)
```
Python harnesses: routing compliance (`src/test/mavlink/routing/`) lands PR-2; mission rig
(`src/test/mavlink/missions/`) lands PR-4.

---

## 5. Cutting procedure

```bash
cd inav
git fetch origin
SRC=mavlink_multiport2

# --- PR-1 (commit-replay; recent history is clean here) ---
git checkout -b mav/01-sitl-fixes origin/maintenance-10.x
git cherry-pick 692a950e3 3c486d618 a18db634d 15d4a4111   # SITL load, RX gate, X-Plane motor, pitch/yaw
git cherry-pick 99019a215                                  # X-Plane altitude inputs
# resolve, build, commit-message cleanup

# --- PR-2 (reconstruct-forward) ---
git checkout -b mav/02-core mav/01-sitl-fixes
# c1: pure move — checkout module files, then amputate per §3
git checkout $SRC -- src/main/mavlink/ src/main/fc/fc_mavlink.c src/main/fc/fc_mavlink.h \
                     src/main/telemetry/mavlink.c src/main/telemetry/mavlink.h src/main/rx/mavlink.h
# EDIT: apply §3 amputations. Carve shared files:
git checkout -p $SRC -- src/main/telemetry/telemetry.c src/main/telemetry/telemetry.h \
                        src/main/fc/settings.yaml src/main/CMakeLists.txt
git commit -m "Split MAVLink telemetry into modules (no behavior change)"
# c2: generated headers
git checkout $SRC -- lib/main/MAVLink
git commit -m "Regenerate MAVLink headers with STorM32 dialect"
# c3..c5: multiport, routing, half-duplex — re-add the amputated-in-c1-but-PR-2 content
...

# --- PR-3..6: same pattern, each branch from the previous ---
# whole-file: git checkout $SRC -- <files>
# shared:     git checkout -p $SRC -- <files>   (take only this PR's hunks)
# tests:      stage cumulative mavlink_unittest.cc section(s)
```

**Per-level gate (run before stacking the next branch):**
1. SITL build (warnings-as-errors) — this is the compilability contract
2. unit target + this level's gtest filter — green
3. `build.sh SPEEDYBEEF405WING` — record FLASH/RAM delta in the PR description
   (branch endpoint: FLASH 72.32%, RAM **92.14%** — find which PR is the RAM hog)
4. Run `docs/development/msp/gen_docs.sh` (MUST run from its own directory) and commit
   regenerated MSP docs with the PR. Note: upstream's checked-in MSP docs are STALE
   (generated from master, wrong FC version + enum drift) — the first regen commit
   (`b455584fb` on mav/04) corrects that; later PRs should only show their own deltas.
5. Headers PR onward: routing compliance 11/11 · mission PR onward: live mission rig 8/8

**Final equivalence check (the "did we lose anything" invariant):**
```bash
git diff mav/06-tunnel $SRC -- src/ lib/ docs/
```
Must be empty except (a) upstream-drift adjustments, (b) `docs/ADSB.md`. Any other hunk =
content that fell through the cracks; assign it to a PR and re-cut.

---

## 5b. Base audit results (2026-07-11, upstream `telemetry/mavlink.c` @ current maintenance-10.x, 1513 lines)

**Upstream INCOMING cases:** HEARTBEAT, PARAM_REQUEST_LIST, RC_CHANNELS_OVERRIDE,
RADIO_STATUS, ADSB_VEHICLE, COMMAND_LONG, COMMAND_INT, MISSION_CLEAR_ALL, MISSION_COUNT,
MISSION_ITEM (float only), MISSION_REQUEST, MISSION_REQUEST_LIST.
**Upstream commands:** MAV_CMD_DO_CHANGE_ALTITUDE, DO_REPOSITION, NAV_RETURN_TO_LAUNCH.
**Upstream OUTGOING:** attitude, battery_status, command_ack, global_position_int,
gps_global_origin, gps_raw_int, heartbeat, mission_ack/count/item/request, param_value,
rc_channels(+raw), scaled_pressure, statustext, sys_status, **system_time**, vfr_hud.

**Boundary corrections vs §3 as originally written:**
- PR-2 must PRESERVE upstream's old-style mission handling (float MISSION_ITEM et al).
  PR-4 = *replace* old mission code with the transfer state machine (+ ITEM_INT,
  REQUEST_INT, MISSION_ACK cases, MISSION_CURRENT, ITEM_REACHED).
- PR-2 must PRESERVE upstream command set (DO_CHANGE_ALTITUDE / DO_REPOSITION / RTL with
  upstream's forced-RTH backend). PR-5 = change RTH backend + add new commands + extract
  command/guided modules.
- REQUEST_DATA_STREAM is branch-NEW (upstream has no such case) → moves PR-2 → PR-3.
- SYSTEM_TIME periodic sender exists upstream → PR-3 only adds request/interval control.
- MLRS_RADIO_LINK_* cases are branch-new → land in PR-2 half-duplex/radio-etiquette commit.

**Approach revision (supersedes "pure single-port move" c1):** the branch modules are
multi-port-native; single-porting them for a synthetic move commit means writing throwaway
code. PR-2 c1 is therefore "modularize WITH multi-port runtime + routing, later features
amputated". Upstream-parity invariant applies to the message/command surface, not port
count. PR-2 commit plan: c1 move+multiport+routing (feature-amputated, upstream mission
and command code preserved inside the new modules) · c2 regenerated STorM32 headers ·
c3 half-duplex etiquette + MLRS/radio-status per-port handling · c4 settings/docs.

## 5c. PR-2 execution state (2026-07-11)

**Stack restructure (user call):** the header regen is its own PR so the core diff stays
reviewable. Branches now: `mav/02-headers` = `2a3ef1553` alone (172 generated files,
+56k lines, review = the generate.sh fix only) · `mav/03-core` = `1e488f31c` on top
(hand-written refactor only). Later PRs shift by one: 04-streams, 05-mission,
06-command-guided, 07-tunnel. Both branches pushed; old `mav/02-core` deleted from origin.

**Headers-point buildability fix (2026-07-11):** header regen alone does NOT build — the
regenerated library moves MAV_CMD out of `common/common.h` into `storm32/storm32.h`, and
MAVLink's include guard means the FIRST include wins (`src/main/rx/mavlink.h`, not
telemetry/mavlink.c). `mav/02-headers` therefore carries a second commit `748553458`:
switch rx/mavlink.h to `storm32/mavlink.h` (keeping upstream `MAVLINK_COMM_NUM_BUFFERS 1`
+ extra warning pragmas for the new helpers), drop the monolith's local APM_PLANE_MODE /
APM_COPTER_MODE enum copies (generated typedefs are `PLANE_MODE`/`COPTER_MODE`, no APM_
prefix). Verified: SITL builds clean at mav/02-headers AND at mav/03-core; rebased core
tree is byte-identical to the pre-rebase one. Same failure was independently hit by the
user's Codex session on a hardware target — symptom: `MAV_CMD_* undeclared` in
telemetry/mavlink.c.

`mav/03-core` builds clean (SITL, warnings-as-errors).

Seam decisions as executed (deltas vs §1 table):
- HIGH_LATENCY2 moved PR-3 → PR-2 (infrastructure threaded through port structs/settings).
- Per-message interval override STORAGE stays PR-2; SET/GET_MESSAGE_INTERVAL +
  REQUEST_MESSAGE + REQUEST_PROTOCOL_VERSION/CAPABILITIES/GET_HOME_POSITION handlers → PR-3.
- REQUEST_DATA_STREAM handler cut from PR-2 (branch-new, not upstream) → PR-3.
- mavlink_command.c/guided.c land REDUCED in PR-2 (upstream surface: DO_REPOSITION minus
  loiter radius, DO_CHANGE_ALTITUDE, + CONTROL_HIGH_LATENCY); PR-5 expands them.
- Mission = documented temporary regression at PR-2 (upstream's old float-mission code NOT
  ported; PR-4 brings the rewrite). PR-2 commit message carries the warning.
- mavFrameSupportMask_e enum parked in mavlink_guided.h; PR-4 moves it to mavlink_mission.h.
- GPS_RAW_INT reverted to upstream accuracy fields (branch gps.h extensions → PR-3).
- target/common.h taken whole in PR-2 (MAX_MAVLINK_PORTS + flash-gating of MAVLink).

DONE since: core unit slice (19/19, `edafa1ff6`) · `mav/04-streams-protocol` cut, built
clean, unit slice 38/38, pushed. PR text files: PR-01..PR-04.md in this directory.
Test carving tool: `claude/developer/scripts/testing/carve_gtest_cases.py` (keep-list of
test-name regexes; reapply the 3 fixture cuts — encodeMspV1Reply helper, wpReached fixture
resets, navigationConsumeWaypointReached stub — until PR-5/PR-7 restore them).
Still open: docs/Mavlink.md staged subsets + docs/Settings.md regen (all PRs) ·
hardware flash/RAM delta (do inline, no agent) · remaining branches: 05-mission,
06-command-guided, 07-tunnel.

## 6. Risks / open items

1. ~~PR-2 "upstream parity" base audit~~ — DONE, see §5b.
2. **`rcdevice_unittest.cc` +80** — cause unverified; confirm it's rc_modes fallout before
   assigning to PR-5.
3. **`target/common.h`** hunks may mix PR-1 (SITL gate) and PR-2 (MAVLink defines) — inspect.
4. **settings.yaml carving** — regenerate `docs/Settings.md` per PR rather than carving it.
5. **Unittest file carving effort** — 3623 lines into 5 cumulative stages; the file appears
   feature-sectioned, but expect shared fixtures/helpers to need care at PR-2.
6. Cherry-pick hashes in §5 are from current branch history; early history (pre-refactor) is
   NOT cleanly pickable — that's why PRs 2–4 and 6 use reconstruct-forward.
7. RAM budget: if one level jumps RAM sharply, consider making that feature's buffers
   build-time-gated before it ever goes upstream.

## 2026-07-12 stack revision
- Dropped from PR-1 (user call): `Fix X-Plane SITL motor output with XITL` and
  `Fix X-Plane SITL pitch yaw signs` — suspected band-aids over a wrong `--chanmap`.
  The stack now INTENTIONALLY diverges from `mavlink_multiport2` in
  `src/main/target/SITL/sim/xplane.c` (those two fixes) and `docs/SITL/X-Plane.md`.
  If the chanmap theory is disproved, cherry-pick 23465a0f0 / d985111eb back in.
- Whole stack rebased and force-pushed; tip verified: SITL clean, 86/86 unit tests.
- PR-02 body now explains the STorM32 dialect choice: OlliW's mLRS-specific messages
  live in that dialect (experimental mLRS support); STorM32 is a superset of
  ardupilotmega+common so no previously-used messages are lost.

## 2026-07-12 docs completion
- `docs/Mavlink.md` was MISSING from the stack (final equivalence check only covered
  src/ + lib/ — docs/ gap). Landed complete on mav/07 (`9c17a905b`), audited against the
  implementation: de-branchified wording, added the lagging flight-mode-change STATUSTEXT
  notices (Jul 11 feature the branch doc never documented). `docs/Settings.md` regenerated
  via `python3 src/utils/update_cli_docs.py` — now byte-identical to the branch's.
- Known imperfection: the full Mavlink.md lands only at PR-7. If upstream goes sequential,
  re-stage doc sections per PR at that point (multiport/routing+settings → PR-3 etc.).

## 2026-07-12 harness import
- Imported the forgotten live harnesses from inav_development mydev/branch/mavlink_multiport2/mavlink_tests:
  mav_multi_benchmark.py + mav_multi_sweep.py + sweep yaml → `src/test/mavlink/ports/` (mav/03-core, `04b35e472`);
  mavlink_msp_tunnel_smoketest.py → `src/test/mavlink/tunnel/` (mav/07-tunnel, `d972b07c1`).
  Paths repointed from mydev/ to in-tree results/ dirs (gitignored); py_compile + yaml parse checked.
  NOT yet live-run from their new locations (needs SITL + pymavlink/mspapi2 env); the sweep yaml's
  `binary:` points at cmake/build_SITL/inav_9.1.0_SITL (version-named, fragile — verify on next live run).
- Cascade rebased 04-07, force-pushed. User additions to PR-05/PR-07 bodies preserved.

## 2026-07-17 — all 7 PRs opened on iNavFlight/inav
Upstream can't base a PR on a fork branch, so all 7 target maintenance-10.x (user chose
"all at once with disclaimers"). Each PR 2-7 body leads with a blockquote naming its own
commit range + a fork compare link, so reviewers can isolate the layer. PR-1 body carries
the full series roadmap. gh pr edit is broken on this repo (deprecated projects-classic
GraphQL) — use `gh api -X PATCH repos/iNavFlight/inav/pulls/<n> -F body=@file` instead.

| Part | PR | Branch |
|------|-----|--------|
| 1 | #11712 | mav/01-sitl-fixes |
| 2 | #11713 | mav/02-headers |
| 3 | #11714 | mav/03-core |
| 4 | #11715 | mav/04-streams-protocol |
| 5 | #11716 | mav/05-mission |
| 6 | #11717 | mav/06-command-guided |
| 7 | #11718 | mav/07-tunnel |

Merge order 1→7. After each merges, the next one's diff auto-cleans against maintenance-10.x.
