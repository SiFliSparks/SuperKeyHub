#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬件监控模块
"""

import os, sys, math, time, threading
import psutil
import ctypes
from ctypes import wintypes
from typing import Dict, List, Optional, Any
import platform

def _try_import(name):
    try: 
        return __import__(name)
    except Exception: 
        return None

clr = _try_import("clr")

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class CachedSensorMapper:
    
    def __init__(self, cache_duration=2.0):
        self.sensor_data = {}
        self.last_update = 0
        self.cache_duration = cache_duration
        self.update_lock = threading.Lock()
        self._hardware_list = []
        
    def set_hardware_list(self, hardware_list):
        self._hardware_list = list(hardware_list)
        
    def should_update(self):
        return time.time() - self.last_update > self.cache_duration
        
    def update_sensors_if_needed(self):
        if not self.should_update():
            return False
            
        with self.update_lock:
            if not self.should_update():
                return False
                
            try:
                self._update_sensors_internal()
                return True
            except Exception:
                return False
    
    def _update_sensors_internal(self):
        new_sensor_data = {}
        
        for hw in self._hardware_list:
            try:
                hw_type = str(hw.HardwareType)
                hw_name = str(hw.Name)
                
                if hw_type not in new_sensor_data:
                    new_sensor_data[hw_type] = {}
                if hw_name not in new_sensor_data[hw_type]:
                    new_sensor_data[hw_type][hw_name] = {
                        'sensors': {},
                        'hardware': hw
                    }
                
                hw.Update()
                for sensor in hw.Sensors:
                    self._process_sensor(new_sensor_data, hw_type, hw_name, sensor)
                
                for sub_hw in hw.SubHardware:
                    try:
                        sub_hw_type = str(sub_hw.HardwareType)
                        sub_hw_name = str(sub_hw.Name)
                        
                        if sub_hw_type not in new_sensor_data:
                            new_sensor_data[sub_hw_type] = {}
                        if sub_hw_name not in new_sensor_data[sub_hw_type]:
                            new_sensor_data[sub_hw_type][sub_hw_name] = {
                                'sensors': {},
                                'hardware': sub_hw
                            }
                        
                        sub_hw.Update()
                        for sensor in sub_hw.Sensors:
                            self._process_sensor(new_sensor_data, sub_hw_type, sub_hw_name, sensor)
                    except Exception:
                        continue
                        
            except Exception:
                continue
        
        self.sensor_data = new_sensor_data
        self.last_update = time.time()
    
    def _process_sensor(self, sensor_data, hw_type, hw_name, sensor):
        try:
            sensor_type = str(sensor.SensorType)
            sensor_name = str(sensor.Name).lower()
            sensor_value = sensor.Value
            
            if sensor_value is None or (isinstance(sensor_value, float) and math.isnan(sensor_value)):
                return
            
            if sensor_type not in sensor_data[hw_type][hw_name]['sensors']:
                sensor_data[hw_type][hw_name]['sensors'][sensor_type] = {}
            
            sensor_data[hw_type][hw_name]['sensors'][sensor_type][sensor_name] = {
                'value': float(sensor_value),
                'name': str(sensor.Name),
            }
        except Exception:
            pass
    
    def get_sensor_value(self, hw_type, sensor_type, keywords, fallback_keywords=None):
        self.update_sensors_if_needed()
        
        if hw_type not in self.sensor_data:
            return None
        
        for hw_name, hw_info in self.sensor_data[hw_type].items():
            if sensor_type in hw_info['sensors']:
                for sensor_name, sensor_info in hw_info['sensors'][sensor_type].items():
                    if any(keyword in sensor_name for keyword in keywords):
                        return sensor_info['value']
        
        if fallback_keywords:
            for hw_name, hw_info in self.sensor_data[hw_type].items():
                if sensor_type in hw_info['sensors']:
                    for sensor_name, sensor_info in hw_info['sensors'][sensor_type].items():
                        if any(keyword in sensor_name for keyword in fallback_keywords):
                            return sensor_info['value']
        
        for hw_name, hw_info in self.sensor_data[hw_type].items():
            if sensor_type in hw_info['sensors']:
                sensors = hw_info['sensors'][sensor_type]
                if sensors:
                    return list(sensors.values())[0]['value']
        
        return None
    
    def get_all_sensor_values(self, hw_type, sensor_type, keywords):
        self.update_sensors_if_needed()
        
        values = []
        if hw_type not in self.sensor_data:
            return values
        
        for hw_name, hw_info in self.sensor_data[hw_type].items():
            if sensor_type in hw_info['sensors']:
                for sensor_name, sensor_info in hw_info['sensors'][sensor_type].items():
                    if any(keyword in sensor_name for keyword in keywords):
                        values.append(sensor_info['value'])
        
        return values

def convert_memory_to_bytes(value: float, data_type: str = "auto") -> Optional[float]:
    """
    智能内存单位转换
    
    LibreHardwareMonitor返回格式:
    - GPU显存: MB (如 8192 MB = 8 GB)
    - 系统内存: GB (如 16 GB)
    """
    if value is None or value < 0:
        return None
    
    if value == 0:
        return 0
    
    if data_type == "gpu_mem":
        if value < 1:
            return value * (1024 ** 3)
        elif value < 200:
            return value * (1024 ** 3)
        elif value < 200000:
            return value * (1024 ** 2)
        else:
            return value
            
    elif data_type == "system_mem":
        if value < 1:
            return value * (1024 ** 3)
        elif value < 1024:
            return value * (1024 ** 3)
        elif value < 1048576:
            return value * (1024 ** 2)
        else:
            return value
            
    else:
        if value < 1:
            return value * (1024 ** 3)
        elif value < 200:
            return value * (1024 ** 3)
        elif value < 200000:
            return value * (1024 ** 2)
        elif value < 1073741824:
            return value * 1024
        else:
            return value

def validate_memory_value(value: float, expected_range_gb: tuple = (0.1, 256)) -> bool:
    if value is None or value <= 0:
        return False
    
    value_gb = value / (1024 ** 3)
    return expected_range_gb[0] <= value_gb <= expected_range_gb[1]

class OptimizedLHM:
    
    def __init__(self):
        self.ok = False
        self.SensorType = None
        self.HardwareType = None
        self.pc = None
        self.sensor_mapper = CachedSensorMapper(cache_duration=2.0)
        self.error_details = []
        self.partial_load = False
        
        self.system_info = {
            'python_arch': platform.architecture(),
            'is_admin': is_admin(),
        }
        
        if not clr:
            return
        
        self._try_load_lhm()
    
    def _try_load_lhm(self):
        try:
            dll_paths = [
                os.path.join(os.path.dirname(__file__), "libs", "LibreHardwareMonitorLib.dll"),
                os.path.join(os.path.dirname(__file__), "LibreHardwareMonitorLib.dll"),
                os.path.join(os.getcwd(), "libs", "LibreHardwareMonitorLib.dll"),
                os.path.join(os.getcwd(), "LibreHardwareMonitorLib.dll"),
                "libs/LibreHardwareMonitorLib.dll",
                "LibreHardwareMonitorLib.dll",
            ]
            
            dll_loaded = False
            for dll_path in dll_paths:
                if os.path.exists(dll_path):
                    try:
                        clr.AddReference(dll_path)
                        dll_loaded = True
                        break
                    except Exception:
                        continue
            
            if not dll_loaded:
                try:
                    clr.AddReference("LibreHardwareMonitorLib")
                    dll_loaded = True
                except Exception:
                    return
            
            try:
                from LibreHardwareMonitor.Hardware import Computer, SensorType, HardwareType
                self.SensorType = SensorType
                self.HardwareType = HardwareType
            except Exception:
                return
            
            try:
                pc = Computer()
                pc.IsCpuEnabled = True
                pc.IsGpuEnabled = True
                pc.IsMemoryEnabled = True
                pc.IsMotherboardEnabled = True
                pc.IsStorageEnabled = True
                
                try:
                    pc.IsControllerEnabled = False 
                    pc.IsNetworkEnabled = False   
                    pc.IsPsuEnabled = False    
                    pc.IsSuperIOEnabled = True  
                except:
                    pass
                    
            except Exception:
                return
            
            try:
                pc.Open()
                self.pc = pc
                self.ok = True
                
                self.sensor_mapper.set_hardware_list(pc.Hardware)
                self.sensor_mapper.update_sensors_if_needed()
                
            except Exception as e:
                if "HidSharp" in str(e) or "Controller" in str(e):
                    if self._try_partial_initialization():
                        return
                
                self.ok = False
                
        except Exception:
            self.ok = False
    
    def _try_partial_initialization(self):
        try:
            safe_pc = Computer()
            safe_pc.IsCpuEnabled = True
            safe_pc.IsGpuEnabled = True
            safe_pc.IsMemoryEnabled = True
            safe_pc.IsMotherboardEnabled = True
            safe_pc.IsStorageEnabled = True
            
            safe_pc.IsControllerEnabled = False
            safe_pc.IsNetworkEnabled = False
            safe_pc.IsPsuEnabled = False
            safe_pc.IsSuperIOEnabled = False
            
            safe_pc.Open()
            self.pc = safe_pc
            self.ok = True
            self.partial_load = True
            
            self.sensor_mapper.set_hardware_list(safe_pc.Hardware)
            self.sensor_mapper.update_sensors_if_needed()
            
            return True
            
        except Exception:
            return False
    
    def get_cpu_info(self):
        if not self.ok:
            return {"name": "CPU", "usage": None, "temp": None, "power": None, "clock_mhz": None}
        
        cpu_name = "CPU"
        try:
            for hw in self.pc.Hardware:
                if hw.HardwareType == self.HardwareType.Cpu:
                    cpu_name = str(hw.Name)
                    break
        except:
            pass
        
        cpu_usage = self.sensor_mapper.get_sensor_value(
            'Cpu', 'Load', 
            ['cpu total', 'total'],
            ['cpu', 'load']
        )
        
        cpu_temp = self.sensor_mapper.get_sensor_value(
            'Cpu', 'Temperature',
            ['package', 'tctl', 'tdie'],
            ['cpu', 'core']
        )
        
        cpu_power = self.sensor_mapper.get_sensor_value(
            'Cpu', 'Power',
            ['package', 'cpu package'],
            ['cpu', 'total']
        )
        
        cpu_clocks = self.sensor_mapper.get_all_sensor_values(
            'Cpu', 'Clock',
            ['core', 'cpu']
        )
        
        cpu_clock = max(cpu_clocks) if cpu_clocks else None
            
        return {
            "name": cpu_name,
            "usage": cpu_usage,
            "temp": cpu_temp,
            "power": cpu_power,
            "clock_mhz": cpu_clock
        }
    
    def get_gpu_list(self):
        if not self.ok:
            return ["未检测到GPU"]
        
        gpu_list = []
        gpu_types = ['GpuNvidia', 'GpuAmd', 'GpuIntel']
        for gpu_type in gpu_types:
            if gpu_type in self.sensor_mapper.sensor_data:
                for gpu_name in self.sensor_mapper.sensor_data[gpu_type].keys():
                    gpu_list.append(gpu_name)
        
        return gpu_list if gpu_list else ["未检测到GPU"]
    
    def get_gpu_info(self, gpu_index=0):
        if not self.ok:
            return {"name": "GPU", "util": None, "temp": None, "clock_mhz": None,
                   "mem_used_b": None, "mem_total_b": None, "power": None}
        
        gpu_list = []
        gpu_types = ['GpuNvidia', 'GpuAmd', 'GpuIntel']
        
        for gpu_type in gpu_types:
            if gpu_type in self.sensor_mapper.sensor_data:
                for gpu_name, gpu_info in self.sensor_mapper.sensor_data[gpu_type].items():
                    gpu_list.append((gpu_type, gpu_name, gpu_info))
        
        if not gpu_list or gpu_index >= len(gpu_list):
            return {"name": "GPU", "util": None, "temp": None, "clock_mhz": None,
                   "mem_used_b": None, "mem_total_b": None, "power": None}
        
        gpu_type, gpu_name, gpu_info = gpu_list[gpu_index]
        
        gpu_util = self.sensor_mapper.get_sensor_value(
            gpu_type, 'Load',
            ['core', 'gpu core', '3d'],
            ['gpu', 'load']
        )
        
        gpu_temp = self.sensor_mapper.get_sensor_value(
            gpu_type, 'Temperature',
            ['core', 'gpu core'],
            ['gpu', 'temp']
        )
        
        gpu_clock = self.sensor_mapper.get_sensor_value(
            gpu_type, 'Clock',
            ['core', 'gpu core'],
            ['gpu', 'clock']
        )
        
        gpu_power = self.sensor_mapper.get_sensor_value(
            gpu_type, 'Power',
            ['gpu power', 'total'],
            ['gpu', 'power']
        )
        
        gpu_mem_used_raw = self.sensor_mapper.get_sensor_value(
            gpu_type, 'SmallData',
            ['memory used', 'gpu memory used'],
            ['used', 'memory']
        )
        
        gpu_mem_total_raw = self.sensor_mapper.get_sensor_value(
            gpu_type, 'SmallData', 
            ['memory total', 'gpu memory total'],
            ['total', 'memory']
        )
        
        gpu_mem_used = convert_memory_to_bytes(gpu_mem_used_raw, data_type="gpu_mem")
        gpu_mem_total = convert_memory_to_bytes(gpu_mem_total_raw, data_type="gpu_mem")
        
        if gpu_mem_used and not validate_memory_value(gpu_mem_used, (0.4, 128)):
            gpu_mem_used = None
            
        if gpu_mem_total and not validate_memory_value(gpu_mem_total, (0.4, 128)):
            gpu_mem_total = None
        
        return {
            "name": gpu_name,
            "util": gpu_util,
            "temp": gpu_temp,
            "clock_mhz": gpu_clock,
            "mem_used_b": gpu_mem_used,
            "mem_total_b": gpu_mem_total,
            "power": gpu_power
        }
    
    def get_memory_info(self):
        if not self.ok:
            vm = psutil.virtual_memory()
            return {
                "used_b": vm.used,
                "total_b": vm.total,
                "percent": vm.percent,
                "freq_mhz": None
            }
        
        mem_percent = self.sensor_mapper.get_sensor_value(
            'Memory', 'Load',
            ['memory'],
            ['load']
        )
        
        mem_used_raw = self.sensor_mapper.get_sensor_value(
            'Memory', 'Data',
            ['memory used'],
            ['used']
        )
        
        mem_total_raw = self.sensor_mapper.get_sensor_value(
            'Memory', 'Data',
            ['memory total'],
            ['total']
        )
        
        mem_used = convert_memory_to_bytes(mem_used_raw, data_type="system_mem")
        mem_total = convert_memory_to_bytes(mem_total_raw, data_type="system_mem")
        
        vm = psutil.virtual_memory()
        
        if mem_used is None or mem_total is None:
            mem_percent = vm.percent
            mem_used = vm.used
            mem_total = vm.total
        elif not validate_memory_value(mem_used, (0.5, 1024)) or \
             not validate_memory_value(mem_total, (1, 1024)):
            mem_percent = vm.percent
            mem_used = vm.used
            mem_total = vm.total
        elif mem_used > mem_total:
            mem_percent = vm.percent
            mem_used = vm.used
            mem_total = vm.total
        elif abs(mem_used - mem_total) < (mem_total * 0.01):
            mem_percent = vm.percent
            mem_used = vm.used
            mem_total = vm.total
        else:
            if mem_percent is None and mem_total > 0:
                mem_percent = (mem_used / mem_total) * 100
        
        if not hasattr(self, '_cached_mem_freq'):
            try:
                import wmi
                w = wmi.WMI()
                speeds = []
                for m in w.Win32_PhysicalMemory():
                    if m.Speed:
                        speeds.append(int(m.Speed))
                self._cached_mem_freq = max(speeds) if speeds else None
            except:
                self._cached_mem_freq = None
        
        return {
            "used_b": mem_used,
            "total_b": mem_total,
            "percent": mem_percent,
            "freq_mhz": self._cached_mem_freq
        }

class CachedDisks:
    def __init__(self):
        self.prev_io = {}
        self.prev_time = None
        self.disk_info_cache = None
        self.disk_info_cache_time = 0
        self.disk_info_cache_duration = 60
        
    def _get_disk_info(self):
        current_time = time.time()
        if (self.disk_info_cache is None or 
            current_time - self.disk_info_cache_time > self.disk_info_cache_duration):
            
            self.disk_info_cache = self._build_disk_info()
            self.disk_info_cache_time = current_time
            
        return self.disk_info_cache
    
    def _build_disk_info(self):
        disks = []
        try:
            import wmi
            w = wmi.WMI()
            for d in w.Win32_DiskDrive():
                disk_info = {
                    'index': int(d.Index) if d.Index else 0,
                    'model': (d.Model or f"PhysicalDrive{d.Index}").strip(),
                    'size': int(d.Size) if d.Size else 0,
                    'device_id': f"PhysicalDrive{d.Index}"
                }
                
                letters = []
                try:
                    for p in d.associators("Win32_DiskDriveToDiskPartition"):
                        for ld in p.associators("Win32_LogicalDiskToPartition"):
                            if ld.DeviceID:
                                letters.append(ld.DeviceID)
                except:
                    pass
                
                disk_info['letters'] = sorted(set(letters))
                disks.append(disk_info)
        except:
            partitions = psutil.disk_partitions()
            for i, partition in enumerate(partitions):
                if 'cdrom' not in partition.opts:
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        disks.append({
                            'index': i,
                            'model': f"Drive {partition.device}",
                            'size': usage.total,
                            'letters': [partition.device.replace('\\', '')]
                        })
                    except:
                        continue
        
        return disks
    
    def get_disk_data(self):
        current_time = time.time()
        current_io = {}
        
        try:
            io_counters = psutil.disk_io_counters(perdisk=True)
            for device, io in io_counters.items():
                current_io[device] = {
                    'read_bytes': io.read_bytes,
                    'write_bytes': io.write_bytes
                }
        except:
            pass
        
        disks = self._get_disk_info()
        disk_data = []
        
        for disk in disks:
            used = 0
            for letter in disk['letters']:
                try:
                    usage = psutil.disk_usage(letter + '\\' if len(letter) == 1 else letter)
                    used += usage.used
                except:
                    continue
            
            read_speed = None
            write_speed = None
            
            if self.prev_io and self.prev_time and current_time > self.prev_time:
                dt = current_time - self.prev_time
                device_key = f"PhysicalDrive{disk['index']}"
                
                if (device_key in current_io and device_key in self.prev_io and dt > 0):
                    read_speed = max(0, (current_io[device_key]['read_bytes'] - 
                                       self.prev_io[device_key]['read_bytes']) / dt)
                    write_speed = max(0, (current_io[device_key]['write_bytes'] - 
                                        self.prev_io[device_key]['write_bytes']) / dt)
            
            disk_data.append({
                'index': disk['index'],
                'model': disk['model'],
                'size': disk['size'],
                'used': used,
                'rps': read_speed,
                'wps': write_speed
            })
        
        self.prev_io = current_io
        self.prev_time = current_time
        
        return disk_data

class CachedNetwork:
    def __init__(self):
        self.prev_stats = None
        self.prev_time = None
    
    def get_network_data(self):
        current_time = time.time()
        
        try:
            current_stats = psutil.net_io_counters(pernic=False)
        except:
            return {"up": None, "down": None}
        
        up_speed = None
        down_speed = None
        
        if self.prev_stats and self.prev_time and current_time > self.prev_time:
            dt = current_time - self.prev_time
            if dt > 0:
                up_speed = max(0, (current_stats.bytes_sent - self.prev_stats.bytes_sent) / dt)
                down_speed = max(0, (current_stats.bytes_recv - self.prev_stats.bytes_recv) / dt)
        
        self.prev_stats = current_stats
        self.prev_time = current_time
        
        return {"up": up_speed, "down": down_speed}

class HardwareMonitor:
    
    def __init__(self):
        self.lhm = OptimizedLHM()
        self.disks = CachedDisks()
        self.network = CachedNetwork()
        
        self._cpu_percent_cache = None
        self._cpu_percent_cache_time = 0
        
        self._preload()
    
    def _preload(self):
        try:
            psutil.cpu_percent(interval=None)
            
            if self.lhm.ok:
                self.lhm.sensor_mapper.update_sensors_if_needed()
            
            self.disks.get_disk_data()
            self.network.get_network_data()
            
        except Exception:
            pass
    
    def is_lhm_loaded(self):
        return self.lhm.ok
    
    def get_cpu_name(self):
        cpu_info = self.lhm.get_cpu_info()
        return cpu_info.get("name", "CPU")
    
    def get_cpu_data(self):
        cpu_info = self.lhm.get_cpu_info()
        
        if cpu_info["usage"] is None:
            current_time = time.time()
            if (self._cpu_percent_cache is None or 
                current_time - self._cpu_percent_cache_time > 1.0):
                try:
                    self._cpu_percent_cache = psutil.cpu_percent(interval=None)
                    self._cpu_percent_cache_time = current_time
                except:
                    pass
            
            cpu_info["usage"] = self._cpu_percent_cache
        
        return cpu_info
    
    def get_gpu_data(self, gpu_index=0):
        return self.lhm.get_gpu_info(gpu_index)
    
    @property
    def gpu_names(self):
        return self.lhm.get_gpu_list()
    
    def get_memory_data(self):
        return self.lhm.get_memory_info()
    
    def get_disk_data(self):
        return self.disks.get_disk_data()
    
    def get_network_data(self):
        return self.network.get_network_data()

def bytes2human(n):
    if n is None: return "—"
    n = float(n); units = ("B","KB","MB","GB","TB","PB"); i = 0
    while n >= 1024 and i < len(units) - 1: n /= 1024; i += 1
    return f"{n:.1f} {units[i]}" if i else f"{int(n)} {units[i]}"

def pct_str(v):   
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.0f}%"

def mhz_str(v):  
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.0f} MHz"

def temp_str(v): 
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.0f} °C"

def watt_str(v): 
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.0f} W"