# Todo: RC-less Telemetry/Nav Control Mode

## Phase 1: Design & Feasibility (only committed deliverable for now)

- [x] Survey PX4 "datalink loss" and ArduPilot `FS_GCS_ENABLE` behavior as reference
- [x] Document the RC-frame bandwidth cost of the current `RX_TYPE_MSP` path (the
      thing a GCS failsafe lets you avoid)
- [x] Trace how `failsafe.c`/`failsafe.h` currently reads its RX-loss liveness signal,
      and identify the clean insertion point for a second, independent source
- [x] Decide heartbeat transport: MSP command activity and/or a MAVLink heartbeat
      (see `mavlink_multiport2`); define where the "last seen" timestamp lives
- [x] Define the settings surface: independent enable + timeout per source, and how
      the RC-link and GCS sources compose when both/neither are enabled
- [x] Enumerate every safety interlock the RC-less case touches (arming, failsafe,
      RTH-on-link-loss, throttle/level/geozone)
- [x] Write `design.md` with the above + a firmware-change recommendation
      → `design.md` (grounded in source, Option A recommended)

## Phase 2: Implement (normal dev workflow)

- [ ] Acquire `inav.lock`, create branch from the correct base (see git-workflow skill)
- [ ] `failsafe.c`/`.h`: add GCS-heartbeat liveness source + timeout, evaluated in
      `failsafeUpdateState`
- [ ] Heartbeat source: refresh on MSP traffic on the configured RX/telemetry port(s)
      only (resolve which `mspPort_t` maps to those serial functions)
- [ ] `fc_core.c`/`runtime_config.h`: add `ARMING_DISABLED_GCS_LINK` (display) + composed
      `anyEnabledControlLinkUp` arm predicate
- [ ] `settings.yaml`: `failsafe_gcs_link_enabled` / `_timeout` / `_source`; run
      `utils/src/update_cli_docs.py`
- [ ] Build via inav-builder; `inav-code-review` pass

## Phase 3: SITL failsafe testing (the real gate)

- [ ] Stale GCS heartbeat → configured `failsafe_procedure` fires
- [ ] Fresh GCS heartbeat → no failsafe
- [ ] Arming permitted with fresh heartbeat and zero RC frames
- [ ] Existing RC-link failsafe behavior unchanged (regression)

## Completion

- [x] design.md complete and grounded in source
- [ ] SITL failsafe tests pass
- [ ] User documentation drafted
- [ ] PR created; completion report sent to manager

_Note: formal Security Analyst review dropped 2026-07-22 (no crypto/auth/network
surface). Review request retracted → `security-analyst/email/inbox-archive/...-CANCELLED.md`.
Real gate is safety-correctness review + SITL failsafe testing._
