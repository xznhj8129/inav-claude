#!/usr/bin/env python3
"""
elrs_detect — shared library for ELRS receiver detection via FC serial passthrough.

Imported by fc_web_tool/fc_web_tool.py and any CLI wrappers.

Entry point:
    result = detect_elrs(port, allow_bootloader=False, log_fn=print)

See detect_elrs() docstring and ELRS_RX_TESTING.md for full protocol details.
"""

import re
import time
import serial

FC_BAUD = 115200
RX_BAUD = 420000

# ── CRC-8 (poly 0xD5, used by both CRSF and ELRS bootloader) ─────────────────

def crc8(data, poly=0xD5):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ poly) if (crc & 0x80) else (crc << 1)
    return crc & 0xFF

# ── CRSF addresses and frame types ───────────────────────────────────────────

CRSF_ADDR_FC  = 0xC8   # FLIGHT_CONTROLLER — also the sync byte accepted by RX
CRSF_ADDR_TX  = 0xEA   # RADIO_TRANSMITTER
CRSF_ADDR_RX  = 0xEC   # CRSF_RECEIVER

CRSF_TYPE_LINK_STATS  = 0x14
CRSF_TYPE_RC_CHANNELS = 0x16
CRSF_TYPE_DEVICE_PING = 0x28
CRSF_TYPE_DEVICE_INFO = 0x29

CRSF_TYPE_NAMES = {
    CRSF_TYPE_LINK_STATS:  'LINK_STATS',
    CRSF_TYPE_RC_CHANNELS: 'RC_CHANNELS',
    CRSF_TYPE_DEVICE_PING: 'DEVICE_PING',
    CRSF_TYPE_DEVICE_INFO: 'DEVICE_INFO',
}

# ── Packet builders ───────────────────────────────────────────────────────────

def build_crsf_ping():
    """
    CRSF device ping addressed to the RX (dest=0xEC).
    AppendTelemetryPackage() only triggers sendDeviceFrame when dest == 0xEC.
    """
    payload = bytes([CRSF_TYPE_DEVICE_PING, CRSF_ADDR_RX, CRSF_ADDR_FC])
    return bytes([CRSF_ADDR_FC, len(payload) + 1]) + payload + bytes([crc8(payload)])


def build_bootloader_seq(chip_type='ESP82'):
    """
    ELRS CRSF bootloader-enter command.
    chip_type='ESP82' for ESP8265/8285 targets (default).
    chip_type=None for the plain form used by STM32 targets.
    Send only once — multiple sends confuse the ROM bootloader.
    """
    base = [0xEC, 0x04, 0x32, ord('b'), ord('l')]
    if chip_type:
        key = [ord(c) for c in chip_type]
        base[1] += len(key)
        base += key
    return bytes(base + [crc8(base[2:])])


# ROM bootloader baud-rate training sequence (prevents auto-baud misdetection)
TRAIN_SEQ = b'\x07\x07\x12\x20' + b'\x55' * 32

# ── Serial helpers ────────────────────────────────────────────────────────────

def _read_until(s, delimiters, timeout=2.0):
    buf, enc = bytearray(), [d.encode() if isinstance(d, str) else d for d in delimiters]
    deadline = time.time() + timeout
    while time.time() < deadline:
        n = s.in_waiting
        if n:
            buf += s.read(n)
            for d in enc:
                if d in buf:
                    return buf.decode('utf-8', errors='replace')
        else:
            time.sleep(0.01)
    return buf.decode('utf-8', errors='replace')


def _drain(s):
    time.sleep(0.3)
    return s.read(s.in_waiting)


# ── CRSF frame parser ─────────────────────────────────────────────────────────

def parse_frames(buf):
    """Extract complete CRSF frames; return (list_of_(addr,type,bytes), remainder)."""
    frames, i = [], 0
    while i < len(buf) - 2:
        addr = buf[i]
        if addr in (CRSF_ADDR_FC, CRSF_ADDR_TX, CRSF_ADDR_RX, 0xEE):
            if i + 1 < len(buf):
                length = buf[i + 1]
                end = i + 2 + length
                if end <= len(buf) and length > 0:
                    frame = buf[i:end]
                    ftype = frame[2] if len(frame) > 2 else 0
                    frames.append((addr, ftype, bytes(frame)))
                    i = end
                    continue
        i += 1
    return frames, buf[i:]


def parse_device_info(frame):
    """
    Parse CRSF DEVICE_INFO frame (type 0x29).
    Layout: [addr][len][type][dest][origin][name\0][serial 4B][hw 4B][fw 4B][nparams][param_ver][crc]
    """
    try:
        null_pos = frame.index(0, 5)
        name = frame[5:null_pos].decode('utf-8', errors='replace')
        rest = frame[null_pos + 1:]
        if len(rest) >= 12:
            fw = rest[8:12]
            fw_str = f"{fw[2]}.{fw[1]}.{fw[0]}"
            return {'name': name, 'fw_version': fw_str}
        return {'name': name}
    except Exception:
        return None

