#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口助手模块 - 支持自动检测断连和重连
"""
import serial
import serial.tools.list_ports
import threading
import queue
import time
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from enum import Enum

class DataFormat(Enum):
    ASCII = "ascii"
    HEX = "hex"

class SerialAssistant:
    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        
        self.rx_queue = queue.Queue(maxsize=10000)
        self.tx_queue = queue.Queue(maxsize=1000)
        
        self.rx_thread: Optional[threading.Thread] = None
        self.tx_thread: Optional[threading.Thread] = None
        self.auto_send_thread: Optional[threading.Thread] = None
        self.monitor_thread: Optional[threading.Thread] = None  # 连接监控线程
        self.stop_threads = threading.Event()
        self.stop_monitor = threading.Event()  # 单独控制监控线程
        
        self.on_data_received: Optional[Callable] = None
        self.on_connection_changed: Optional[Callable] = None
        # 自动重连回调: (成功?, 端口名, 是否为重连)
        self.on_auto_reconnect: Optional[Callable[[bool, str, bool], None]] = None
        
        # 自动重连配置
        self._auto_reconnect_enabled = True  # 默认启用自动重连
        self._reconnect_interval = 2.0  # 重连检测间隔(秒)
        self._last_connected_port = ''  # 上次成功连接的端口
        self._reconnect_lock = threading.Lock()
        self._is_reconnecting = False  # 防止重复重连
        self._connection_lost = False  # 标记连接是否丢失（用于区分主动断开和意外断开）
        self._manual_disconnect = False  # 标记是否为手动断开
        
        self.config = {
            'port': '',
            'baudrate': 1000000,
            'bytesize': 8,
            'stopbits': 1,
            'parity': 'N',
            'timeout': 0.1,
            'write_timeout': 0.5,
            'rts': False,
            'dtr': False,
        }
        
        self.rx_format = DataFormat.ASCII
        self.rx_paused = False
        self.rx_buffer = bytearray()
        self.rx_max_buffer = 1024 * 1024
        
        self.tx_format = DataFormat.ASCII
        self.tx_newline = False
        self.auto_send_enabled = False
        self.auto_send_interval = 1.0
        self.auto_send_data = b''
        
        self.stats = {
            'rx_bytes': 0,
            'tx_bytes': 0,
            'rx_packets': 0,
            'tx_packets': 0,
            'errors': 0,
            'start_time': None
        }
    
    # =========================================================================
    # 自动重连相关方法
    # =========================================================================
    
    def enable_auto_reconnect(self, enabled: bool = True, interval: float = 2.0):
        """启用/禁用自动重连功能
        
        Args:
            enabled: 是否启用自动重连
            interval: 检测间隔(秒)
        """
        self._auto_reconnect_enabled = enabled
        self._reconnect_interval = max(0.5, interval)  # 最小0.5秒
        
        if enabled and not self.stop_monitor.is_set():
            self._start_monitor()
        elif not enabled:
            self._stop_monitor()
    
    def is_auto_reconnect_enabled(self) -> bool:
        """检查是否启用了自动重连"""
        return self._auto_reconnect_enabled
    
    def get_last_connected_port(self) -> str:
        """获取上次成功连接的端口"""
        return self._last_connected_port
    
    def set_last_connected_port(self, port: str):
        """设置上次连接的端口（用于启动时自动连接）"""
        self._last_connected_port = port
    
    def _start_monitor(self):
        """启动连接监控线程"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        
        self.stop_monitor.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
        self.monitor_thread.start()
    
    def _stop_monitor(self):
        """停止连接监控线程"""
        self.stop_monitor.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1)
    
    def _monitor_worker(self):
        """连接监控工作线程"""
        while not self.stop_monitor.is_set():
            try:
                self._check_connection_status()
            except Exception:
                pass
            
            # 分段sleep，以便更快响应stop信号
            for _ in range(int(self._reconnect_interval * 10)):
                if self.stop_monitor.is_set():
                    break
                time.sleep(0.1)
    
    def _check_connection_status(self):
        """检查连接状态并尝试重连"""
        if not self._auto_reconnect_enabled:
            return
        
        # 如果是手动断开的，不自动重连
        if self._manual_disconnect:
            return
        
        with self._reconnect_lock:
            if self._is_reconnecting:
                return
            
            # 情况1: 已连接，检查连接是否正常
            if self.is_connected and self.serial_port:
                if not self._is_port_healthy():
                    # 连接丢失
                    self._connection_lost = True
                    self._handle_connection_lost()
            
            # 情况2: 未连接但有上次的端口，尝试重连
            elif not self.is_connected and self._last_connected_port and self._connection_lost:
                self._try_reconnect()
    
    def _is_port_healthy(self) -> bool:
        """检查端口是否正常"""
        if not self.serial_port:
            return False
        
        try:
            # 检查端口是否仍然打开
            if not self.serial_port.is_open:
                return False
            
            # 检查端口是否仍然存在于系统中
            current_ports = [p.device for p in serial.tools.list_ports.comports()]
            if self.config['port'] not in current_ports:
                return False
            
            # 尝试读取CTS状态（这是一个轻量级的检查方式）
            # 如果端口已断开，这通常会抛出异常
            try:
                _ = self.serial_port.cts
            except (serial.SerialException, OSError):
                return False
            
            return True
            
        except Exception:
            return False
    
    def _handle_connection_lost(self):
        """处理连接丢失"""
        # 记录端口信息
        lost_port = self.config['port']
        
        # 清理当前连接
        self._cleanup_connection()
        
        # 通知连接状态变化
        if self.on_connection_changed:
            self.on_connection_changed(False)
    
    def _cleanup_connection(self):
        """清理连接资源（内部使用，不触发回调）"""
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
            except:
                pass
        
        self.serial_port = None
        self.is_connected = False
        
        # 清空队列
        while not self.rx_queue.empty():
            try:
                self.rx_queue.get_nowait()
            except:
                break
        while not self.tx_queue.empty():
            try:
                self.tx_queue.get_nowait()
            except:
                break
    
    def _try_reconnect(self):
        """尝试重新连接"""
        if self._is_reconnecting:
            return
        
        self._is_reconnecting = True
        
        try:
            target_port = self._last_connected_port
            
            # 检查目标端口是否存在
            current_ports = [p.device for p in serial.tools.list_ports.comports()]
            if target_port not in current_ports:
                return
            
            # 配置端口
            self.config['port'] = target_port
            
            # 尝试连接
            if self._connect_internal():
                self._connection_lost = False
                # 通知重连成功
                if self.on_auto_reconnect:
                    self.on_auto_reconnect(True, target_port, True)
            
        finally:
            self._is_reconnecting = False
    
    def _connect_internal(self) -> bool:
        """内部连接方法（不设置last_connected_port）"""
        if self.is_connected:
            return True
        
        try:
            bytesize_map = {5: serial.FIVEBITS, 6: serial.SIXBITS,
                           7: serial.SEVENBITS, 8: serial.EIGHTBITS}
            stopbits_map = {1: serial.STOPBITS_ONE, 1.5: serial.STOPBITS_ONE_POINT_FIVE,
                           2: serial.STOPBITS_TWO}
            parity_map = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN,
                         'O': serial.PARITY_ODD, 'M': serial.PARITY_MARK,
                         'S': serial.PARITY_SPACE}
            
            self.serial_port = serial.Serial()
            self.serial_port.port = self.config['port']
            self.serial_port.baudrate = self.config['baudrate']
            self.serial_port.bytesize = bytesize_map.get(self.config['bytesize'], serial.EIGHTBITS)
            self.serial_port.stopbits = stopbits_map.get(self.config['stopbits'], serial.STOPBITS_ONE)
            self.serial_port.parity = parity_map.get(self.config['parity'], serial.PARITY_NONE)
            self.serial_port.timeout = self.config['timeout']
            self.serial_port.write_timeout = self.config['write_timeout']
            
            self.serial_port.rts = False
            self.serial_port.dtr = False
            
            self.serial_port.open()
            
            time.sleep(0.1)
            
            self._apply_rts_dtr_settings()
            
            self.is_connected = True
            self.stop_threads.clear()
            
            self.rx_thread = threading.Thread(target=self._rx_worker, daemon=True)
            self.tx_thread = threading.Thread(target=self._tx_worker, daemon=True)
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
        """尝试静默自动连接到指定端口
        
        用于启动时自动连接上次使用的端口
        
        Args:
            port: 要连接的端口名
            
        Returns:
            是否连接成功
        """
        # 检查端口是否存在
        current_ports = [p.device for p in serial.tools.list_ports.comports()]
        if port not in current_ports:
            return False
        
        # 配置端口
        self.configure(port=port)
        
        # 尝试连接
        success = self.connect()
        
        if success:
            # 通知自动连接成功（不是重连）
            if self.on_auto_reconnect:
                self.on_auto_reconnect(True, port, False)
        
        return success
    
    # =========================================================================
    # 原有方法
    # =========================================================================
    
    def get_available_ports(self) -> List[Dict[str, str]]:
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'port': port.device,
                'description': port.description,
                'hwid': port.hwid
            })
        return ports
    
    def get_baudrate_list(self) -> List[int]:
        return [
            38400, 57600, 115200, 128000, 230400, 256000,
            460800, 500000, 576000, 921600, 1000000, 1152000,
            1500000, 2000000
        ]
    
    def configure(self, **kwargs):
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
    
    def set_rts_dtr_control(self, rts: Optional[bool] = None, dtr: Optional[bool] = None):
        if rts is not None:
            self.config['rts'] = rts
        if dtr is not None:
            self.config['dtr'] = dtr
            
        if self.is_connected and self.serial_port:
            self._apply_rts_dtr_settings()
    
    def _apply_rts_dtr_settings(self):
        if not self.serial_port:
            return
            
        try:
            self.serial_port.rts = self.config['rts']
            self.serial_port.dtr = self.config['dtr']
        except Exception:
            self.stats['errors'] += 1
    
    def get_rts_dtr_status(self) -> Dict[str, Any]:
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
        except:
            return {'rts': None, 'dtr': None, 'connected': self.is_connected}
    
    def toggle_rts(self):
        if self.serial_port:
            try:
                self.serial_port.rts = not self.serial_port.rts
                self.config['rts'] = self.serial_port.rts
                return self.serial_port.rts
            except Exception:
                self.stats['errors'] += 1
        return None
    
    def toggle_dtr(self):
        if self.serial_port:
            try:
                self.serial_port.dtr = not self.serial_port.dtr
                self.config['dtr'] = self.serial_port.dtr
                return self.serial_port.dtr
            except Exception:
                self.stats['errors'] += 1
        return None
    
    def reset_target_device(self):
        if not self.serial_port:
            return False
            
        try:
            original_rts = self.serial_port.rts
            original_dtr = self.serial_port.dtr
            
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
        """连接到配置的串口"""
        if self.is_connected:
            return True
        
        # 重置手动断开标志
        self._manual_disconnect = False
        
        success = self._connect_internal()
        
        if success:
            # 记录成功连接的端口
            self._last_connected_port = self.config['port']
            self._connection_lost = False
            
            # 启动监控线程
            if self._auto_reconnect_enabled:
                self._start_monitor()
        
        return success
    
    def disconnect(self):
        """断开连接"""
        if not self.is_connected:
            return
        
        # 标记为手动断开
        self._manual_disconnect = True
        self._connection_lost = False
        
        self.stop_auto_send()
        
        self.stop_threads.set()
        
        if self.rx_thread and self.rx_thread.is_alive():
            self.rx_thread.join(timeout=1)
        if self.tx_thread and self.tx_thread.is_alive():
            self.tx_thread.join(timeout=1)
        
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except:
                pass
        
        self.serial_port = None
        self.is_connected = False
        
        while not self.rx_queue.empty():
            try:
                self.rx_queue.get_nowait()
            except:
                break
        while not self.tx_queue.empty():
            try:
                self.tx_queue.get_nowait()
            except:
                break
        
        if self.on_connection_changed:
            self.on_connection_changed(False)
    
    def _rx_worker(self):
        while not self.stop_threads.is_set():
            if not self.serial_port or not self.serial_port.is_open:
                time.sleep(0.01)
                continue
            
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
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
                # 串口异常可能意味着断开
                if self._auto_reconnect_enabled and not self._manual_disconnect:
                    self._connection_lost = True
                time.sleep(0.1)
            except Exception:
                self.stats['errors'] += 1
                time.sleep(0.1)
    
    def _tx_worker(self):
        while not self.stop_threads.is_set():
            try:
                data = self.tx_queue.get(timeout=0.1)
                
                if self.serial_port and self.serial_port.is_open:
                    self.serial_port.write(data)
                    self.serial_port.flush()
                    
                    self.stats['tx_bytes'] += len(data)
                    self.stats['tx_packets'] += 1
                    
            except queue.Empty:
                continue
            except serial.SerialException:
                self.stats['errors'] += 1
                # 串口异常可能意味着断开
                if self._auto_reconnect_enabled and not self._manual_disconnect:
                    self._connection_lost = True
            except Exception:
                self.stats['errors'] += 1
    
    def send_data(self, data: str, format: Optional[DataFormat] = None):
        if not self.is_connected:
            self.stats['errors'] += 1
            return False
        
        format = format or self.tx_format
        
        try:
            if format == DataFormat.HEX:
                hex_str = data.replace(" ", "").replace("\n", "").replace("\r", "")
                if len(hex_str) % 2 != 0:
                    hex_str = "0" + hex_str
                bytes_data = bytes.fromhex(hex_str)
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
    
    def get_received_data(self, format: Optional[DataFormat] = None) -> str:
        format = format or self.rx_format
        data_list = []
        
        while not self.rx_queue.empty():
            try:
                data = self.rx_queue.get_nowait()
                data_list.append(data)
            except queue.Empty:
                break
        
        if not data_list:
            return ""
        
        all_data = b''.join(data_list)
        
        if format == DataFormat.HEX:
            hex_str = ' '.join([f'{b:02X}' for b in all_data])
            return hex_str
        else:
            return all_data.decode('utf-8', errors='replace')
    
    def clear_rx_buffer(self):
        while not self.rx_queue.empty():
            try:
                self.rx_queue.get_nowait()
            except:
                break
        self.rx_buffer.clear()
    
    def pause_rx(self, paused: bool):
        self.rx_paused = paused
    
    def set_rx_format(self, format: DataFormat):
        self.rx_format = format
    
    def set_tx_format(self, format: DataFormat):
        self.tx_format = format
    
    def set_tx_newline(self, enabled: bool):
        self.tx_newline = enabled
    
    def start_auto_send(self, data: str, interval: float):
        if self.auto_send_thread and self.auto_send_thread.is_alive():
            self.stop_auto_send()
        
        self.auto_send_enabled = True
        self.auto_send_interval = interval
        self.auto_send_data = data
        
        self.auto_send_thread = threading.Thread(target=self._auto_send_worker, daemon=True)
        self.auto_send_thread.start()
    
    def stop_auto_send(self):
        self.auto_send_enabled = False
        if self.auto_send_thread and self.auto_send_thread.is_alive():
            self.auto_send_thread.join(timeout=1)
    
    def _auto_send_worker(self):
        while self.auto_send_enabled and not self.stop_threads.is_set():
            if self.is_connected and self.auto_send_data:
                self.send_data(self.auto_send_data)
            time.sleep(self.auto_send_interval)
    
    def get_statistics(self) -> Dict[str, Any]:
        stats = self.stats.copy()
        if stats['start_time']:
            duration = (datetime.now() - stats['start_time']).total_seconds()
            stats['duration'] = duration
            stats['rx_rate'] = stats['rx_bytes'] / duration if duration > 0 else 0
            stats['tx_rate'] = stats['tx_bytes'] / duration if duration > 0 else 0
        return stats
    
    def __del__(self):
        self._stop_monitor()
        self.disconnect()


def format_hex_display(data: bytes, width: int = 16) -> str:
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i+width]
        hex_part = ' '.join([f'{b:02X}' for b in chunk])
        ascii_part = ''.join([chr(b) if 32 <= b < 127 else '.' for b in chunk])
        lines.append(f'{i:08X}  {hex_part:<{width*3}}  {ascii_part}')
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
        result = 0
        for b in data:
            result ^= b
        return result
    elif method == 'crc16':
        crc = 0xFFFF
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