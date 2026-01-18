#!/usr/bin/env python3
"""
串口数据处理
"""
import queue
import threading
import time
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any, Union

import serial
import serial.tools.list_ports


class DataFormat(Enum):
    ASCII = "ascii"
    HEX = "hex"


class SerialAssistant:
    def __init__(self) -> None:
        self.serial_port: serial.Serial | None = None
        self.is_connected: bool = False

        self.rx_queue: queue.Queue[bytes] = queue.Queue(maxsize=10000)
        self.tx_queue: queue.Queue[bytes] = queue.Queue(maxsize=1000)

        self.rx_thread: threading.Thread | None = None
        self.tx_thread: threading.Thread | None = None
        self.auto_send_thread: threading.Thread | None = None
        self.monitor_thread: threading.Thread | None = None
        self.stop_threads: threading.Event = threading.Event()
        self.stop_monitor: threading.Event = threading.Event()

        self.on_data_received: Callable[[bytes], None] | None = None
        self.on_connection_changed: Callable[[bool], None] | None = None
        self.on_auto_reconnect: Callable[[bool, str, bool], None] | None = None

        self._auto_reconnect_enabled: bool = True
        self._reconnect_interval: float = 2.0
        self._last_connected_port: str = ''
        self._reconnect_lock: threading.Lock = threading.Lock()
        self._is_reconnecting: bool = False
        self._connection_lost: bool = False
        self._manual_disconnect: bool = False

        self.config: dict[str, Any] = {
            'port': '',
            'baudrate': 1000000,
            'bytesize': 8,
            'stopbits': 1,
            'parity': 'N',
            'timeout': 0.1,
            'write_timeout': 0.5,
            'rts': False,
            'dtr': True,  # 关键修复: USB CDC需要DTR=True
        }

        self.rx_format: DataFormat = DataFormat.ASCII
        self.rx_paused: bool = False
        self.rx_buffer: bytearray = bytearray()
        self.rx_max_buffer: int = 1024 * 1024

        self.tx_format: DataFormat = DataFormat.ASCII
        self.tx_newline: bool = False
        self.auto_send_enabled: bool = False
        self.auto_send_interval: float = 1.0
        self.auto_send_data: Union[str, bytes] = b''

        self.stats: dict[str, Any] = {
            'rx_bytes': 0,
            'tx_bytes': 0,
            'rx_packets': 0,
            'tx_packets': 0,
            'errors': 0,
            'start_time': None
        }

    def enable_auto_reconnect(
            self,
            enabled: bool = True,
            interval: float = 2.0) -> None:
        self._auto_reconnect_enabled = enabled
        self._reconnect_interval = max(0.5, interval)
        if enabled:
            self._start_monitor()
        elif not enabled:
            self._stop_monitor()

    def is_auto_reconnect_enabled(self) -> bool:
        return self._auto_reconnect_enabled

    def get_last_connected_port(self) -> str:
        return self._last_connected_port

    def set_last_connected_port(self, port: str) -> None:
        self._last_connected_port = port

    def _start_monitor(self) -> None:
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        self.stop_monitor.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_worker, daemon=True)
        self.monitor_thread.start()

    def _stop_monitor(self) -> None:
        self.stop_monitor.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1)

    def _monitor_worker(self) -> None:
        import contextlib
        while not self.stop_monitor.is_set():
            with contextlib.suppress(Exception):
                self._check_connection_status()
            for _ in range(int(self._reconnect_interval * 10)):
                if self.stop_monitor.is_set():
                    break
                time.sleep(0.1)

    def _check_connection_status(self) -> None:
        if not self._auto_reconnect_enabled:
            return
        if self._manual_disconnect:
            return
        with self._reconnect_lock:
            if self._is_reconnecting:
                return
            if self.is_connected and self.serial_port:
                if not self._is_port_healthy():
                    self._connection_lost = True
                    self._handle_connection_lost()
            elif (not self.is_connected
                  and self._last_connected_port
                  and self._connection_lost):
                self._try_reconnect()

    def _is_port_healthy(self) -> bool:
        """检查端口健康状态 - 对USB CDC设备特殊处理"""
        if not self.serial_port:
            return False
        try:
            if not self.serial_port.is_open:
                return False
            # 检查端口是否存在
            current_ports: list[str] = [
                p.device for p in serial.tools.list_ports.comports()]
            # USB CDC设备不检查CTS，只检查端口存在性
            return self.config["port"] in current_ports
        except Exception:
            return False

    def _handle_connection_lost(self) -> None:
        self._cleanup_connection()
        if self.on_connection_changed:
            self.on_connection_changed(False)

    def _cleanup_connection(self) -> None:
        self.stop_auto_send()
        self.stop_threads.set()
        if self.rx_thread and self.rx_thread.is_alive():
            self.rx_thread.join(timeout=0.5)
        if self.tx_thread and self.tx_thread.is_alive():
            self.tx_thread.join(timeout=0.5)
        if self.serial_port:
            try:
                if self.serial_port.is_open:
                    self.serial_port.close()
            except BaseException:
                pass
        self.serial_port = None
        self.is_connected = False
        while not self.rx_queue.empty():
            try:
                self.rx_queue.get_nowait()
            except BaseException:
                break
        while not self.tx_queue.empty():
            try:
                self.tx_queue.get_nowait()
            except BaseException:
                break

    def _try_reconnect(self) -> None:
        if self._is_reconnecting:
            return
        self._is_reconnecting = True
        try:
            target_port: str = self._last_connected_port
            current_ports: list[str] = [
                p.device for p in serial.tools.list_ports.comports()]
            if target_port not in current_ports:
                return
            self.config['port'] = target_port
            if self._connect_internal():
                self._connection_lost = False
                if self.on_auto_reconnect:
                    self.on_auto_reconnect(True, target_port, True)
        finally:
            self._is_reconnecting = False

    def _connect_internal(self) -> bool:
        """内部连接方法 - 修复DTR设置"""
        if self.is_connected:
            return True
        try:
            bytesize_map: dict[int, int] = {
                5: serial.FIVEBITS, 6: serial.SIXBITS,
                7: serial.SEVENBITS, 8: serial.EIGHTBITS}
            stopbits_map: dict[Union[int, float], float] = {
                1: serial.STOPBITS_ONE,
                1.5: serial.STOPBITS_ONE_POINT_FIVE,
                2: serial.STOPBITS_TWO}
            parity_map: dict[str, str] = {
                'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN,
                'O': serial.PARITY_ODD, 'M': serial.PARITY_MARK,
                'S': serial.PARITY_SPACE}

            self.serial_port = serial.Serial()
            self.serial_port.port = self.config['port']
            self.serial_port.baudrate = self.config['baudrate']
            self.serial_port.bytesize = bytesize_map.get(
                self.config['bytesize'], serial.EIGHTBITS)
            self.serial_port.stopbits = stopbits_map.get(
                self.config['stopbits'], serial.STOPBITS_ONE)
            self.serial_port.parity = parity_map.get(
                self.config['parity'], serial.PARITY_NONE)
            self.serial_port.timeout = self.config['timeout']
            self.serial_port.write_timeout = self.config['write_timeout']

            # 关键修复: 打开前先设置为False，打开后再设置为True
            self.serial_port.rts = False
            self.serial_port.dtr = False

            self.serial_port.open()
            time.sleep(0.05)  # 等待端口稳定

            # 关键: 打开后立即设置DTR=True
            self.serial_port.dtr = self.config['dtr']  # 默认True
            self.serial_port.rts = self.config['rts']
            time.sleep(0.1)  # 等待设备响应DTR

            self.is_connected = True
            self.stop_threads.clear()

            self.rx_thread = threading.Thread(
                target=self._rx_worker, daemon=True)
            self.tx_thread = threading.Thread(
                target=self._tx_worker, daemon=True)
            self.rx_thread.start()
            self.tx_thread.start()

            self.stats['start_time'] = datetime.now()
            self.stats['rx_bytes'] = 0
            self.stats['tx_bytes'] = 0
            self.stats['rx_packets'] = 0
            self.stats['tx_packets'] = 0
            self.stats['errors'] = 0

            if self.on_connection_changed:
                self.on_connection_changed(True)

            return True

        except Exception:
            self.is_connected = False
            self.stats['errors'] += 1
            return False

    def try_auto_connect(self, port: str) -> bool:
        current_ports: list[str] = [
            p.device for p in serial.tools.list_ports.comports()
        ]
        if port not in current_ports:
            return False
        self.configure(port=port)
        success: bool = self.connect()
        if success and self.on_auto_reconnect:
            self.on_auto_reconnect(True, port, False)
        return success

    def get_available_ports(self) -> list[dict[str, str]]:
        ports: list[dict[str, str]] = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'port': port.device,
                'description': port.description,
                'hwid': port.hwid
            })
        return ports

    def get_baudrate_list(self) -> list[int]:
        return [
            38400, 57600, 115200, 128000, 230400, 256000,
            460800, 500000, 576000, 921600, 1000000, 1152000,
            1500000, 2000000
        ]

    def configure(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value

    def set_rts_dtr_control(
            self,
            rts: bool | None = None,
            dtr: bool | None = None) -> None:
        if rts is not None:
            self.config['rts'] = rts
        if dtr is not None:
            self.config['dtr'] = dtr
        if self.is_connected and self.serial_port:
            self._apply_rts_dtr_settings()

    def _apply_rts_dtr_settings(self) -> None:
        if not self.serial_port:
            return
        try:
            self.serial_port.rts = self.config['rts']
            self.serial_port.dtr = self.config['dtr']
        except Exception:
            self.stats['errors'] += 1

    def get_rts_dtr_status(self) -> dict[str, Any]:
        if not self.serial_port:
            return {'rts': None, 'dtr': None, 'connected': False}
        try:
            return {
                'rts': self.serial_port.rts,
                'dtr': self.serial_port.dtr,
                'connected': self.is_connected,
                'config_rts': self.config['rts'],
                'config_dtr': self.config['dtr']
            }
        except BaseException:
            return {'rts': None, 'dtr': None, 'connected': self.is_connected}

    def toggle_rts(self) -> bool | None:
        if self.serial_port:
            try:
                self.serial_port.rts = not self.serial_port.rts
                self.config['rts'] = self.serial_port.rts
                return self.serial_port.rts
            except Exception:
                self.stats['errors'] += 1
        return None

    def toggle_dtr(self) -> bool | None:
        if self.serial_port:
            try:
                self.serial_port.dtr = not self.serial_port.dtr
                self.config['dtr'] = self.serial_port.dtr
                return self.serial_port.dtr
            except Exception:
                self.stats['errors'] += 1
        return None

    def reset_target_device(self) -> bool:
        if not self.serial_port:
            return False
        try:
            self.serial_port.rts = True
            self.serial_port.dtr = True
            time.sleep(0.1)
            self.serial_port.rts = False
            self.serial_port.dtr = False
            time.sleep(0.5)
            self.serial_port.rts = self.config['rts']
            self.serial_port.dtr = self.config['dtr']
            return True
        except Exception:
            self.stats['errors'] += 1
            return False

    def connect(self) -> bool:
        if self.is_connected:
            return True
        self._manual_disconnect = False
        success: bool = self._connect_internal()
        if success:
            self._last_connected_port = self.config['port']
            self._connection_lost = False
            if self._auto_reconnect_enabled:
                self._start_monitor()
        return success

    def disconnect(self) -> None:
        if not self.is_connected:
            return
        self._manual_disconnect = True
        self._connection_lost = False
        self.stop_auto_send()
        self.stop_threads.set()
        # 缩短超时时间，线程是 daemon 模式会自动退出
        if self.rx_thread and self.rx_thread.is_alive():
            self.rx_thread.join(timeout=0.3)
        if self.tx_thread and self.tx_thread.is_alive():
            self.tx_thread.join(timeout=0.3)
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.dtr = False
                time.sleep(0.02)  # 缩短等待时间
                self.serial_port.close()
            except BaseException:
                pass
        self.serial_port = None
        self.is_connected = False
        while not self.rx_queue.empty():
            try:
                self.rx_queue.get_nowait()
            except BaseException:
                break
        while not self.tx_queue.empty():
            try:
                self.tx_queue.get_nowait()
            except BaseException:
                break
        if self.on_connection_changed:
            self.on_connection_changed(False)

    def _rx_worker(self) -> None:
        while not self.stop_threads.is_set():
            if not self.serial_port or not self.serial_port.is_open:
                time.sleep(0.01)
                continue
            try:
                if self.serial_port.in_waiting > 0:
                    data: bytes = self.serial_port.read(
                        self.serial_port.in_waiting
                    )
                    if data:
                        self.stats['rx_bytes'] += len(data)
                        self.stats['rx_packets'] += 1
                        if not self.rx_paused:
                            try:
                                self.rx_queue.put(data, timeout=0.01)
                                if self.on_data_received:
                                    self.on_data_received(data)
                            except queue.Full:
                                pass
                else:
                    time.sleep(0.001)
            except serial.SerialException:
                self.stats['errors'] += 1
                if (self._auto_reconnect_enabled
                        and not self._manual_disconnect):
                    self._connection_lost = True
                time.sleep(0.1)
            except Exception:
                self.stats['errors'] += 1
                time.sleep(0.1)

    def _tx_worker(self) -> None:
        while not self.stop_threads.is_set():
            try:
                data: bytes = self.tx_queue.get(timeout=0.1)
                if self.serial_port and self.serial_port.is_open:
                    self.serial_port.write(data)
                    self.serial_port.flush()
                    self.stats['tx_bytes'] += len(data)
                    self.stats['tx_packets'] += 1
            except queue.Empty:
                continue
            except serial.SerialException:
                self.stats['errors'] += 1
                if (self._auto_reconnect_enabled
                        and not self._manual_disconnect):
                    self._connection_lost = True
            except Exception:
                self.stats['errors'] += 1

    def send_data(
            self, data: str, format: DataFormat | None = None) -> bool:
        if not self.is_connected:
            self.stats['errors'] += 1
            return False
        format = format or self.tx_format
        try:
            if format == DataFormat.HEX:
                hex_str: str = data.replace(
                    " ", "").replace("\n", "").replace("\r", "")
                if len(hex_str) % 2 != 0:
                    hex_str = "0" + hex_str
                bytes_data: bytes = bytes.fromhex(hex_str)
            else:
                bytes_data = data.encode('utf-8', errors='ignore')
            if self.tx_newline:
                bytes_data += b'\r\n'
            try:
                self.tx_queue.put(bytes_data, timeout=0.1)
                return True
            except queue.Full:
                self.stats['errors'] += 1
                return False
        except ValueError:
            self.stats['errors'] += 1
            return False
        except Exception:
            self.stats['errors'] += 1
            return False

    def get_received_data(self, format: DataFormat | None = None) -> str:
        format = format or self.rx_format
        data_list: list[bytes] = []
        while not self.rx_queue.empty():
            try:
                data: bytes = self.rx_queue.get_nowait()
                data_list.append(data)
            except queue.Empty:
                break
        if not data_list:
            return ""
        all_data: bytes = b''.join(data_list)
        if format == DataFormat.HEX:
            hex_str: str = ' '.join([f'{b:02X}' for b in all_data])
            return hex_str
        else:
            return all_data.decode('utf-8', errors='replace')

    def clear_rx_buffer(self) -> None:
        while not self.rx_queue.empty():
            try:
                self.rx_queue.get_nowait()
            except BaseException:
                break
        self.rx_buffer.clear()

    def pause_rx(self, paused: bool) -> None:
        self.rx_paused = paused

    def set_rx_format(self, format: DataFormat) -> None:
        self.rx_format = format

    def set_tx_format(self, format: DataFormat) -> None:
        self.tx_format = format

    def set_tx_newline(self, enabled: bool) -> None:
        self.tx_newline = enabled

    def start_auto_send(self, data: str, interval: float) -> None:
        if self.auto_send_thread and self.auto_send_thread.is_alive():
            self.stop_auto_send()
        self.auto_send_enabled = True
        self.auto_send_interval = interval
        self.auto_send_data = data
        self.auto_send_thread = threading.Thread(
            target=self._auto_send_worker, daemon=True)
        self.auto_send_thread.start()

    def stop_auto_send(self) -> None:
        self.auto_send_enabled = False
        if self.auto_send_thread and self.auto_send_thread.is_alive():
            self.auto_send_thread.join(timeout=1)

    def _auto_send_worker(self) -> None:
        while self.auto_send_enabled and not self.stop_threads.is_set():
            if self.is_connected and self.auto_send_data:
                self.send_data(str(self.auto_send_data))
            time.sleep(self.auto_send_interval)

    def get_statistics(self) -> dict[str, Any]:
        stats: dict[str, Any] = self.stats.copy()
        if stats['start_time']:
            elapsed = datetime.now() - stats['start_time']
            duration: float = elapsed.total_seconds()
            stats['duration'] = duration
            stats['rx_rate'] = (
                stats['rx_bytes'] / duration if duration > 0 else 0
            )
            stats['tx_rate'] = (
                stats['tx_bytes'] / duration if duration > 0 else 0
            )
        return stats

    def __del__(self) -> None:
        self._stop_monitor()
        self.disconnect()


def format_hex_display(data: bytes, width: int = 16) -> str:
    lines: list[str] = []
    for i in range(0, len(data), width):
        chunk: bytes = data[i:i + width]
        hex_part: str = ' '.join([f'{b:02X}' for b in chunk])
        ascii_part: str = ''.join(
            [chr(b) if 32 <= b < 127 else '.' for b in chunk]
        )
        lines.append(f'{i:08X}  {hex_part:<{width * 3}}  {ascii_part}')
    return '\n'.join(lines)


def parse_hex_input(hex_str: str) -> bytes:
    hex_str = ''.join(hex_str.split())
    if len(hex_str) % 2 != 0:
        hex_str = '0' + hex_str
    return bytes.fromhex(hex_str)


def calculate_checksum(data: bytes, method: str = 'sum8') -> int:
    if method == 'sum8':
        return sum(data) & 0xFF
    elif method == 'xor':
        result: int = 0
        for b in data:
            result ^= b
        return result
    elif method == 'crc16':
        crc: int = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    else:
        return 0