#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬件监控模块 - 跨平台支持 Windows/macOS/Linux
v2.1 - 增强型跨平台监控
"""

import os, sys, math, time, threading, subprocess, re, json
import psutil
from typing import Dict, List, Optional, Any, Tuple
import platform

# =============================================================================
# 平台检测
# =============================================================================
SYSTEM = platform.system().lower()
IS_WINDOWS = SYSTEM == 'windows'
IS_MACOS = SYSTEM == 'darwin'
IS_LINUX = SYSTEM == 'linux'

# =============================================================================
# 条件导入
# =============================================================================
def _try_import(name):
    try: 
        return __import__(name)
    except Exception: 
        return None

# Windows 特定
clr = None
wmi_module = None
if IS_WINDOWS:
    clr = _try_import("clr")
    wmi_module = _try_import("wmi")
    import ctypes
    from ctypes import wintypes

def is_admin():
    """检查是否有管理员权限"""
    if IS_WINDOWS:
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    else:
        return os.geteuid() == 0 if hasattr(os, 'geteuid') else False


# =============================================================================
# Windows LHM 相关类 (保持原有逻辑)
# =============================================================================

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
    """智能内存单位转换"""
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


# =============================================================================
# Windows LHM 类 (原有逻辑保持不变)
# =============================================================================

class OptimizedLHM:
    """Windows LibreHardwareMonitor 封装"""
    
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
        
        if not IS_WINDOWS or not clr:
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
            from LibreHardwareMonitor.Hardware import Computer
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
                if wmi_module:
                    w = wmi_module.WMI()
                    speeds = []
                    for m in w.Win32_PhysicalMemory():
                        if m.Speed:
                            speeds.append(int(m.Speed))
                    self._cached_mem_freq = max(speeds) if speeds else None
                else:
                    self._cached_mem_freq = None
            except:
                self._cached_mem_freq = None
        
        return {
            "used_b": mem_used,
            "total_b": mem_total,
            "percent": mem_percent,
            "freq_mhz": self._cached_mem_freq
        }


# =============================================================================
# macOS 硬件监控 (增强版)
# =============================================================================

class MacOSHardwareMonitor:
    """macOS 硬件监控实现 - 增强版"""
    
    def __init__(self):
        self._cpu_name = None
        self._gpu_info_cache = None
        self._gpu_info_time = 0
        self._is_apple_silicon = self._detect_apple_silicon()
        self._powermetrics_available = self._check_powermetrics()
        self._last_cpu_temp = None
        self._last_gpu_info = {}
    
    def _detect_apple_silicon(self) -> bool:
        """检测是否为 Apple Silicon"""
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return 'Apple' in result.stdout
        except:
            pass
        return platform.processor() == 'arm'
    
    def _check_powermetrics(self) -> bool:
        """检查 powermetrics 是否可用 (需要 sudo)"""
        return os.path.exists('/usr/bin/powermetrics')
    
    def _run_cmd(self, cmd: list, timeout: int = 5) -> Optional[str]:
        """运行命令并返回输出"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.stdout if result.returncode == 0 else None
        except:
            return None
    
    def get_cpu_info(self) -> Dict[str, Any]:
        # CPU名称
        if self._cpu_name is None:
            output = self._run_cmd(['sysctl', '-n', 'machdep.cpu.brand_string'])
            if output:
                self._cpu_name = output.strip()
            else:
                # Apple Silicon fallback
                output = self._run_cmd(['sysctl', '-n', 'hw.model'])
                self._cpu_name = output.strip() if output else "Apple CPU"
        
        # CPU使用率
        usage = psutil.cpu_percent(interval=None)
        
        # CPU频率
        freq = psutil.cpu_freq()
        clock_mhz = freq.current if freq else None
        
        # Apple Silicon: 尝试获取性能核心频率
        if self._is_apple_silicon and clock_mhz is None:
            # Apple Silicon 没有传统频率概念
            clock_mhz = None
        
        # CPU温度
        temp = self._get_cpu_temp()
        
        # CPU功耗 (Apple Silicon via powermetrics 或其他方式)
        power = None
        
        return {
            "name": self._cpu_name,
            "usage": usage,
            "temp": temp,
            "power": power,
            "clock_mhz": clock_mhz
        }
    
    def _get_cpu_temp(self) -> Optional[float]:
        """获取 CPU 温度 - 多种方法尝试"""
        # 方法1: osx-cpu-temp (第三方工具)
        output = self._run_cmd(['osx-cpu-temp'])
        if output:
            match = re.search(r'(\d+\.?\d*)', output)
            if match:
                return float(match.group(1))
        
        # 方法2: 使用 istats (如果安装了)
        output = self._run_cmd(['istats', '--no-graphs'])
        if output:
            match = re.search(r'CPU temp:\s*(\d+\.?\d*)', output)
            if match:
                return float(match.group(1))
        
        # 方法3: Apple Silicon 使用 ioreg (有限制)
        if self._is_apple_silicon:
            # Apple Silicon 温度通常需要特殊工具
            pass
        
        return self._last_cpu_temp
    
    def get_gpu_list(self) -> List[str]:
        self._update_gpu_info()
        if self._gpu_info_cache:
            return [g["name"] for g in self._gpu_info_cache]
        return ["Integrated GPU"]
    
    def _update_gpu_info(self):
        """使用 system_profiler 获取GPU信息"""
        if self._gpu_info_cache and time.time() - self._gpu_info_time < 60:
            return
        
        output = self._run_cmd(['system_profiler', 'SPDisplaysDataType', '-json'], timeout=10)
        if output:
            try:
                data = json.loads(output)
                displays = data.get('SPDisplaysDataType', [])
                
                self._gpu_info_cache = []
                for display in displays:
                    gpu_name = display.get('sppci_model', 'Unknown GPU')
                    
                    # Apple Silicon: GPU 集成在 SoC 中
                    if 'Apple' in gpu_name or self._is_apple_silicon:
                        chip_type = display.get('sppci_model', 'Apple GPU')
                        cores = display.get('sppci_cores', '')
                        if cores:
                            gpu_name = f"{chip_type} ({cores} cores)"
                    
                    vram = display.get('spdisplays_vram', '0')
                    vram_bytes = 0
                    match = re.search(r'(\d+)\s*(GB|MB)', str(vram), re.IGNORECASE)
                    if match:
                        size = int(match.group(1))
                        unit = match.group(2).upper()
                        vram_bytes = size * (1024**3 if unit == "GB" else 1024**2)
                    
                    # Apple Silicon: 共享内存
                    if self._is_apple_silicon and vram_bytes == 0:
                        mem = psutil.virtual_memory()
                        vram_bytes = mem.total  # 共享统一内存
                    
                    self._gpu_info_cache.append({
                        "name": gpu_name,
                        "mem_total_b": vram_bytes,
                        "is_integrated": self._is_apple_silicon or 'Intel' in gpu_name
                    })
                
                self._gpu_info_time = time.time()
            except:
                pass
        
        if not self._gpu_info_cache:
            self._gpu_info_cache = [{"name": "Apple GPU" if self._is_apple_silicon else "Unknown GPU", 
                                    "mem_total_b": 0, "is_integrated": True}]
    
    def get_gpu_info(self, gpu_index: int = 0) -> Dict[str, Any]:
        self._update_gpu_info()
        
        gpu = self._gpu_info_cache[gpu_index] if self._gpu_info_cache and gpu_index < len(self._gpu_info_cache) else {}
        
        # Apple Silicon: GPU 利用率 (尝试通过 Activity Monitor 或 powermetrics)
        util = None
        temp = None
        power = None
        mem_used = None
        
        return {
            "name": gpu.get("name", "Unknown GPU"),
            "util": util,
            "temp": temp,
            "clock_mhz": None,
            "mem_used_b": mem_used,
            "mem_total_b": gpu.get("mem_total_b"),
            "power": power
        }
    
    def get_memory_info(self) -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        
        # macOS 内存频率 (通过 system_profiler)
        freq = self._get_memory_freq()
        
        return {
            "used_b": mem.used,
            "total_b": mem.total,
            "percent": mem.percent,
            "freq_mhz": freq
        }
    
    def _get_memory_freq(self) -> Optional[int]:
        """获取内存频率"""
        if hasattr(self, '_cached_mem_freq'):
            return self._cached_mem_freq
        
        output = self._run_cmd(['system_profiler', 'SPMemoryDataType', '-json'], timeout=10)
        if output:
            try:
                data = json.loads(output)
                mem_items = data.get('SPMemoryDataType', [])
                for item in mem_items:
                    if 'SPMemoryDataType' in item:
                        for mem in item.get('SPMemoryDataType', []):
                            speed = mem.get('dimm_speed', '')
                            match = re.search(r'(\d+)', str(speed))
                            if match:
                                self._cached_mem_freq = int(match.group(1))
                                return self._cached_mem_freq
            except:
                pass
        
        self._cached_mem_freq = None
        return None


