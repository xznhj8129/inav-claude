#!/usr/bin/env python3
"""
Flight Controller Web Test Tool
Web interface for motor testing and serial port configuration via MSP protocol.
WARNING: Motor testing will spin motors. Ensure propellers are removed!
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import serial
import struct
import time
import glob
import subprocess
import sys
import os
from typing import List, Optional, Tuple, Dict
from abc import ABC, abstractmethod
import threading
import logging

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from elrs_detect import detect_elrs

# Suppress Flask development server warnings
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fc-test-tool-secret'
socketio = SocketIO(app, cors_allowed_origins="*")


class MSPCodes:
    """MSP protocol command codes"""
    MSP_API_VERSION = 1
    MSP_FC_VARIANT = 2
    MSP_FC_VERSION = 3
    MSP_MOTOR = 104
    MSP_SET_MOTOR = 214
    MSP_SET_FEATURE = 37
    MSP_FEATURE = 36
    MSP_EEPROM_WRITE = 250
    MSP_SET_REBOOT = 68
    MSP2_INAV_MIXER = 0x2010
    MSP2_COMMON_MOTOR_MIXER = 0x1005
    MSPV2_INAV_OUTPUT_MAPPING_EXT2 = 0x210D
    MSPV2_INAV_ANALOG = 0x2002
    MSP2_CF_SERIAL_CONFIG = 0x1009
    MSP2_SET_CF_SERIAL_CONFIG = 0x100A
    MSP2_INAV_TIMER_OUTPUT_MODE = 0x200E
    MSP2_INAV_SET_TIMER_OUTPUT_MODE = 0x200F
    MSP2_COMMON_SET_MOTOR_MIXER = 0x1006
    MSP2_INAV_SERVO_MIXER = 0x2020
    MSP2_INAV_SET_SERVO_MIXER = 0x2021
    MSP_CURRENT_METER_CONFIG = 40

INPUT_MAX = 29  # inputSource_e: constant full-scale input, always outputs +1.0


class MSPBase(ABC):
    """Base class for MSP protocol implementations"""

    def __init__(self, serial_port: serial.Serial):
        self.serial = serial_port

    @abstractmethod
    def send_command(self, cmd: int, data: bytes = b'') -> Optional[bytes]:
        """Send MSP command and receive response"""
        pass

    @abstractmethod
    def _calculate_checksum(self, cmd: int, data: bytes, **kwargs) -> int:
        """Calculate checksum for the protocol version"""
        pass


class MSPv1(MSPBase):
    """MSP Protocol Version 1 implementation"""

    def _calculate_checksum(self, cmd: int, data: bytes, **kwargs) -> int:
        """Calculate MSP v1 XOR checksum"""
        checksum = len(data) ^ cmd
        for byte in data:
            checksum ^= byte
        return checksum

    def send_command(self, cmd: int, data: bytes = b'') -> Optional[bytes]:
        """Send MSP v1 command and receive response"""
        message = bytearray([ord('$'), ord('M'), ord('<')])
        message.append(len(data))
        message.append(cmd)
        message.extend(data)
        checksum = self._calculate_checksum(cmd, data)
        message.append(checksum)

        self.serial.write(message)
        self.serial.flush()

        return self._read_response()

    def _read_response(self, timeout: float = 1.0) -> Optional[bytes]:
        """Read MSP v1 response from serial port"""
        start_time = time.time()

        header_found = False
        while time.time() - start_time < timeout:
            byte = self.serial.read(1)
            if not byte:
                continue
            if byte == b'$':
                if self.serial.read(1) == b'M':
                    direction = self.serial.read(1)
                    if direction == b'>':
                        header_found = True
                        break

        if not header_found:
            return None

        size_byte = self.serial.read(1)
        if not size_byte:
            return None
        size = ord(size_byte)

        cmd_byte = self.serial.read(1)
        if not cmd_byte:
            return None

        data = self.serial.read(size)
        if len(data) != size:
            return None

        checksum_byte = self.serial.read(1)
        if not checksum_byte:
            return None

        return data


class MSPv2(MSPBase):
    """MSP Protocol Version 2 implementation"""

    def _crc8_dvb_s2(self, crc: int, ch: int) -> int:
        """CRC8-DVB-S2 algorithm"""
        crc ^= ch
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) & 0xFF) ^ 0xD5
            else:
                crc = (crc << 1) & 0xFF
        return crc

    def _calculate_checksum(self, cmd: int, data: bytes, flag: int = 0, **kwargs) -> int:
        """Calculate MSP v2 CRC8-DVB-S2 checksum"""
        crc = 0
        crc = self._crc8_dvb_s2(crc, flag)
        crc = self._crc8_dvb_s2(crc, cmd & 0xFF)
        crc = self._crc8_dvb_s2(crc, (cmd >> 8) & 0xFF)
        crc = self._crc8_dvb_s2(crc, len(data) & 0xFF)
        crc = self._crc8_dvb_s2(crc, (len(data) >> 8) & 0xFF)
        for byte in data:
            crc = self._crc8_dvb_s2(crc, byte)
        return crc

    def send_command(self, cmd: int, data: bytes = b'') -> Optional[bytes]:
        """Send MSP v2 command and receive response"""
        message = bytearray([ord('$'), ord('X'), ord('<')])
        flag = 0
        message.append(flag)
        message.append(cmd & 0xFF)
        message.append((cmd >> 8) & 0xFF)
        message.append(len(data) & 0xFF)
        message.append((len(data) >> 8) & 0xFF)
        message.extend(data)
        checksum = self._calculate_checksum(cmd, data, flag)
        message.append(checksum)

        self.serial.write(message)
        self.serial.flush()

        return self._read_response()

    def _read_response(self, timeout: float = 1.0) -> Optional[bytes]:
        """Read MSP v2 response from serial port"""
        start_time = time.time()

        header_found = False
        while time.time() - start_time < timeout:
            byte = self.serial.read(1)
            if not byte:
                continue
            if byte == b'$':
                if self.serial.read(1) == b'X':
                    direction = self.serial.read(1)
                    if direction == b'>':
                        header_found = True
                        break

        if not header_found:
            return None

        flag_byte = self.serial.read(1)
        if not flag_byte:
            return None
        flag = ord(flag_byte)

        cmd_low = self.serial.read(1)
        cmd_high = self.serial.read(1)
        if not cmd_low or not cmd_high:
            return None

        size_low = self.serial.read(1)
        size_high = self.serial.read(1)
        if not size_low or not size_high:
            return None
        size = ord(size_low) | (ord(size_high) << 8)

        data = self.serial.read(size)
        if len(data) != size:
            return None

        checksum_byte = self.serial.read(1)
        if not checksum_byte:
            return None

        return data


class FlightController:
    """High-level flight controller interface"""

    # Serial function bit flags
    FUNCTION_MSP = 0
    FUNCTION_GPS = 1
    FUNCTION_TELEMETRY_FRSKY = 2
    FUNCTION_TELEMETRY_HOTT = 3
    FUNCTION_TELEMETRY_LTM = 4
    FUNCTION_TELEMETRY_SMARTPORT = 5
    FUNCTION_RX_SERIAL = 6
    FUNCTION_BLACKBOX = 7

    def __init__(self, port: str, baudrate: int = 115200):
        self.serial = serial.Serial(port, baudrate, timeout=1)
        self.port = port
        time.sleep(2)

        self.msp_v1 = MSPv1(self.serial)
        self.msp_v2 = MSPv2(self.serial)

    def _send_command(self, cmd: int, data: bytes = b'') -> Optional[bytes]:
        """Send command using appropriate protocol version"""
        if cmd < 255:
            return self.msp_v1.send_command(cmd, data)
        else:
            return self.msp_v2.send_command(cmd, data)

    def test_connection(self) -> bool:
        """Test if the flight controller responds"""
        try:
            response = self._send_command(MSPCodes.MSP_API_VERSION)
            return response is not None and len(response) >= 3
        except Exception:
            return False

    def get_fc_info(self) -> dict:
        """Get flight controller information"""
        info = {}

        response = self._send_command(MSPCodes.MSP_FC_VARIANT)
        if response:
            info['variant'] = response[:4].decode('ascii', errors='ignore')

        response = self._send_command(MSPCodes.MSP_FC_VERSION)
        if response and len(response) >= 3:
            info['fc_version'] = f"{response[0]}.{response[1]}.{response[2]}"

        return info

    def get_serial_config(self) -> List[Dict]:
        """Get serial port configuration"""
        response = self._send_command(MSPCodes.MSP2_CF_SERIAL_CONFIG)

        ports = []
        if response:
            num_ports = len(response) // 9
            for i in range(num_ports):
                offset = i * 9
                identifier = response[offset]
                functions = struct.unpack('<I', response[offset+1:offset+5])[0]
                msp_baudrate = response[offset+5]
                gps_baudrate = response[offset+6]
                telemetry_baudrate = response[offset+7]
                peripheral_baudrate = response[offset+8]

                if identifier == 20:  # Skip VCP
                    continue

                ports.append({
                    'identifier': identifier,
                    'functions': functions,
                    'msp_baudrate': msp_baudrate,
                    'gps_baudrate': gps_baudrate,
                    'telemetry_baudrate': telemetry_baudrate,
                    'peripheral_baudrate': peripheral_baudrate
                })

        return ports

    def set_serial_config(self, ports: List[Dict]):
        """Set serial port configuration"""
        data = bytearray()

        for port in ports:
            data.append(port['identifier'])
            data.extend(struct.pack('<I', port['functions']))
            data.append(port['msp_baudrate'])
            data.append(port['gps_baudrate'])
            data.append(port['telemetry_baudrate'])
            data.append(port['peripheral_baudrate'])

        self._send_command(MSPCodes.MSP2_SET_CF_SERIAL_CONFIG, bytes(data))

    def get_current_meter_config(self) -> dict:
        """Get current meter configuration (scale, offset, type, capacity)"""
        response = self._send_command(MSPCodes.MSP_CURRENT_METER_CONFIG)
        config = {}
        if response and len(response) >= 7:
            scale, offset, sensor_type, capacity = struct.unpack_from('<hhBH', response)
            config['scale'] = scale
            config['offset'] = offset
            config['sensor_type'] = sensor_type
            config['capacity'] = capacity
        return config

    def get_analog_data(self) -> dict:
        """Get analog sensor data (RSSI, voltage, current)"""
        response = self._send_command(MSPCodes.MSPV2_INAV_ANALOG)

        analog_data = {}
        if response and len(response) >= 20:
            offset = 0
            offset += 1  # Skip flags byte
            analog_data['voltage'] = struct.unpack('<H', response[offset:offset+2])[0] / 100.0
            offset += 2
            analog_data['current'] = struct.unpack('<h', response[offset:offset+2])[0] / 100.0
            offset += 18
            analog_data['rssi'] = struct.unpack('<H', response[offset:offset+2])[0]

        return analog_data

    def save_to_eeprom(self):
        """Save settings to EEPROM"""
        self._send_command(MSPCodes.MSP_EEPROM_WRITE)
        time.sleep(1)

    def reboot(self):
        """Reboot the flight controller"""
        self._send_command(MSPCodes.MSP_SET_REBOOT)

    def get_motor_config(self) -> Tuple[int, int]:
        """Get motor and servo count"""
        response = self._send_command(MSPCodes.MSP2_INAV_MIXER)

        motor_count = 0
        servo_count = 0

        if response and len(response) >= 9:
            motor_count = struct.unpack('<b', response[7:8])[0]
            servo_count = struct.unpack('<b', response[8:9])[0]

        return motor_count, servo_count

    def get_output_mapping(self) -> List[Dict]:
        """Get physical PWM output mapping via MSPV2_INAV_OUTPUT_MAPPING_EXT2.
        Returns one entry per non-input timer output (6 bytes each):
          timerId (uint8) | usageFlags (uint32 LE) | specialLabels (uint8)
        timerId == timer2id() == index into timerDefinitions[], same key used by SET_TIMER_OUTPUT_MODE.
        """
        response = self._send_command(MSPCodes.MSPV2_INAV_OUTPUT_MAPPING_EXT2)
        outputs = []
        if response:
            for i in range(len(response) // 6):
                offset = i * 6
                timer_id, usage_flags, special_labels = struct.unpack_from('<BIB', response, offset)
                outputs.append({
                    'index': i,
                    'timerId': timer_id,
                    'usageFlags': usage_flags,
                    'specialLabels': special_labels,
                    'isMotor': bool(usage_flags & (1 << 2)),   # TIM_USE_MOTOR
                    'isServo': bool(usage_flags & (1 << 3)),   # TIM_USE_SERVO
                    'isLED':   bool(usage_flags & (1 << 24)),  # TIM_USE_LED
                })
        return outputs

    def get_timer_output_modes(self) -> Dict[int, int]:
        """Get timer output mode overrides: {timerId: mode}.
        Mode: 0=AUTO, 1=MOTORS, 2=SERVOS, 3=LED.
        """
        response = self._send_command(MSPCodes.MSP2_INAV_TIMER_OUTPUT_MODE)
        modes = {}
        if response:
            for i in range(0, len(response) - 1, 2):
                timer_id = response[i]
                mode = response[i + 1]
                modes[timer_id] = mode
        return modes

    def set_timer_output_mode(self, timer_id: int, mode: int):
        """Set output mode override for one timer (0=AUTO, 1=MOTORS, 2=SERVOS, 3=LED)."""
        data = struct.pack('<BB', timer_id, mode)
        self._send_command(MSPCodes.MSP2_INAV_SET_TIMER_OUTPUT_MODE, data)

    def get_servo_mixer_rules(self) -> List[Dict]:
        """Get servo mixer rules via MSP2_INAV_SERVO_MIXER (0x2020).
        6 bytes per rule: target(u8), input(u8), rate(s16LE), speed(u8), conditionId(s8).
        """
        response = self._send_command(MSPCodes.MSP2_INAV_SERVO_MIXER)
        rules = []
        if response:
            for i in range(len(response) // 6):
                offset = i * 6
                target, input_src, rate, speed, cond_id = struct.unpack_from('<BBhBb', response, offset)
                rules.append({
                    'index': i,
                    'target': target,
                    'input': input_src,
                    'rate': rate,
                    'speed': speed,
                    'conditionId': cond_id,
                })
        return rules

    def set_servo_mixer_rule(self, rule_index: int, target: int, input_src: int,
                             rate: int, speed: int = 0, condition_id: int = -1):
        """Set one servo mixer rule via MSP2_INAV_SET_SERVO_MIXER (0x2021).
        rate: -1000..+1000 (sign=direction, magnitude=percent×10, so -150 = 15% toward min).
        input_src: INPUT_MAX=29 gives constant full-scale (+1.0) input.
        """
        data = struct.pack('<BBBhBb', rule_index, target, input_src, rate, speed, condition_id)
        self._send_command(MSPCodes.MSP2_INAV_SET_SERVO_MIXER, data)

    def set_motor_mixer_entry(self, motor_index: int,
                              throttle: float, roll: float, pitch: float, yaw: float):
        """Set one motor mixer entry via MSP2_COMMON_SET_MOTOR_MIXER (0x1006).
        Wire encoding: wire = int((float + 2.0) * 1000), so 1.0 → 3000, 0.0 → 2000.
        """
        def to_wire(f: float) -> int:
            return int(max(0, min(4000, (f + 2.0) * 1000)))

        data = struct.pack('<BHHHH', motor_index,
                           to_wire(throttle), to_wire(roll), to_wire(pitch), to_wire(yaw))
        self._send_command(MSPCodes.MSP2_COMMON_SET_MOTOR_MIXER, data)

    def enable_pwm_output(self):
        """Enable PWM output feature"""
        response = self._send_command(MSPCodes.MSP_FEATURE)
        if response is None or len(response) < 4:
            raise Exception("Failed to read features")

        current_features = struct.unpack('<I', response)[0]
        new_features = current_features | (1 << 28)

        data = struct.pack('<I', new_features)
        self._send_command(MSPCodes.MSP_SET_FEATURE, data)

    def set_motor_values(self, motor_values: List[int]):
        """Set motor throttle values"""
        data = bytearray()
        for i in range(8):
            if i < len(motor_values):
                value = motor_values[i]
            else:
                value = 1000
            data.extend(struct.pack('<H', value))

        self._send_command(MSPCodes.MSP_SET_MOTOR, bytes(data))

    def close(self):
        """Close connection"""
        self.serial.close()


# Global state
fc_manager = {
    'fc': None,
    'port': None,
    'motors_running': False,
    'adc_monitoring': False,
    'port_data': [],
    'port_original_functions': [],
    'tester_serial': None,
    'tester_port': None,
    'elrs_testing': False,
    'elrs_in_passthrough': False,
}


def emit_connection_error(message='No flight controller connected'):
    """Emit both a log line and a dedicated connection_error event.

    The scrolling log panel is easy to miss during bench testing, so
    connection failures also need an event the client renders as a
    banner/toast that interrupts the user.
    """
    emit('log', {'message': message})
    emit('connection_error', {'message': message})


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('log', {'message': 'Connected to server'})
    auto_connect()
    auto_connect_tester()


@socketio.on('reconnect_fc')
def handle_reconnect():
    """Handle reconnection request"""
    auto_connect()


@socketio.on('reconnect_tester')
def handle_reconnect_tester():
    """Handle tester reconnection request"""
    auto_connect_tester()


@socketio.on('reboot_fc')
def handle_reboot():
    """Handle FC reboot request"""
    if not fc_manager['fc']:
        emit_connection_error()
        return

    try:
        emit('log', {'message': 'Sending reboot command...'})
        fc_manager['fc'].reboot()
        emit('log', {'message': 'Flight controller rebooting...'})

        disconnect_fc()
        emit('status', {'connected': False, 'info': 'FC rebooting...'})

        # Schedule reconnection after 5 seconds
        socketio.start_background_task(delayed_reconnect)
    except Exception as e:
        emit('log', {'message': f'Reboot error: {e}'})


def delayed_reconnect():
    """Reconnect after delay"""
    time.sleep(5)
    auto_connect()


@socketio.on('shutdown_system')
def handle_shutdown():
    """Handle system shutdown request"""
    try:
        emit('log', {'message': 'Shutting down system...'})
        socketio.emit('log', {'message': 'System shutting down in 3 seconds...'})

        # Disconnect FC first
        disconnect_fc()

        # Schedule shutdown after a short delay to allow message to be sent
        def shutdown_delayed():
            time.sleep(3)
            try:
                subprocess.run(['/sbin/poweroff'], check=True)
            except subprocess.CalledProcessError as e:
                socketio.emit('log', {'message': f'Shutdown failed: {e}. Try: sudo poweroff'})
            except FileNotFoundError:
                # Try alternative commands
                try:
                    subprocess.run(['sudo', 'poweroff'], check=True)
                except Exception as e2:
                    socketio.emit('log', {'message': f'Shutdown failed: {e2}'})

        socketio.start_background_task(shutdown_delayed)
        emit('log', {'message': 'Shutdown initiated. Goodbye!'})

    except Exception as e:
        emit('log', {'message': f'Shutdown error: {e}'})


@socketio.on('send_tester_command')
def handle_tester_command(data):
    """Send a raw command character to the tester Arduino via /dev/ttyUSB*"""
    cmd = data.get('command', '')
    if cmd not in ('r', 's'):
        emit('log', {'message': f'Unknown tester command: {cmd}'})
        return

    if not fc_manager['tester_serial']:
        emit('log', {'message': 'No tester device connected (/dev/ttyUSB*)'})
        return

    try:
        label = 'SBUS' if cmd == 's' else 'RX-Only'
        emit('log', {'message': f'Sending {label} test command...'})
        for _ in range(2):
            fc_manager['tester_serial'].write(f'{cmd}\n'.encode('utf-8'))
            fc_manager['tester_serial'].flush()
            time.sleep(0.5)
        emit('log', {'message': f'{label} test command sent'})
    except Exception as e:
        emit('log', {'message': f'Error sending tester command: {e}'})


@socketio.on('load_serial_config')
def handle_load_serial():
    """Load serial configuration"""
    if not fc_manager['fc']:
        emit_connection_error()
        return

    try:
        ports = fc_manager['fc'].get_serial_config()
        fc_manager['port_data'] = ports
        fc_manager['port_original_functions'] = [
            p['functions'] & ~(1 << FlightController.FUNCTION_MSP) for p in ports
        ]

        # Format for web display
        port_list = []
        for port in ports:
            port_name = f"UART{port['identifier']+1}" if port['identifier'] < 30 else f"SOFTSERIAL{port['identifier']-30+1}"
            msp_enabled = bool(port['functions'] & (1 << FlightController.FUNCTION_MSP))

            functions = []
            if port['functions'] & (1 << FlightController.FUNCTION_GPS):
                functions.append("GPS")
            if port['functions'] & (1 << FlightController.FUNCTION_RX_SERIAL):
                functions.append("RX_SERIAL")
            if port['functions'] & (1 << FlightController.FUNCTION_BLACKBOX):
                functions.append("BLACKBOX")
            if port['functions'] & (1 << FlightController.FUNCTION_TELEMETRY_FRSKY):
                functions.append("FRSKY")
            if port['functions'] & (1 << FlightController.FUNCTION_TELEMETRY_SMARTPORT):
                functions.append("SMARTPORT")

            port_list.append({
                'name': port_name,
                'identifier': port['identifier'],
                'msp_enabled': msp_enabled,
                'functions': ', '.join(functions) if functions else 'None'
            })

        emit('serial_config', {'ports': port_list})
        emit('log', {'message': f'Loaded configuration for {len(ports)} serial ports'})
    except Exception as e:
        emit('log', {'message': f'Failed to load serial config: {e}'})


@socketio.on('toggle_msp')
def handle_toggle_msp(data):
    """Toggle MSP on a port"""
    port_id = data['port_id']
    enabled = data['enabled']

    if not fc_manager['fc']:
        emit_connection_error()
        return

    # Find the port index
    idx = None
    for i, port in enumerate(fc_manager['port_data']):
        if port['identifier'] == port_id:
            idx = i
            break

    if idx is None:
        emit('log', {'message': f'Port {port_id} not found'})
        return

    # Check if we're exceeding limit
    msp_count = sum(1 for p in fc_manager['port_data']
                   if p['functions'] & (1 << FlightController.FUNCTION_MSP))

    if enabled and msp_count >= 2:
        emit('log', {'message': 'Maximum of 2 ports can have MSP enabled'})
        emit('msp_toggle_rejected', {'port_id': port_id})
        return

    port = fc_manager['port_data'][idx]
    original_functions = fc_manager['port_original_functions'][idx]

    if enabled:
        port['functions'] = (1 << FlightController.FUNCTION_MSP)
    else:
        port['functions'] = original_functions

    if not _reconnect_and_retry(lambda: fc_manager['fc'].set_serial_config(fc_manager['port_data'])):
        return

    # Reload config to update display
    handle_load_serial()


@socketio.on('save_serial_config')
def handle_save_serial():
    """Save serial configuration to EEPROM"""
    if not fc_manager['fc']:
        emit_connection_error()
        return

    def _do_save():
        fc_manager['fc'].set_serial_config(fc_manager['port_data'])
        fc_manager['fc'].save_to_eeprom()

    try:
        if not _reconnect_and_retry(_do_save):
            return
    except Exception as e:
        emit('log', {'message': f'Failed to save serial config: {e}'})
        return

    # Update original functions
    for idx, port in enumerate(fc_manager['port_data']):
        fc_manager['port_original_functions'][idx] = port['functions'] & ~(1 << FlightController.FUNCTION_MSP)

    emit('log', {'message': 'Serial configuration saved successfully'})

    # Reboot
    handle_reboot()


@socketio.on('start_motor_test')
def handle_start_motor_test():
    """Start motor test"""
    if fc_manager['motors_running']:
        emit('log', {'message': 'Motor test already running'})
        return

    if not fc_manager['fc']:
        emit_connection_error()
        return

    socketio.start_background_task(motor_test_thread)


def motor_test_thread():
    """Motor test worker"""
    try:
        fc_manager['motors_running'] = True
        socketio.emit('motor_status', {'running': True})

        socketio.emit('log', {'message': 'Enabling PWM output...'})
        fc_manager['fc'].enable_pwm_output()
        fc_manager['fc'].save_to_eeprom()

        socketio.emit('log', {'message': 'Getting motor configuration...'})
        motor_count, servo_count = fc_manager['fc'].get_motor_config()
        socketio.emit('log', {'message': f'Found {motor_count} motors, {servo_count} servos'})

        if motor_count == 0:
            socketio.emit('log', {'message': 'No motors configured!'})
            return

        MIN_THROTTLE = 1000
        MAX_THROTTLE = 2000
        throttle_range = MAX_THROTTLE - MIN_THROTTLE

        motor_values = []
        for i in range(motor_count):
            percentage = 15 + (i * 10)
            throttle_value = MIN_THROTTLE + int((percentage / 100.0) * throttle_range)
            motor_values.append(throttle_value)
            socketio.emit('log', {'message': f'Motor {i+1}: {percentage}% = {throttle_value} µs'})

        socketio.emit('log', {'message': 'Setting motor values...'})
        fc_manager['fc'].set_motor_values(motor_values)
        socketio.emit('log', {'message': 'Motors spinning! Click Stop to stop.'})

        while fc_manager['motors_running']:
            time.sleep(0.1)

    except Exception as e:
        socketio.emit('log', {'message': f'Motor test error: {e}'})
    finally:
        stop_motors()


@socketio.on('stop_motors')
def handle_stop_motors():
    """Stop motors"""
    stop_motors()


def stop_motors():
    """Internal stop motors function"""
    if not fc_manager['motors_running']:
        return

    fc_manager['motors_running'] = False

    try:
        if fc_manager['fc']:
            motor_count, _ = fc_manager['fc'].get_motor_config()
            fc_manager['fc'].set_motor_values([1000] * motor_count)
            socketio.emit('log', {'message': 'Motors stopped'})
            socketio.emit('motor_status', {'running': False})
    except Exception as e:
        socketio.emit('log', {'message': f'Error stopping motors: {e}'})


@socketio.on('start_adc_monitoring')
def handle_start_adc():
    """Start ADC monitoring"""
    if fc_manager['adc_monitoring']:
        return

    if not fc_manager['fc']:
        emit_connection_error()
        return

    fc_manager['adc_monitoring'] = True
    emit('adc_status', {'monitoring': True})
    emit('log', {'message': 'ADC monitoring started'})

    socketio.start_background_task(adc_monitoring_thread)


def adc_monitoring_thread():
    """ADC monitoring worker"""
    LOAD_RESISTANCE = 1.11  # ohms
    current_scale = None

    # Fetch current meter scale once at start
    try:
        meter_cfg = fc_manager['fc'].get_current_meter_config()
        current_scale = meter_cfg.get('scale')
    except Exception:
        pass

    while fc_manager['adc_monitoring'] and fc_manager['fc']:
        try:
            data = fc_manager['fc'].get_analog_data()

            voltage = data.get('voltage', 0)
            current = data.get('current', 0)
            rssi = data.get('rssi', 0)

            current_check = None
            if voltage > 0.5 and current > 0.1:
                expected_current = voltage / LOAD_RESISTANCE
                pct_error = (current - expected_current) / expected_current * 100
                # if abs(pct_error) > 10:
                direction = 'high' if pct_error > 0 else 'low'
                msg = (f'Current {current:.1f}A is {abs(pct_error):.0f}% '
                       f'too {direction} for voltage {voltage:.1f}V')
                if current_scale is not None:
                    correction = current / expected_current
                    suggested_scale = int(round(current_scale * correction))
                    msg += f' (scale: {current_scale} -> {suggested_scale})'
                current_check = msg

            socketio.emit('adc_data', {
                'voltage': f'{voltage:.2f}',
                'current': f'{current:.2f}',
                'rssi': rssi,
                'current_check': current_check,
            })

            time.sleep(0.2)
        except Exception as e:
            socketio.emit('log', {'message': f'ADC error: {e}'})
            fc_manager['adc_monitoring'] = False
            socketio.emit('adc_status', {'monitoring': False})
            break


@socketio.on('stop_adc_monitoring')
def handle_stop_adc():
    """Stop ADC monitoring"""
    fc_manager['adc_monitoring'] = False
    emit('adc_status', {'monitoring': False})
    emit('log', {'message': 'ADC monitoring stopped'})


@socketio.on('test_elrs_rx')
def handle_test_elrs_rx():
    """Run ELRS receiver detection via CLI serial passthrough."""
    if fc_manager['elrs_testing']:
        emit('log', {'message': 'ELRS test already running'})
        return

    if fc_manager['elrs_in_passthrough']:
        emit('log', {'message': 'FC is in passthrough mode — power-cycle FC to restore'})
        return

    if not fc_manager['fc']:
        emit_connection_error()
        return

    port = fc_manager['port']

    # Release MSP connection — passthrough needs exclusive port access
    disconnect_fc()
    socketio.emit('status', {'connected': False, 'info': 'FC in ELRS test mode'})

    fc_manager['elrs_testing'] = True
    socketio.emit('elrs_status', {'testing': True, 'in_passthrough': False})
    socketio.start_background_task(_elrs_test_thread, port)


def _elrs_test_thread(port):
    """Background worker for ELRS receiver detection."""
    def log(msg):
        socketio.emit('log', {'message': msg})

    try:
        result = detect_elrs(port, allow_bootloader=False, log_fn=log)
    except Exception as e:
        result = {
            'found': False, 'stage': 0,
            'rx_pin': False, 'tx_pin': False,
            'name': None, 'fw_version': None, 'target': None,
            'error': str(e),
        }

    fc_manager['elrs_testing'] = False
    fc_manager['elrs_in_passthrough'] = (result['error'] is None)

    socketio.emit('elrs_result', result)
    socketio.emit('elrs_status', {
        'testing': False,
        'in_passthrough': fc_manager['elrs_in_passthrough'],
    })


def auto_connect():
    """Auto-connect to flight controller"""
    disconnect_fc()

    ports = sorted(glob.glob('/dev/ttyACM*'))

    if not ports:
        socketio.emit('log', {'message': 'No /dev/ttyACM* ports found'})
        socketio.emit('status', {'connected': False, 'info': 'No ports found'})
        return

    for port in ports:
        try:
            socketio.emit('log', {'message': f'Trying {port}...'})
            fc = FlightController(port)
            if fc.test_connection():
                fc_manager['fc'] = fc
                fc_manager['port'] = port
                info = fc.get_fc_info()
                variant = info.get('variant', 'Unknown')
                version = info.get('fc_version', 'Unknown')

                info_text = f"{variant} v{version} on {port}"
                fc_manager['elrs_in_passthrough'] = False
                socketio.emit('elrs_status', {'testing': False, 'in_passthrough': False})
                socketio.emit('status', {'connected': True, 'info': info_text})
                socketio.emit('log', {'message': f'Connected to {variant} v{version}'})
                return
            else:
                fc.close()
        except Exception as e:
            socketio.emit('log', {'message': f'Error on {port}: {e}'})

    socketio.emit('log', {'message': 'No flight controller found'})
    socketio.emit('status', {'connected': False, 'info': 'No FC found'})


@socketio.on('configure_test_mixer')
def handle_configure_test_mixer():
    """Write test motor/servo mixer entries based on current output assignments.

    Motors: throttle=roll=pitch=yaw=1.0 (equal weight on all axes).
    Servos: INPUT_MAX with rates -150, -250, -350, ... (servo 0=15%, 1=25%, 2=35%, ...)
            so each servo sits at a progressively different position for visual inspection.
    """
    if not fc_manager['fc']:
        emit_connection_error()
        return

    try:
        outputs = fc_manager['fc'].get_output_mapping()
        modes = fc_manager['fc'].get_timer_output_modes()

        motor_idx = 0
        servo_idx = 0
        servo_rule_idx = 0

        for out in outputs:
            override = modes.get(out['timerId'], 0)
            # Explicit override takes priority; AUTO falls back to usageFlags
            if override == 1:
                is_motor, is_servo = True, False
            elif override == 2:
                is_motor, is_servo = False, True
            else:
                is_motor = out['isMotor']
                is_servo = out['isServo']

            if is_motor:
                fc_manager['fc'].set_motor_mixer_entry(motor_idx, 1.0, 1.0, 1.0, 1.0)
                emit('log', {'message': f'Motor {motor_idx + 1}: throttle=1 roll=1 pitch=1 yaw=1'})
                motor_idx += 1
            elif is_servo:
                # Each servo gets 10% more deflection: -150(15%), -250(25%), -350(35%)…
                rate = -(150 + servo_idx * 100)
                rate_pct = abs(rate) // 10
                fc_manager['fc'].set_servo_mixer_rule(
                    servo_rule_idx, servo_idx, INPUT_MAX, rate, speed=0, condition_id=-1)
                emit('log', {'message': f'Servo {servo_idx + 1}: INPUT_MAX rate={rate} ({rate_pct}%)'})
                servo_idx += 1
                servo_rule_idx += 1

        emit('log', {'message': f'Test mixer done: {motor_idx} motor(s), {servo_idx} servo(s). '
                                 f'Save & Reboot to apply.'})
        emit('test_mixer_done', {'motors': motor_idx, 'servos': servo_idx})
    except Exception as e:
        emit('log', {'message': f'Error configuring test mixer: {e}'})


@socketio.on('load_outputs')
def handle_load_outputs():
    """Load physical PWM output mapping and current mode overrides"""
    if not fc_manager['fc']:
        emit_connection_error()
        return

    try:
        outputs = fc_manager['fc'].get_output_mapping()
        modes = fc_manager['fc'].get_timer_output_modes()
        motor_count, servo_count = fc_manager['fc'].get_motor_config()

        motor_num = 1
        servo_num = 1
        output_list = []
        for out in outputs:
            override_mode = modes.get(out['timerId'], 0)

            if out['isLED'] or out['specialLabels'] == 1:
                label = 'LED Strip'
            elif out['isMotor']:
                label = f'Motor {motor_num}'
                motor_num += 1
            elif out['isServo']:
                label = f'Servo {servo_num}'
                servo_num += 1
            else:
                label = 'Unassigned'

            output_list.append({
                'index': out['index'],
                'timerId': out['timerId'],
                'label': label,
                'isMotor': out['isMotor'],
                'isServo': out['isServo'],
                'isLED': out['isLED'],
                'overrideMode': override_mode,
            })

        emit('outputs_data', {
            'outputs': output_list,
            'motorCount': motor_count,
            'servoCount': servo_count,
        })
        emit('log', {'message': f'Loaded {len(outputs)} outputs ({motor_count} motors, {servo_count} servos)'})
    except Exception as e:
        emit('log', {'message': f'Failed to load outputs: {e}'})


@socketio.on('set_output_mode')
def handle_set_output_mode(data):
    """Set output mode override for one timer"""
    timer_id = data.get('timer_id')
    mode = data.get('mode')

    if not fc_manager['fc']:
        emit_connection_error()
        return

    mode_names = {0: 'Auto', 1: 'Motor', 2: 'Servo', 3: 'LED'}

    def _do_set():
        fc_manager['fc'].set_timer_output_mode(timer_id, mode)

    if not _reconnect_and_retry(_do_set):
        return

    emit('log', {'message': f'Timer {timer_id} → {mode_names.get(mode, mode)}'})


@socketio.on('save_outputs')
def handle_save_outputs():
    """Save output config to EEPROM and reboot"""
    if not fc_manager['fc']:
        emit_connection_error()
        return

    def _do_save():
        fc_manager['fc'].save_to_eeprom()

    if not _reconnect_and_retry(_do_save):
        return

    emit('log', {'message': 'Output configuration saved to EEPROM'})
    handle_reboot()


def auto_connect_tester():
    """Auto-connect to diagnostic tester device on /dev/ttyUSB*"""
    if fc_manager['tester_serial']:
        try:
            fc_manager['tester_serial'].close()
        except Exception:
            pass
        fc_manager['tester_serial'] = None
        fc_manager['tester_port'] = None

    ports = sorted(glob.glob('/dev/ttyUSB*'))
    if not ports:
        socketio.emit('log', {'message': 'No /dev/ttyUSB* tester found'})
        socketio.emit('tester_status', {'connected': False})
        return

    for port in ports:
        try:
            ser = serial.Serial(port, baudrate=115200, timeout=3)
            data = ser.read(64)
            if data and b'Command' in data:
                fc_manager['tester_serial'] = ser
                fc_manager['tester_port'] = port
                socketio.emit('log', {'message': f'Tester connected on {port}'})
                socketio.emit('tester_status', {'connected': True, 'port': port})
                return
            ser.close()
        except Exception as e:
            socketio.emit('log', {'message': f'Tester error on {port}: {e}'})

    socketio.emit('log', {'message': 'No tester device found on /dev/ttyUSB*'})
    socketio.emit('tester_status', {'connected': False})


def disconnect_fc():
    """Disconnect flight controller"""
    if fc_manager['motors_running']:
        stop_motors()

    if fc_manager['adc_monitoring']:
        fc_manager['adc_monitoring'] = False

    if fc_manager['fc']:
        try:
            fc_manager['fc'].close()
        except:
            pass
        fc_manager['fc'] = None
        fc_manager['port'] = None


def _reconnect_and_retry(action_fn):
    """Try action_fn(), reconnect on serial disconnect, retry once.

    Emits fc_disconnected to the browser if still unreachable after reconnect.
    Returns True on success, False if the command could not be sent.
    """
    try:
        action_fn()
        return True
    except serial.SerialException:
        pass

    socketio.emit('log', {'message': 'Serial disconnect detected, reconnecting...'})
    socketio.emit('status', {'connected': False, 'info': 'Reconnecting...'})
    time.sleep(1)
    auto_connect()

    if not fc_manager['fc']:
        socketio.emit('log', {'message': 'Could not reconnect to flight controller'})
        socketio.emit('fc_disconnected', {})
        return False

    try:
        action_fn()
        return True
    except serial.SerialException:
        socketio.emit('log', {'message': 'Command failed after reconnect'})
        socketio.emit('fc_disconnected', {})
        return False


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Flight Controller Web Tool")
    print("="*60)
    print("\nStarting server on port 5000...")
    print("\nAccess from:")
    print("  - This device: http://localhost:5000")
    print("  - Other devices: http://<pi-ip-address>:5000")
    print("\n" + "="*60 + "\n")

    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
