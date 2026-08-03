# Dual RX configurator support (secondary receiver + failover UI)

Companion to the firmware dual RX fallback feature. Exposes the second receiver in
the UI and reports which link is currently in control.

Branch: `feature/dualrx` (based on `mavlink_multiport2`).

## Changes

- **Receiver tab** (`tabs/receiver.html`, `tabs/receiver.js`): primary/secondary receiver
  type, provider, inversion and half-duplex controls, and an indicator of the currently
  active RX link.
- **Ports tab** (`tabs/ports.js`, `js/serialPortHelper.js`): new `RX_SERIAL_SECONDARY`
  serial function (bit 13) so a second serial RX can bind to its own UART.
- **Configuration tab** (`tabs/configuration.html`, `tabs/configuration.js`): dual-receiver
  enable and serial-RX grouping.
- **MSP** (`js/msp/MSPHelper.js`, `js/fc.js`): read the `activeRX` byte appended to
  `MSP2_INAV_MISC` (bounds-checked so older firmware without the byte still parses).
- **Programming** (`js/logicConditionOperators.js`): "Select RX link" logic operator,
  id **63**, matching the firmware `logicOperation_e` value.
- **Translations**: new keys for en/ja/ru/uk/zh_CN.

## Cross-repo consistency (verified against firmware)

- Logic operator "Select RX link" id **63** == firmware `LOGIC_CONDITION_RX_SELECT_OVERRIDE`.
- `RX_SERIAL_SECONDARY` serial-function bit **13** == firmware `FUNCTION_RX_SERIAL_SECONDARY`
  (`1 << 13`).
- `activeRX` read position matches the firmware append to `MSP2_INAV_MISC`.

## Verification

- All five locale JSON files parse.
- All changed JS files parse (`node --check`); `LOGIC_OPERATORS` has no duplicate keys and
  exposes id 63.
- Every new `data-i18n` key in the changed HTML resolves in `locale/en/messages.json`.
- No linter is configured in the repo (`yarn lint` is a no-op).
- Not exercised in a running Electron session — needs a manual pass against a connected FC
  (or SITL) for the receiver/ports UI.

## Depends on

The firmware branch `feature/dualrx` (fork `origin`, based on `mavlink_multiport3`).