# ── Exceptions ────────────────────────────────────────────────────────────────

class AlreadyInPassthrough(Exception):
    pass

class NoSerialRxConfigured(Exception):
    pass

# ── FC CLI interaction ────────────────────────────────────────────────────────

def enter_cli_and_find_rx_port(s, log_fn=print):
    """
    Enter the FC CLI and find the UART index configured for serial RX.
    Raises AlreadyInPassthrough if the FC doesn't respond.
    Raises NoSerialRxConfigured if no UART has serial RX enabled.
    """
    for attempt in range(6):
        s.reset_input_buffer()
        s.write(b'#\r\n')
        s.flush()
        resp = _read_until(s, ['# '], timeout=1.5)
        if '# ' in resp:
            break
        if attempt < 5:
            time.sleep(0.5)
    else:
        raise AlreadyInPassthrough(
            "FC did not respond to CLI commands. It may already be in passthrough "
            "mode — power-cycle the FC USB connection and try again."
        )

    s.write(b'serial\r\n')
    s.flush()
    resp = _read_until(s, ['# '], timeout=2.0)

    for line in resp.splitlines():
        m = re.match(r'serial\s+(\d+)\s+(\d+)', line)
        if m and (int(m.group(2)) & 64):  # bit 6 = serial RX
            return int(m.group(1))

    raise NoSerialRxConfigured(
        "No UART is configured for serial RX in the FC. "
        "Check that the receiver port is set to 'Serial Receiver' in the FC configurator."
    )


def enable_passthrough(s, rx_idx, log_fn=print):
    """Send CLI serialpassthrough command. After this the port is a raw bridge."""
    cmd = f'serialpassthrough {rx_idx} {RX_BAUD}\r\n'
    s.write(cmd.encode())
    s.flush()
    resp = _drain(s)
    if b'Forwarding' not in resp:
        log_fn(f"  Warning: unexpected passthrough response: {resp!r}")
    return resp

# ── Detection stages ──────────────────────────────────────────────────────────

def stage_passive_listen(s, timeout=1.5):
    """
    Stage 1: Listen for spontaneous CRSF frames (requires active TX link).
    Returns list of (addr, ftype, frame_bytes).
    """
    buf = bytearray()
    deadline = time.time() + timeout
    while time.time() < deadline:
        n = s.in_waiting
        if n:
            buf += s.read(n)
        else:
            time.sleep(0.01)
    frames, _ = parse_frames(buf)
    return frames


def stage_crsf_ping(s, timeout=1.5):
    """
    Stage 2: Send CRSF DEVICE_PING and wait for DEVICE_INFO response.
    Works without TX link. Returns parsed device info dict or None.
    """
    s.reset_input_buffer()
    ping = build_crsf_ping()
    s.write(ping)
    s.flush()

    buf = bytearray()
    deadline = time.time() + timeout
    while time.time() < deadline:
        n = s.in_waiting
        if n:
            buf += s.read(n)
            frames, buf = parse_frames(bytearray(buf))
            for addr, ftype, frame in frames:
                if ftype == CRSF_TYPE_DEVICE_INFO:
                    return parse_device_info(frame)
        else:
            time.sleep(0.02)
    return None


def stage_bootloader(s, log_fn=print):
    """
    Stage 3: Send ELRS bootloader-enter command. DESTRUCTIVE — RX reboots into
    bootloader mode and requires power-cycle to recover.
    Returns dict with 'target' key, or None if no response.
    """
    s.reset_input_buffer()
    time.sleep(0.1)
    initial = s.read(s.in_waiting)
    if b'CCC' in initial:
        return {'target': '(already in bootloader — target unknown)'}

    s.write(TRAIN_SEQ)
    s.flush()
    time.sleep(0.2)
    s.reset_input_buffer()

    for chip_type in ('ESP82', None):
        seq = build_bootloader_seq(chip_type)
        label = chip_type or 'plain'
        log_fn(f"  Trying bootloader seq chip_type={label}: {seq.hex(' ')}")
        s.write(seq)
        s.flush()

        deadline = time.time() + 2.0
        buf = bytearray()
        while time.time() < deadline:
            n = s.in_waiting
            if n:
                buf += s.read(n)
                text = buf.decode('utf-8', errors='replace')
                for line in text.splitlines():
                    line = line.strip()
                    if '_RX' in line.upper():
                        return {'target': line}
                    if 'CCC' in line:
                        return {'target': '(already in bootloader — target unknown)'}
            time.sleep(0.05)

        if buf:
            log_fn(f"  Got bytes but no target: {buf.hex(' ')}")

    return None

# ── Main entry point ──────────────────────────────────────────────────────────

