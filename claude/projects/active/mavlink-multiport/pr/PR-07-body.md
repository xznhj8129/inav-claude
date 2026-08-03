**Part 7/7 of the mavlink_multiport2 stack — final part; the tree now carries the complete feature set.**

## MSP-over-MAVLink tunnel

MSP transport over the MAVLink [Tunnel service](https://mavlink.io/en/services/tunnel.html) (private payload type `0x8001`, MAVLink 2 only), so the INAV Configurator can talk MSP over an existing MAVLink telemetry link — typically a radio that exposes no separate MSP transport. The companion configurator PR adds a "MAVLink Tunnel" option under Wireless mode with SYSID selection for multi-vehicle networks.

- Reuses the existing MSP parser/encoder through three narrow `msp_serial` seams (byte parser, encode-to-buffer, command processing) — no duplicate MSP framing logic.
- Replies are fragmented across `TUNNEL` messages and returned **on the ingress port only**; `target_component = 0` is accepted for local delivery but never fanned out to other ports.
- MSP framing symmetry is preserved end-to-end: MSPv1 requests get MSPv1 replies, MSPv2 gets MSPv2.
- `MSP_REBOOT` post-processing is supported over the tunnel; serial passthrough and ESC 4-way passthrough are rejected **before** dispatch.
- Malformed payload lengths are dropped without poisoning parser state; stale partial frames reset after a timeout; a new sender displaces a stale partial transaction.
- Reply/frame buffers are file-scope, not telemetry-task stack (avoids stack overflow on FLASHFS targets).
- Not a general-purpose serial tunnel: CLI mode is not carried over this path.

## Documentation

This PR also lands the complete user-facing `docs/Mavlink.md` (multiport/routing, datastream groups and CLI settings, mLRS integration, supported messages/commands, mode mappings, mission behavior and MSP parity gaps, tunnel, high-latency mode) and regenerates `docs/Settings.md` for the per-port `mavlink_port{1-4}_*` settings.

## Testing
- Full `mavlink_unittest` suite: **86/86 passing** (tunnel cases: malformed-length rejection, pre-dispatch passthrough rejection, reboot ingress-port handling, stale-frame reset, multi-message reply fragmentation).
- Full SITL build, warnings-as-errors, clean.
- Previously validated live end-to-end on the development branch: Configurator connect over tunnel, EEPROM write, reboot, reconnect after reboot.
- Includes the live tunnel smoke-test harness (`src/test/mavlink/tunnel/`) covering that same sequence against a running SITL/FC.
- Configurator branch tested, Tunnel works over ELRS-Mavlink and mLRS

Companion PRs: `inav-configurator:mavlink_multiport2` (tunnel UI + wrapping), `mspapi2:mavlink_multiport2`.
