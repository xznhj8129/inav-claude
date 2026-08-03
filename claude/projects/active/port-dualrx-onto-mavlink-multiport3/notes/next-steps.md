# Dual RX — next steps

Design decisions from the 2026-07-24 review discussion. Ordered by priority.
Branches as pushed: inav `feature/dualrx` @ `c88d5a248`, inav-configurator
`feature/dualrx` @ `2daaffe7`. Both need locks reacquired before work resumes.

---

## P1 — BUG (introduced by me, fix first)

**MSP-over-CRSF replies go out the wrong port.**

`crsfDataReceive()` in `src/main/rx/crsf.c` handles `CRSF_FRAMETYPE_MSP_REQ` /
`MSP_WRITE` for frames arriving on *either* link (it calls `bufferCrsfMspFrame()` /
`crsfScheduleMspResponse()` from the per-link ISR path). But `crsfRxSendTelemetryData()`
writes to the single file-scope `serialPort`, which I set to the **primary** link's port
only. So an MSP request arriving on the secondary receiver is answered on the primary
port — wrong destination, and it silently crosses the two links.

Correct principle, already settled by the MAVLink tunnel work: **replies go out the
ingress port.** Fix requires per-link telemetry state (buffer + port + length), not a
single shared one. Naturally folds into P2.

Introduced in `a97c7fb81` while refactoring CRSF statics into `crsfLinkStates[]`.

---

## P2 — Telemetry to both links

Telemetry must flow on **both** links independently. RC loss and telemetry loss are
independent events; a second operator / ground station wants data regardless of who
currently holds the sticks. My "telemetry stays on primary" in `crsfRxInit()` was a
refactor shortcut that I then wrote up as if it were a design decision — it was not.

- Per-link telemetry buffers + per-link `serialPort`.
- Half-duplex TX backoff paces per port — the per-link `frameStartAtUs` added in the
  refactor already supports this.
- Costs: bandwidth, RAM (see P6).

---

## P3 — Switchover model (the real design work)

Current selection is binary and death-only: primary valid → primary, else secondary.
It never reacts to *degradation*, which is the case that actually matters with two
receivers.

### Tiering (agreed)

1. **Always:** failover on link **death**. Protocol-agnostic, no metric comparison,
   safe for any pair (2.4 + 900, CRSF + SBUS, …).
2. **Only when metrics are comparable:** quality-based switchover. Gate on the two links
   sharing a metric basis — comparing CRSF LQ against an RSSI-derived value and switching
   on the difference is nonsense. Needs threshold + dwell + minimum-improvement-to-switch
   as one coupled design, not three independent settings.
3. **Manual:** override (see below).

Note: a threshold **without** hysteresis makes flapping worse, because you'd start
switching on noise instead of only on death.

### Bumpless transfer

At switch, `rxApplyActiveLink()` memcpy's the other link's independently-tracked channel
history wholesale → sticks can step discontinuously. Same problem family as hysteresis;
solve together.

### Manual select — authority model (the sharp edge)

A dedicated `RECEIVER SELECT` mode is warranted; LC alone is not sufficient (discoverable
only to people already writing logic conditions, for a safety-relevant action).

**The crux: the select input is read from the link it selects.** Feedback loop.

- *Same TX, two receivers:* fine — the switch position arrives identically on both links,
  they agree by construction.
- *Two operators / true handoff:* if B's switch sits in the "link 1" position and control
  is handed to B's link, B's channel data immediately commands "go back to link 1" →
  instant flip-flop, in the failsafe path, in flight.

Combine:

1. **Handoff, not seize.** A link may *release* control; it may not *take* it. A
   mismatched static switch position on the receiving side then does nothing. Automatic
   seize stays for the death case only. Semantically honest for handoff, kills the
   flip-flop outright.
2. **Authority link.** If level-based seize is wanted anyway, honor the select channel
   only from a designated authority link.
3. **Disregard selection input from a link with no signal.** Non-negotiable in either
   model — channel data holds its last value indefinitely after death, so a stale
   "select link 2" would pin control to a corpse.

**Important:** (3) is the principle behind the override fix already landed in `a97c7fb81`,
but that fix does **not** solve the flip-flop. If an LC is driven by an RC channel, the
existing `LOGIC_CONDITION_RX_SELECT_OVERRIDE` has the identical feedback bug today — it is
only safe for the same-TX case.

Also needs a stated tie-break for simultaneous requests: **link 1 wins.**

---

## P4 — OSD naming: `RX:1` / `RX:2`

Replace `RX:P` / `RX:S`. "P/S" implies a permanent hierarchy, but with override and
quality-based switching link 2 can legitimately be *the* link; numbers are neutral and
scale if a third link ever appears.

Knock-on renames for consistency:
- Warning string `"PRI RX FS"` → `"RX1 FS"` (fits the 10-char multifunction limit).
- `rxIsPrimaryFailsafe()` carries the same naming bias.

---

## P5 — Blackbox logging of link state

Log active link as a field, plus an event marker on switch (ideally with both links'
stats at that instant). For a redundancy feature, "when did it switch and why" is the
entire post-flight question. Cheap to add.

---

## P6 — Arming, config divergence, RAM

- **Arming:** allowed on the secondary link, and allowed with no primary. Arming checks
  are currently not link-aware at all (greenfield). Arming with only one live link means
  arming *without redundancy* — warn the pilot, don't block.
- **Channel-map / channel-count divergence:** both links share one `rcmap` and channel
  expectations. User's responsibility, but must not be silent — surface a mismatch as an
  arming warning / configurator notice. No enforcement, no cleverness.
- **RAM:** already 93.01% on SPEEDYBEEF405WING. Per-link state for the remaining drivers
  and per-link telemetry buffers both grow it. Watch before instancing further.

---

## P7 — Remaining serial drivers instance-safe

Apply the CRSF/SBUS per-link pattern to Spektrum, SUMD, IBUS, JETI, FPORT/FPORT2, SRXL2,
GHST so two identical receivers of those types work. Until then `rxInit()` guards them
(refuses dual RX when both links share a not-yet-safe driver group).

---

## Scope decision: serial RC protocols only

MSP stays excluded — but for the *mechanical* reason, not the principled one I originally
wrote: `rx/msp.c` keeps channel state in module statics (same class of problem as the
drivers), and MSP RC has no port identity, so "link 1 vs link 2" isn't derivable from the
transport.

MAVLink is a genuinely open question, deliberately deferred rather than inherited: with
multiport it *does* have per-port identity, so it is closer to the serial model than MSP
is. Do not let it ride along with this work — telemetry protocols doubling as RC links is
where users get confused, and confusion in a failsafe path is a safety cost.

---

## Still outstanding from the port itself

- Bench/flight validation of the secondary serial path (needs hardware): single-RX
  regression + a real dual-RX setup. Nothing here is hardware-verified.
- `dual_rx_pr.md` is marked WIP by the user pending elaboration on switchover states,
  hysteresis/dwell, receiver configurations and telemetry (i.e. P2/P3 above).
