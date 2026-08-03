# Project: RC-less Telemetry/Nav Control Mode

**Status:** 📋 TODO
**Priority:** LOW
**Type:** Feature (safety-critical — touches arming interlock)
**Created:** 2026-07-22
**Estimated Effort:** Design phase 4-6 hours; implementation TBD after design review

## Overview

Add a **GCS/datalink-heartbeat failsafe** to INAV — a second, independent link-liveness
detector modeled on PX4 ("datalink loss") and ArduPilot (`FS_GCS_ENABLE`). This lets an
aircraft be flown under telemetry-link + autonomous-nav control **without streaming RC
frames and without a companion computer**, while still having a genuine link-loss
safety response. Design-first: confirm feasibility and interlock impact before code.

## Problem

Users want to operate an aircraft under telemetry-link + autonomous-nav control
without paying the cost of continuously streaming RC frames. A telemetry/radio link
is still present (this is NOT about flying with zero link); the objection is that the
*current* RC-less path is wasteful and hardware-hostile:

1. **Bandwidth waste.** `receiverType = MSP` requires a continuous stream of MSP RC
   frames to keep the link "alive," even when the RC content is effectively null.
   On a constrained telemetry link that stream is expensive.
2. **Forced companion hardware.** Generating that RC stream in practice means bolting
   on a companion computer (e.g. an ESP32) whose only job is to fake RC frames — a
   hardware workaround for what is fundamentally a software limitation.

**What already exists (confirmed in source, 2026-07-22):**
- `receiverType = MSP` (`RX_TYPE_MSP`, `inav/src/main/rx/rx.h:63`) — RC channel data
  supplied over the MSP link.
- `USE_MSP_RC_OVERRIDE` + `msp_override` (`inav/src/main/rx/msp_override.c`).
- Autonomous nav (waypoint missions, RTH, POSHOLD, cruise) runs with no stick input.
- Arming gate `ARMING_DISABLED_RC_LINK` (`inav/src/main/fc/fc_core.c:221-227`) keyed
  **solely** on `failsafeIsReceivingRxData()`.

**Not an authorization/anti-abuse project.** A companion ESP32 can already fly an
aircraft RC-less today by inertially spoofing RC frames ("arm, angle, throttle up,
alt>10 → WP mode, keep sending RC") with zero regard for link state. That is possible
now, unwise, and not what this addresses. The onus for safe operation is on the user.

**What's actually missing — a second, independent liveness detector.** INAV's failsafe
is **entirely RX-loss-driven** (`inav/src/main/flight/failsafe.h` — all procedures key
off RX signal loss). There is **no GCS/datalink heartbeat failsafe** in the tree
(confirmed 2026-07-22). PX4 ("datalink loss") and ArduPilot (`FS_GCS_ENABLE`) both have
one: a periodic heartbeat over the telemetry link whose loss triggers the failsafe
procedure, *independent of RC*. INAV has no equivalent.

## Solution

Design-first. Add a **GCS/datalink-heartbeat failsafe** as a **separate liveness
source** alongside the existing RC-link failsafe, modeled on PX4/ArduPilot:

- A new, independent setting (its own enable + timeout), NOT a modification of the
  RC-link check. Heartbeat arrives over the telemetry link (MSP and/or MAVLink — see
  `mavlink_multiport2` work); loss triggers the configured `failsafe_procedure`.
- **Both liveness sources independently toggleable.** A user who wants RC-less,
  low-bandwidth operation disables RC-link failsafe and relies on GCS failsafe;
  a conventional user does the reverse. Both may be disabled (user's onus), but
  realistically at least one is always active.
- Net effect: fly under telemetry/nav control with NO streamed RC frames and NO
  companion computer, while still having a real link-loss safety response.

Produce a written design doc first (done — `design.md`), then implement through the
normal dev workflow. Because it touches arming/failsafe, the real gate is a
**safety-correctness review + SITL failsafe testing** — not a formal security
analysis (no crypto/auth/network-attack surface is involved).

## Scope

**In Scope:**
- Design/feasibility document for a **new GCS/datalink-heartbeat failsafe** as an
  independent liveness source alongside the existing RC-link failsafe.
- Deciding the heartbeat transport (MSP command activity and/or a MAVLink heartbeat —
  see `mavlink_multiport2`) and where its "last seen" timestamp lives.
- New independent settings (enable + timeout per source); how the two sources compose.
- Enumerating every safety interlock the RC-less case interacts with (arming,
  failsafe, RTH-on-link-loss, throttle/level/geozone gates).
- User-facing documentation of the supported RC-less configuration.

**Out of Scope (unless the design phase justifies it, then re-scope with Manager):**
- Removing or weakening the *existing* RC-link failsafe. The GCS failsafe is
  **additive** — a parallel source, independently enabled/disabled.
- Any design where BOTH sources being disabled is presented as a normal/recommended
  config. (It's permitted — user's onus — but realistically ≥1 is always active.)
- New hidden/undocumented modes — everything here is explicit and documented.

## Implementation

**Phase 1 — Design (DONE):** `design.md` — grounded in source; recommends an additive
GCS-heartbeat liveness source (Option A), MSP-activity-sourced first (scoped to the
configured RX/telemetry ports), MAVLink heartbeat as a follow-on. Product-owner
decisions baked in: no hard minimum-one-source; separate `ARMING_DISABLED_GCS_LINK`
display flag with a composed arm predicate; advisory config warning only.

**Phase 2 — Implement** per the normal developer workflow (branch, code, build,
`inav-code-review`). Files in play: `failsafe.c`/`.h` (new liveness source + timeout),
`rx.c`/MSP port resolution (heartbeat source), `fc_core.c`/`runtime_config.h` (new arm
flag + composed predicate), `settings.yaml` + `update_cli_docs.py` (new settings).

**Phase 3 — SITL failsafe testing (the real gate):** verify the GCS failsafe triggers
the configured procedure when the heartbeat goes stale, and does NOT trigger while
it's fresh; verify arming is permitted with a fresh GCS heartbeat and no RC frames.

## Success Criteria

- [ ] `design.md` written, grounded in actual source (file:line references)
- [ ] PX4/ArduPilot GCS-failsafe behavior surveyed for reference
- [ ] Heartbeat transport chosen (MSP activity and/or MAVLink heartbeat) with rationale
- [ ] Settings surface defined (independent enable + timeout; how sources compose)
- [ ] Every safety interlock the feature touches enumerated with current behavior
- [ ] SITL failsafe testing: triggers on stale GCS heartbeat, not on fresh; arms with
      fresh heartbeat and no RC frames
- [ ] `inav-code-review` pass before PR
- [ ] User documentation drafted for the supported RC-less path

## Related

- **Issue:** N/A
- **PR:** N/A (not yet created)
- **Design:** `design.md` (complete)