def detect_elrs(port, allow_bootloader=False, log_fn=print):
    """
    Detect an ELRS receiver via FC serial passthrough.

    Args:
        port:             Serial port path (e.g. '/dev/ttyACM0')
        allow_bootloader: Run the destructive stage 3 if stages 1+2 both fail.
                          Defaults to False — leave receivers in a good state.
        log_fn:           Callable for progress messages; default is print.

    Returns:
        dict with keys:
            found       bool   True if receiver was detected by any stage
            stage       int    Which stage detected it (0=none/error, 1, 2, or 3)
            rx_pin      bool   RX pin (RX→FC direction) confirmed
            tx_pin      bool   TX pin (FC→RX direction) confirmed
            name        str    Receiver device name (stage 2 only), or None
            fw_version  str    Firmware version string (stage 2 only), or None
            target      str    Bootloader target name (stage 3 only), or None
            error       str    Fatal error message if test couldn't run, or None

    NOTE: After this returns, the FC is in passthrough mode regardless of result.
    The FC requires a physical USB power-cycle to restore normal MSP operation.
    """
    result = {
        'found': False, 'stage': 0,
        'rx_pin': False, 'tx_pin': False,
        'name': None, 'fw_version': None, 'target': None,
        'error': None,
    }

    log_fn(f"Connecting to FC on {port}...")
    try:
        s = serial.Serial(port=port, baudrate=FC_BAUD, bytesize=8, parity='N',
                          stopbits=1, timeout=1, xonxoff=0, rtscts=0)
    except serial.SerialException as e:
        result['error'] = f"Cannot open {port}: {e}"
        log_fn(f"[ERROR] {result['error']}")
        return result

    try:
        rx_idx = enter_cli_and_find_rx_port(s, log_fn)
        log_fn(f"Serial RX on FC UART index {rx_idx}")
    except AlreadyInPassthrough as e:
        result['error'] = str(e)
        log_fn(f"[ERROR] {result['error']}")
        s.close()
        return result
    except NoSerialRxConfigured as e:
        result['error'] = str(e)
        log_fn(f"[ERROR] {result['error']}")
        s.close()
        return result

    log_fn(f"Enabling passthrough (UART {rx_idx} @ {RX_BAUD} baud)...")
    enable_passthrough(s, rx_idx, log_fn)
    log_fn("Passthrough active. Power-cycle FC USB to exit.")

    # Stage 1: passive listen
    log_fn("[Stage 1] Passive listen (1.5s)...")
    frames = stage_passive_listen(s)
    if frames:
        result['rx_pin'] = True
        types_seen = set(CRSF_TYPE_NAMES.get(ft, f'0x{ft:02x}') for _, ft, _ in frames)
        log_fn(f"  Received {len(frames)} CRSF frame(s): {types_seen}")
        if any(ft in (CRSF_TYPE_LINK_STATS, CRSF_TYPE_RC_CHANNELS) for _, ft, _ in frames):
            log_fn("  RX pin: confirmed")
    else:
        log_fn("  No frames received (no active TX link, or receiver silent)")

    # Stage 2: CRSF device ping
    log_fn("[Stage 2] CRSF device ping...")
    info = stage_crsf_ping(s)
    if info:
        result['found'] = True
        result['stage'] = 2
        result['rx_pin'] = True
        result['tx_pin'] = True
        result['name'] = info.get('name')
        result['fw_version'] = info.get('fw_version')
        log_fn(f"[FOUND] ELRS receiver: {result['name']}"
               + (f" v{result['fw_version']}" if result['fw_version'] else ""))
        s.close()
        return result

    if frames:
        log_fn("  No ping response — TX pin unconfirmed")
        if not allow_bootloader:
            result['found'] = True
            result['stage'] = 1
            log_fn("[PARTIAL] Receiver detected via passive listen — TX pin unconfirmed")
            s.close()
            return result
    else:
        log_fn("  No response")

    # Stage 3: bootloader sequence
    if not allow_bootloader:
        if not result['found']:
            log_fn("[NOT FOUND] No ELRS receiver detected")
            log_fn("  Possible causes: no receiver connected, baud rate mismatch,")
            log_fn("  receiver in WiFi mode (power-cycle once and retry immediately)")
        s.close()
        return result

    log_fn("[Stage 3] ELRS bootloader sequence (DESTRUCTIVE)...")
    log_fn("  WARNING: RX will reboot into bootloader mode. Power-cycle to recover.")
    bl_result = stage_bootloader(s, log_fn)
    if bl_result:
        result['found'] = True
        result['stage'] = 3
        result['rx_pin'] = True
        result['tx_pin'] = True
        result['target'] = bl_result['target']
        log_fn(f"[FOUND] ELRS receiver via bootloader: {result['target']}")
        log_fn("  NOTE: RX is now in bootloader mode — power-cycle RX to recover")
    else:
        log_fn("[NOT FOUND] No ELRS receiver detected")

    s.close()
    return result