# =============================================================================
# Linux 硬件监控 (增强版)
# =============================================================================

class LinuxHardwareMonitor:
    """Linux 硬件监控实现 - 增强版"""
    
    def __init__(self):
        self._cpu_name = None
        self._gpu_type = None  # 'nvidia', 'amd', 'intel', or None
        self._gpu_count = 0
        self._gpu_names = []
        self._detect_gpu()
    
    def _run_cmd(self, cmd: list, timeout: int = 5) -> Optional[str]:
        """运行命令并返回输出"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.stdout if result.returncode == 0 else None
        except:
            return None
    
    def _detect_gpu(self):
        """检测GPU类型和数量"""
        # 检测 NVIDIA
        output = self._run_cmd(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'])
        if output and output.strip():
            self._gpu_type = 'nvidia'
            self._gpu_names = [name.strip() for name in output.strip().split('\n') if name.strip()]
            self._gpu_count = len(self._gpu_names)
            return
        
        # 检测 AMD (通过 rocm-smi)
        output = self._run_cmd(['rocm-smi', '--showproductname'])
        if output:
            self._gpu_type = 'amd'
            names = re.findall(r'Card series:\s*(.+)', output)
            if names:
                self._gpu_names = names
                self._gpu_count = len(names)
            return
        
        # 检测 AMD (通过 amdgpu)
        if os.path.exists('/sys/class/drm'):
            for card in os.listdir('/sys/class/drm'):
                if card.startswith('card') and not '-' in card:
                    vendor_path = f'/sys/class/drm/{card}/device/vendor'
                    if os.path.exists(vendor_path):
                        try:
                            with open(vendor_path) as f:
                                vendor = f.read().strip()
                            if vendor == '0x1002':  # AMD vendor ID
                                self._gpu_type = 'amd'
                                self._gpu_names.append(f"AMD GPU {card}")
                                self._gpu_count = len(self._gpu_names)
                        except:
                            pass
        
        # 检测 Intel 集成 GPU
        output = self._run_cmd(['lspci'])
        if output and 'VGA' in output:
            lines = output.split('\n')
            for line in lines:
                if 'VGA' in line and 'Intel' in line:
                    self._gpu_type = 'intel'
                    match = re.search(r'Intel.*\[(.*?)\]', line)
                    if match:
                        self._gpu_names.append(f"Intel {match.group(1)}")
                    else:
                        self._gpu_names.append("Intel Integrated Graphics")
                    self._gpu_count = len(self._gpu_names)
    
    def get_cpu_info(self) -> Dict[str, Any]:
        # CPU名称
        if self._cpu_name is None:
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'model name' in line:
                            self._cpu_name = line.split(':')[1].strip()
                            break
            except:
                pass
            if not self._cpu_name:
                self._cpu_name = "CPU"
        
        # CPU使用率
        usage = psutil.cpu_percent(interval=None)
        
        # CPU频率
        freq = psutil.cpu_freq()
        clock_mhz = freq.current if freq else None
        
        # CPU温度 (lm-sensors)
        temp = self._get_cpu_temp()
        
        # CPU功耗 (Intel RAPL)
        power = self._get_cpu_power()
        
        return {
            "name": self._cpu_name,
            "usage": usage,
            "temp": temp,
            "power": power,
            "clock_mhz": clock_mhz
        }
    
    def _get_cpu_temp(self) -> Optional[float]:
        """通过 lm-sensors 或 hwmon 获取CPU温度"""
        # 方法1: sensors -j (JSON输出)
        output = self._run_cmd(['sensors', '-j'])
        if output:
            try:
                data = json.loads(output)
                for chip_name, chip_data in data.items():
                    if not isinstance(chip_data, dict):
                        continue
                    # Intel: coretemp, AMD: k10temp 或 zenpower
                    if any(x in chip_name.lower() for x in ['coretemp', 'k10temp', 'zenpower']):
                        for sensor_name, sensor_data in chip_data.items():
                            if isinstance(sensor_data, dict):
                                for key, value in sensor_data.items():
                                    if 'input' in key and isinstance(value, (int, float)):
                                        return float(value)
            except:
                pass
        
        # 方法2: 直接读取 hwmon
        try:
            hwmon_path = '/sys/class/hwmon'
            if os.path.exists(hwmon_path):
                for hwmon in os.listdir(hwmon_path):
                    name_path = os.path.join(hwmon_path, hwmon, 'name')
                    if os.path.exists(name_path):
                        with open(name_path) as f:
                            name = f.read().strip()
                        if any(x in name for x in ['coretemp', 'k10temp', 'zenpower']):
                            # 尝试多个温度传感器
                            for i in range(1, 10):
                                temp_path = os.path.join(hwmon_path, hwmon, f'temp{i}_input')
                                if os.path.exists(temp_path):
                                    with open(temp_path) as f:
                                        return float(f.read().strip()) / 1000.0
        except:
            pass
        
        # 方法3: thermal_zone
        try:
            for zone in os.listdir('/sys/class/thermal'):
                if zone.startswith('thermal_zone'):
                    temp_path = f'/sys/class/thermal/{zone}/temp'
                    if os.path.exists(temp_path):
                        with open(temp_path) as f:
                            return float(f.read().strip()) / 1000.0
        except:
            pass
        
        return None
    
    def _get_cpu_power(self) -> Optional[float]:
        """获取 CPU 功耗 (通过 Intel RAPL)"""
        try:
            rapl_path = '/sys/class/powercap/intel-rapl:0/energy_uj'
            if os.path.exists(rapl_path):
                # 需要两次读取计算功耗
                with open(rapl_path) as f:
                    energy1 = int(f.read().strip())
                time.sleep(0.1)
                with open(rapl_path) as f:
                    energy2 = int(f.read().strip())
                # 转换为瓦特
                power_uw = (energy2 - energy1) / 0.1  # 微焦耳/秒 = 微瓦
                return power_uw / 1000000  # 转换为瓦特
        except:
            pass
        return None
    
    def get_gpu_list(self) -> List[str]:
        if self._gpu_names:
            return self._gpu_names
        return ["Integrated GPU"]
    
    def get_gpu_info(self, gpu_index: int = 0) -> Dict[str, Any]:
        result = {
            "name": self._gpu_names[gpu_index] if gpu_index < len(self._gpu_names) else "Unknown GPU",
            "util": None, "temp": None, "clock_mhz": None,
            "mem_used_b": None, "mem_total_b": None, "power": None
        }
        
        if self._gpu_type == 'nvidia':
            output = self._run_cmd([
                'nvidia-smi', f'--id={gpu_index}',
                '--query-gpu=name,utilization.gpu,temperature.gpu,clocks.gr,memory.used,memory.total,power.draw',
                '--format=csv,noheader,nounits'
            ])
            
            if output:
                parts = [p.strip() for p in output.strip().split(',')]
                if len(parts) >= 7:
                    try:
                        result = {
                            "name": parts[0],
                            "util": float(parts[1]) if parts[1] and parts[1] != '[N/A]' else None,
                            "temp": float(parts[2]) if parts[2] and parts[2] != '[N/A]' else None,
                            "clock_mhz": float(parts[3]) if parts[3] and parts[3] != '[N/A]' else None,
                            "mem_used_b": float(parts[4]) * 1024 * 1024 if parts[4] and parts[4] != '[N/A]' else None,
                            "mem_total_b": float(parts[5]) * 1024 * 1024 if parts[5] and parts[5] != '[N/A]' else None,
                            "power": float(parts[6]) if parts[6] and parts[6] != '[N/A]' else None
                        }
                    except:
                        pass
        
        elif self._gpu_type == 'amd':
            # AMD GPU 监控 - rocm-smi
            temp_output = self._run_cmd(['rocm-smi', '-d', str(gpu_index), '--showtemp'])
            if temp_output:
                match = re.search(r'(\d+\.?\d*)\s*c', temp_output, re.IGNORECASE)
                if match:
                    result["temp"] = float(match.group(1))
            
            usage_output = self._run_cmd(['rocm-smi', '-d', str(gpu_index), '--showuse'])
            if usage_output:
                match = re.search(r'(\d+)%', usage_output)
                if match:
                    result["util"] = float(match.group(1))
            
            # AMD: 通过 amdgpu hwmon 获取更多信息
            result.update(self._get_amd_gpu_info(gpu_index))
        
        elif self._gpu_type == 'intel':
            # Intel GPU 监控
            result.update(self._get_intel_gpu_info(gpu_index))
        
        return result
    
    def _get_amd_gpu_info(self, gpu_index: int) -> Dict[str, Any]:
        """获取 AMD GPU 信息通过 sysfs"""
        result = {}
        try:
            hwmon_path = f'/sys/class/drm/card{gpu_index}/device/hwmon'
            if os.path.exists(hwmon_path):
                hwmons = os.listdir(hwmon_path)
                if hwmons:
                    hwmon = os.path.join(hwmon_path, hwmons[0])
                    
                    # 温度
                    temp_path = os.path.join(hwmon, 'temp1_input')
                    if os.path.exists(temp_path):
                        with open(temp_path) as f:
                            result["temp"] = float(f.read().strip()) / 1000.0
                    
                    # 功耗
                    power_path = os.path.join(hwmon, 'power1_average')
                    if os.path.exists(power_path):
                        with open(power_path) as f:
                            result["power"] = float(f.read().strip()) / 1000000.0  # 微瓦转瓦
        except:
            pass
        return result
    
    def _get_intel_gpu_info(self, gpu_index: int) -> Dict[str, Any]:
        """获取 Intel GPU 信息"""
        result = {}
        # Intel GPU 可以通过 intel_gpu_top 获取使用率
        # 需要 intel-gpu-tools 包
        output = self._run_cmd(['intel_gpu_top', '-l', '-s', '100'])
        if output:
            # 解析 intel_gpu_top 输出
            pass
        return result
    
    def get_memory_info(self) -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        
        # 尝试获取内存频率
        freq = self._get_memory_freq()
        
        return {
            "used_b": mem.used,
            "total_b": mem.total,
            "percent": mem.percent,
            "freq_mhz": freq
        }
    
    def _get_memory_freq(self) -> Optional[int]:
        """获取内存频率"""
        if hasattr(self, '_cached_mem_freq'):
            return self._cached_mem_freq
        
        # 方法1: 通过 dmidecode (需要 sudo)
        output = self._run_cmd(['dmidecode', '-t', 'memory'])
        if output:
            speeds = re.findall(r'Configured.*Speed:\s*(\d+)\s*MT/s', output)
            if speeds:
                self._cached_mem_freq = max(int(s) for s in speeds)
                return self._cached_mem_freq
            
            speeds = re.findall(r'Speed:\s*(\d+)\s*MT/s', output)
            if speeds:
                self._cached_mem_freq = max(int(s) for s in speeds)
                return self._cached_mem_freq
        
        # 方法2: 通过 /sys/devices
        try:
            mem_path = '/sys/devices/system/memory'
            if os.path.exists(mem_path):
                # 某些系统可能有频率信息
                pass
        except:
            pass
        
        self._cached_mem_freq = None
        return None


# =============================================================================
# 通用磁盘和网络监控 (跨平台)
# =============================================================================

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
        
        # Windows: 使用WMI获取详细信息
        if IS_WINDOWS and wmi_module:
            try:
                w = wmi_module.WMI()
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
                return disks
            except:
                pass
        
        # macOS: 获取磁盘信息
        if IS_MACOS:
            try:
                output = subprocess.run(['diskutil', 'list', '-plist'], 
                                       capture_output=True, text=True, timeout=10)
                if output.returncode == 0:
                    # 简化处理: 使用 psutil
                    pass
            except:
                pass
        
        # 通用方法: psutil
        partitions = psutil.disk_partitions()
        seen_devices = set()
        
        for i, partition in enumerate(partitions):
            # 跳过特殊文件系统
            if partition.fstype in ('squashfs', 'tmpfs', 'devtmpfs', 'overlay'):
                continue
            if IS_WINDOWS and 'cdrom' in partition.opts:
                continue
            if IS_LINUX and partition.mountpoint.startswith('/snap'):
                continue
                
            # 去重设备
            device_base = partition.device.split('/')[-1].rstrip('0123456789')
            if device_base in seen_devices and not IS_WINDOWS:
                continue
            seen_devices.add(device_base)
            
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                
                # 获取更友好的名称
                if IS_LINUX:
                    model = self._get_linux_disk_model(partition.device) or partition.device
                elif IS_MACOS:
                    model = self._get_macos_disk_model(partition.device) or partition.device
                else:
                    model = f"Drive {partition.device}"
                
                disks.append({
                    'index': i,
                    'model': model,
                    'size': usage.total,
                    'device': partition.device,
                    'letters': [partition.mountpoint] if IS_LINUX or IS_MACOS else [partition.device.replace('\\', '')]
                })
            except:
                continue
        
        return disks
    
    def _get_linux_disk_model(self, device: str) -> Optional[str]:
        """获取 Linux 磁盘型号"""
        try:
            # 提取设备名 (例如 /dev/sda1 -> sda)
            dev_name = device.split('/')[-1].rstrip('0123456789')
            model_path = f'/sys/block/{dev_name}/device/model'
            if os.path.exists(model_path):
                with open(model_path) as f:
                    return f.read().strip()
        except:
            pass
        return None
    
    def _get_macos_disk_model(self, device: str) -> Optional[str]:
        """获取 macOS 磁盘型号"""
        try:
            result = subprocess.run(['diskutil', 'info', device], 
                                   capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Device / Media Name:' in line:
                        return line.split(':')[1].strip()
        except:
            pass
        return None
    
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
            for letter in disk.get('letters', []):
                try:
                    if IS_WINDOWS:
                        mountpoint = letter + '\\' if len(letter) <= 2 else letter
                    else:
                        mountpoint = letter
                    usage = psutil.disk_usage(mountpoint)
                    used += usage.used
                except:
                    continue
            
            read_speed = None
            write_speed = None
            
            if self.prev_io and self.prev_time and current_time > self.prev_time:
                dt = current_time - self.prev_time
                
                # 查找对应的IO设备
                device_key = None
                if IS_WINDOWS:
                    device_key = f"PhysicalDrive{disk['index']}"
                else:
                    # Linux/macOS: 从设备路径提取设备名
                    device = disk.get('device', disk.get('model', ''))
                    dev_name = device.split('/')[-1].rstrip('0123456789')
                    for key in current_io:
                        if key == dev_name or key.startswith(dev_name):
                            device_key = key
                            break
                
                if device_key and device_key in current_io and device_key in self.prev_io and dt > 0:
                    read_speed = max(0, (current_io[device_key]['read_bytes'] - 
                                       self.prev_io[device_key]['read_bytes']) / dt)
                    write_speed = max(0, (current_io[device_key]['write_bytes'] - 
                                        self.prev_io[device_key]['write_bytes']) / dt)
            
            disk_data.append({
                'index': disk['index'],
                'model': disk['model'],
                'size': disk.get('size', 0),
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


# =============================================================================
# 统一的硬件监控器
# =============================================================================

class HardwareMonitor:
    """统一的跨平台硬件监控器"""
    
    def __init__(self):
        self.disks = CachedDisks()
        self.network = CachedNetwork()
        
        self._cpu_percent_cache = None
        self._cpu_percent_cache_time = 0
        
        # 根据平台初始化不同的监控器
        if IS_WINDOWS:
            self.lhm = OptimizedLHM()
            self._platform_monitor = None
        elif IS_MACOS:
            self.lhm = None
            self._platform_monitor = MacOSHardwareMonitor()
        elif IS_LINUX:
            self.lhm = None
            self._platform_monitor = LinuxHardwareMonitor()
        else:
            self.lhm = None
            self._platform_monitor = None
        
        self._preload()
    
    def _preload(self):
        try:
            psutil.cpu_percent(interval=None)
            
            if IS_WINDOWS and self.lhm and self.lhm.ok:
                self.lhm.sensor_mapper.update_sensors_if_needed()
            
            self.disks.get_disk_data()
            self.network.get_network_data()
            
        except Exception:
            pass
    
    def is_lhm_loaded(self) -> bool:
        """检查LHM是否加载 (仅Windows)"""
        if IS_WINDOWS and self.lhm:
            return self.lhm.ok
        return False
    
    def get_platform_name(self) -> str:
        """获取当前平台名称"""
        if IS_WINDOWS:
            return f"Windows {platform.release()}"
        elif IS_MACOS:
            return f"macOS {platform.mac_ver()[0]}"
        elif IS_LINUX:
            # 尝试获取发行版名称
            try:
                with open('/etc/os-release') as f:
                    for line in f:
                        if line.startswith('PRETTY_NAME='):
                            return line.split('=')[1].strip().strip('"')
            except:
                pass
            return f"Linux {platform.release()}"
        return "Unknown"
    
    def get_cpu_name(self) -> str:
        cpu_info = self.get_cpu_data()
        return cpu_info.get("name", "CPU")
    
    def get_cpu_data(self) -> Dict[str, Any]:
        # Windows: 使用LHM
        if IS_WINDOWS and self.lhm:
            cpu_info = self.lhm.get_cpu_info()
            
            # 如果LHM没有使用率，使用psutil
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
        
        # macOS/Linux: 使用平台特定监控器
        elif self._platform_monitor:
            return self._platform_monitor.get_cpu_info()
        
        # 后备: 基本psutil
        return {
            "name": "CPU",
            "usage": psutil.cpu_percent(interval=None),
            "temp": None,
            "power": None,
            "clock_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None
        }
    
    def get_gpu_data(self, gpu_index: int = 0) -> Dict[str, Any]:
        if IS_WINDOWS and self.lhm:
            return self.lhm.get_gpu_info(gpu_index)
        elif self._platform_monitor:
            return self._platform_monitor.get_gpu_info(gpu_index)
        return {
            "name": "GPU", "util": None, "temp": None, "clock_mhz": None,
            "mem_used_b": None, "mem_total_b": None, "power": None
        }
    
    @property
    def gpu_names(self) -> List[str]:
        if IS_WINDOWS and self.lhm:
            return self.lhm.get_gpu_list()
        elif self._platform_monitor:
            return self._platform_monitor.get_gpu_list()
        return ["未检测到GPU"]
    
    def get_memory_data(self) -> Dict[str, Any]:
        if IS_WINDOWS and self.lhm:
            return self.lhm.get_memory_info()
        elif self._platform_monitor:
            return self._platform_monitor.get_memory_info()
        
        mem = psutil.virtual_memory()
        return {
            "used_b": mem.used,
            "total_b": mem.total,
            "percent": mem.percent,
            "freq_mhz": None
        }
    
    def get_disk_data(self) -> List[Dict[str, Any]]:
        return self.disks.get_disk_data()
    
    def get_network_data(self) -> Dict[str, Any]:
        return self.network.get_network_data()


# =============================================================================
# 辅助函数
# =============================================================================

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


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print(f"平台: {SYSTEM}")
    print(f"Windows: {IS_WINDOWS}, macOS: {IS_MACOS}, Linux: {IS_LINUX}")
    print()
    
    monitor = HardwareMonitor()
    print(f"平台名称: {monitor.get_platform_name()}")
    print()
    
    print("=== CPU ===")
    cpu = monitor.get_cpu_data()
    print(f"名称: {cpu['name']}")
    print(f"使用率: {pct_str(cpu['usage'])}")
    print(f"温度: {temp_str(cpu['temp'])}")
    print(f"频率: {mhz_str(cpu['clock_mhz'])}")
    print(f"功耗: {watt_str(cpu['power'])}")
    print()
    
    print("=== GPU ===")
    print(f"GPU列表: {monitor.gpu_names}")
    gpu = monitor.get_gpu_data()
    print(f"名称: {gpu['name']}")
    print(f"使用率: {pct_str(gpu['util'])}")
    print(f"温度: {temp_str(gpu['temp'])}")
    print(f"显存: {bytes2human(gpu['mem_used_b'])} / {bytes2human(gpu['mem_total_b'])}")
    print()
    
    print("=== Memory ===")
    mem = monitor.get_memory_data()
    print(f"使用: {bytes2human(mem['used_b'])} / {bytes2human(mem['total_b'])}")
    print(f"占用: {pct_str(mem['percent'])}")
    print(f"频率: {mhz_str(mem['freq_mhz'])}")
    print()
    
    print("=== Disk ===")
    for disk in monitor.get_disk_data():
        print(f"  {disk['model']}: {bytes2human(disk['used'])} / {bytes2human(disk['size'])}")
    print()
    
    print("=== Network ===")
    net = monitor.get_network_data()
    print(f"上传: {bytes2human(net['up'])}/s")
    print(f"下载: {bytes2human(net['down'])}/s")