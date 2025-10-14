#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
        self.stop_threads = threading.Event()
        
        self.on_data_received: Optional[Callable] = None
        self.on_connection_changed: Optional[Callable] = None
        
        self.config = {
            'port': '',
            'baudrate': 115200,
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
            300, 600, 1200, 2400, 4800, 9600, 14400, 19200,
            38400, 57600, 115200, 128000, 230400, 256000,
            460800, 500000, 576000, 921600, 1000000, 1152000,
            1500000, 2000000, 2500000, 3000000, 3500000, 4000000
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
    
    def disconnect(self):
        if not self.is_connected:
            return
        
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