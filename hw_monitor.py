#!/usr/bin/env python3
"""
硬件监控模块 - 跨平台支持 Windows/macOS/Linux
v2.2 - Apple Silicon IOKit/IOReport 增强版

对于 Apple Silicon Mac，推荐安装 macmon 以获得最佳体验:
  brew install macmon
"""

import ctypes
from ctypes import POINTER, byref, c_char_p, c_double, c_int64, c_uint32, c_uint64, c_void_p
import json
import math
import os
import platform
import re
import struct
import subprocess
import threading
import time
from types import ModuleType
from typing import Any, Union

import psutil

# =============================================================================
# 平台检测
# =============================================================================
SYSTEM: str = platform.system().lower()
IS_WINDOWS: bool = SYSTEM == 'windows'
IS_MACOS: bool = SYSTEM == 'darwin'
IS_LINUX: bool = SYSTEM == 'linux'


# =============================================================================
# 条件导入
# =============================================================================
def _try_import(name: str) -> ModuleType | None:
    try:
        return __import__(name)
    except Exception:
        return None


# Windows 特定
clr: ModuleType | None = None
wmi_module: ModuleType | None = None
if IS_WINDOWS:
    clr = _try_import("clr")
    wmi_module = _try_import("wmi")


def is_admin() -> bool:
    """检查是否有管理员权限"""
    if IS_WINDOWS:
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    else:
        return os.geteuid() == 0 if hasattr(os, 'geteuid') else False


# =============================================================================
# Windows LHM 相关类 (保持原有逻辑)
# =============================================================================

class CachedSensorMapper:

    def __init__(self, cache_duration: float = 2.0) -> None:
        self.sensor_data: dict[str, dict[str, Any]] = {}
        self.last_update: float = 0
        self.cache_duration: float = cache_duration
        self.update_lock: threading.Lock = threading.Lock()
        self._hardware_list: list[Any] = []

    def set_hardware_list(self, hardware_list: Any) -> None:
        self._hardware_list = list(hardware_list)

    def should_update(self) -> bool:
        return time.time() - self.last_update > self.cache_duration

    def update_sensors_if_needed(self) -> bool:
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

    def _update_sensors_internal(self) -> None:
        new_sensor_data: dict[str, dict[str, Any]] = {}

        for hw in self._hardware_list:
            try:
                hw_type = str(hw.HardwareType)
                hw_name = str(hw.Name)

                if hw_type not in new_sensor_data:
                    new_sensor_data[hw_type] = {}
                if hw_name not in new_sensor_data[hw_type]:
                    new_sensor_data[hw_type][hw_name] = {}

                hw.Update()

                for sensor in hw.Sensors:
                    s_type = str(sensor.SensorType)
                    s_name = str(sensor.Name)
                    s_val = sensor.Value

                    if s_type not in new_sensor_data[hw_type][hw_name]:
                        new_sensor_data[hw_type][hw_name][s_type] = {}

                    new_sensor_data[hw_type][hw_name][s_type][s_name] = (
                        float(s_val) if s_val is not None else None)

                for sub in hw.SubHardware:
                    sub.Update()
                    sub_name = str(sub.Name)
                    if sub_name not in new_sensor_data[hw_type]:
                        new_sensor_data[hw_type][sub_name] = {}

                    for sensor in sub.Sensors:
                        s_type = str(sensor.SensorType)
                        s_name = str(sensor.Name)
                        s_val = sensor.Value

                        if s_type not in new_sensor_data[hw_type][sub_name]:
                            new_sensor_data[hw_type][sub_name][s_type] = {}

                        new_sensor_data[hw_type][sub_name][s_type][s_name] = (
                            float(s_val) if s_val is not None else None)
            except Exception:
                continue

        self.sensor_data = new_sensor_data
        self.last_update = time.time()

    def get_sensor(self, hw_type: str, hw_name: str | None,
                   s_type: str, s_name: str | None = None) -> float | None:
        self.update_sensors_if_needed()

        type_data = self.sensor_data.get(hw_type, {})
        if not type_data:
            return None

        if hw_name:
            hw_data = type_data.get(hw_name, {})
            sensor_type_data = hw_data.get(s_type, {})
            if s_name:
                return sensor_type_data.get(s_name)
            return next(iter(sensor_type_data.values()), None) if sensor_type_data else None

        for hw_data in type_data.values():
            sensor_type_data = hw_data.get(s_type, {})
            if s_name:
                val = sensor_type_data.get(s_name)
                if val is not None:
                    return val
            elif sensor_type_data:
                return next(iter(sensor_type_data.values()), None)
        return None

    def get_all_sensors_of_type(self, hw_type: str,
                                s_type: str) -> list[tuple[str, str, float]]:
        self.update_sensors_if_needed()
        results: list[tuple[str, str, float]] = []

        type_data = self.sensor_data.get(hw_type, {})
        for hw_name, hw_data in type_data.items():
            sensor_type_data = hw_data.get(s_type, {})
            for s_name, val in sensor_type_data.items():
                if val is not None:
                    results.append((hw_name, s_name, val))
        return results


class OptimizedLHM:
    """
    Optimized LibreHardwareMonitor wrapper for Windows
    """
    _instance: 'OptimizedLHM | None' = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> 'OptimizedLHM':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._computer: Any = None
        self._sensor_mapper: CachedSensorMapper = CachedSensorMapper()
        self._available: bool = False
        self._cpu_names: list[str] = []
        self._gpu_names: list[str] = []
        self._init_lock: threading.Lock = threading.Lock()

        self._init_lhm()
        self._initialized = True

    def _init_lhm(self) -> None:
        if not IS_WINDOWS or clr is None:
            return

        try:
            dll_path = self._find_lhm_dll()
            if not dll_path:
                return

            clr.AddReference(dll_path)
            from LibreHardwareMonitor.Hardware import Computer

            self._computer = Computer()
            self._computer.IsCpuEnabled = True
            self._computer.IsGpuEnabled = True
            self._computer.IsMemoryEnabled = True
            self._computer.IsMotherboardEnabled = True
            self._computer.IsStorageEnabled = True
            self._computer.Open()

            hw_list = list(self._computer.Hardware)
            self._sensor_mapper.set_hardware_list(hw_list)

            for hw in hw_list:
                hw_type = str(hw.HardwareType)
                if 'Cpu' in hw_type:
                    self._cpu_names.append(str(hw.Name))
                elif 'Gpu' in hw_type:
                    self._gpu_names.append(str(hw.Name))

            self._available = True
        except Exception:
            self._available = False

    def _find_lhm_dll(self) -> str | None:
        import sys
        
        # 获取基础路径（兼容打包和开发环境）
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后
            base_path = sys._MEIPASS
        else:
            # 开发环境
            base_path = os.path.dirname(__file__)
        
        search_paths = [
            # libs 子目录（推荐位置）
            os.path.join(base_path, 'libs', 'LibreHardwareMonitorLib.dll'),
            # 同级目录
            os.path.join(base_path, 'LibreHardwareMonitorLib.dll'),
            # 开发环境：项目根目录的 libs
            os.path.join(os.path.dirname(__file__), 'libs', 'LibreHardwareMonitorLib.dll'),
            # 当前工作目录
            os.path.join(os.getcwd(), 'LibreHardwareMonitorLib.dll'),
            os.path.join(os.getcwd(), 'libs', 'LibreHardwareMonitorLib.dll'),
            # 系统安装位置
            r'C:\Program Files\LibreHardwareMonitor\LibreHardwareMonitorLib.dll',
            r'C:\Program Files (x86)\LibreHardwareMonitor\LibreHardwareMonitorLib.dll',
        ]
        
        for p in search_paths:
            if os.path.exists(p):
                return p
        return None

    @property
    def available(self) -> bool:
        return self._available

    def get_cpu_temp(self) -> float | None:
        if not self._available:
            return None
        return self._sensor_mapper.get_sensor('Cpu', None, 'Temperature')

    def get_cpu_power(self) -> float | None:
        if not self._available:
            return None
        return self._sensor_mapper.get_sensor('Cpu', None, 'Power', 'CPU Package')

    def get_cpu_clock(self) -> float | None:
        if not self._available:
            return None
        clocks = self._sensor_mapper.get_all_sensors_of_type('Cpu', 'Clock')
        core_clocks = [c[2] for c in clocks if 'Core' in c[1]]
        return sum(core_clocks) / len(core_clocks) if core_clocks else None

    def get_cpu_load(self) -> float | None:
        if not self._available:
            return None
        return self._sensor_mapper.get_sensor(
            'Cpu', None, 'Load', 'CPU Total')

    def get_gpu_temp(self, idx: int = 0) -> float | None:
        if not self._available or idx >= len(self._gpu_names):
            return None
        return self._sensor_mapper.get_sensor(
            'GpuNvidia', self._gpu_names[idx], 'Temperature') or \
            self._sensor_mapper.get_sensor(
                'GpuAmd', self._gpu_names[idx], 'Temperature') or \
            self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'Temperature')

    def get_gpu_power(self, idx: int = 0) -> float | None:
        if not self._available or idx >= len(self._gpu_names):
            return None
        return self._sensor_mapper.get_sensor(
            'GpuNvidia', self._gpu_names[idx], 'Power') or \
            self._sensor_mapper.get_sensor(
                'GpuAmd', self._gpu_names[idx], 'Power') or \
            self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'Power')

    def get_gpu_clock(self, idx: int = 0) -> float | None:
        if not self._available or idx >= len(self._gpu_names):
            return None
        return self._sensor_mapper.get_sensor(
            'GpuNvidia', self._gpu_names[idx], 'Clock', 'GPU Core') or \
            self._sensor_mapper.get_sensor(
                'GpuAmd', self._gpu_names[idx], 'Clock', 'GPU Core') or \
            self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'Clock', 'GPU Core') or \
            self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'Clock')

    def get_gpu_load(self, idx: int = 0) -> float | None:
        if not self._available or idx >= len(self._gpu_names):
            return None
        return self._sensor_mapper.get_sensor(
            'GpuNvidia', self._gpu_names[idx], 'Load', 'GPU Core') or \
            self._sensor_mapper.get_sensor(
                'GpuAmd', self._gpu_names[idx], 'Load', 'GPU Core') or \
            self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'Load', 'GPU Core') or \
            self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'Load', 'D3D 3D') or \
            self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'Load')

    def get_gpu_mem_used(self, idx: int = 0) -> int | None:
        if not self._available or idx >= len(self._gpu_names):
            return None
        # 尝试从不同GPU类型获取显存使用量
        val = self._sensor_mapper.get_sensor(
            'GpuNvidia', self._gpu_names[idx], 'SmallData', 'GPU Memory Used')
        if val is None:
            val = self._sensor_mapper.get_sensor(
                'GpuAmd', self._gpu_names[idx], 'SmallData', 'GPU Memory Used')
        if val is None:
            val = self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'SmallData', 'GPU Memory Used')
        if val is None:
            # Intel核显可能使用D3D共享内存
            val = self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'SmallData', 'D3D Shared Memory Used')
        if val is None:
            val = self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'SmallData')
        return int(val * 1024 * 1024) if val else None

    def get_gpu_mem_total(self, idx: int = 0) -> int | None:
        if not self._available or idx >= len(self._gpu_names):
            return None
        # 尝试从不同GPU类型获取显存总量
        val = self._sensor_mapper.get_sensor(
            'GpuNvidia', self._gpu_names[idx], 'SmallData', 'GPU Memory Total')
        if val is None:
            val = self._sensor_mapper.get_sensor(
                'GpuAmd', self._gpu_names[idx], 'SmallData', 'GPU Memory Total')
        if val is None:
            val = self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'SmallData', 'GPU Memory Total')
        if val is None:
            # Intel核显可能使用共享内存总量
            val = self._sensor_mapper.get_sensor(
                'GpuIntel', self._gpu_names[idx], 'SmallData', 'D3D Shared Memory Total')
        return int(val * 1024 * 1024) if val else None

    def get_memory_load(self) -> float | None:
        if not self._available:
            return None
        return self._sensor_mapper.get_sensor('Memory', None, 'Load')

    def get_memory_clock(self) -> float | None:
        """获取内存频率 (MHz)"""
        # 首先尝试从 LHM 获取
        if self._available:
            freq = self._sensor_mapper.get_sensor('Memory', None, 'Clock')
            if freq is not None:
                return freq
        
        # 后备：使用 WMI 获取
        return self._get_memory_clock_wmi()

    def _get_memory_clock_wmi(self) -> float | None:
        """通过 WMI 获取内存频率"""
        if wmi_module is None:
            return None
        try:
            w = wmi_module.WMI()
            speeds: list[int] = []
            for mem in w.Win32_PhysicalMemory():
                if mem.Speed:
                    speeds.append(int(mem.Speed))
            if speeds:
                return float(max(speeds))  # 返回最高频率 (MT/s)
        except Exception:
            pass
        return None

    def get_gpu_names(self) -> list[str]:
        return self._gpu_names.copy()

    def get_cpu_names(self) -> list[str]:
        return self._cpu_names.copy()

    def get_cpu_info(self) -> dict[str, Any]:
        """获取CPU信息"""
        name = self._cpu_names[0] if self._cpu_names else "Unknown CPU"
        return {
            "name": name,
            "usage": self.get_cpu_load(),
            "temp": self.get_cpu_temp(),
            "power": self.get_cpu_power(),
            "clock_mhz": self.get_cpu_clock()
        }

    def get_gpu_info(self, idx: int = 0) -> dict[str, Any]:
        """获取GPU信息"""
        name = self._gpu_names[idx] if idx < len(self._gpu_names) else "Unknown GPU"
        return {
            "name": name,
            "util": self.get_gpu_load(idx),
            "temp": self.get_gpu_temp(idx),
            "clock_mhz": self.get_gpu_clock(idx),
            "mem_used_b": self.get_gpu_mem_used(idx),
            "mem_total_b": self.get_gpu_mem_total(idx),
            "power": self.get_gpu_power(idx)
        }

    def get_gpu_list(self) -> list[str]:
        """获取GPU列表"""
        return self._gpu_names.copy()

    def get_memory_info(self) -> dict[str, Any]:
        """获取内存信息"""
        mem = psutil.virtual_memory()
        freq_mhz = self.get_memory_clock() if self._available else None
        return {
            "used_b": mem.used,
            "total_b": mem.total,
            "percent": mem.percent,
            "freq_mhz": freq_mhz
        }


# =============================================================================
# macOS Apple Silicon 监控 (使用 macmon CLI 后台采样)
# =============================================================================

class AppleSiliconMonitor:
    """Apple Silicon 性能监控器
    
    使用后台线程运行 macmon 持续采样，避免阻塞 UI。
    """

    def __init__(self) -> None:
        self._macmon_available: bool = self._check_macmon()
        self._last_metrics: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._running: bool = False
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        
        # 如果 macmon 可用，启动后台采样线程
        if self._macmon_available:
            self._start_background_sampling()
        else:
            self._init_ioreport()

    def _check_macmon(self) -> bool:
        """检查 macmon 是否可用"""
        # 常见的 macmon 安装路径
        macmon_paths = [
            '/opt/homebrew/bin/macmon',  # Apple Silicon Homebrew
            '/usr/local/bin/macmon',      # Intel Homebrew
            'macmon',                      # PATH 中（开发环境）
        ]
        
        for path in macmon_paths:
            try:
                result = subprocess.run(
                    [path, '--version'],
                    capture_output=True, timeout=5)
                if result.returncode == 0:
                    self._macmon_path = path  # 保存找到的路径
                    return True
            except Exception:
                continue
        return False

    def _start_background_sampling(self) -> None:
        """启动后台采样线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sampling_loop, daemon=True)
        self._thread.start()

    def _sampling_loop(self) -> None:
        """后台采样循环"""
        macmon_cmd = getattr(self, '_macmon_path', 'macmon')
        while self._running:
            try:
                self._process = subprocess.Popen(
                    [macmon_cmd, '-i', '1000', 'pipe'],  # 使用完整路径
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1
                )
                
                # 持续读取输出
                for line in iter(self._process.stdout.readline, ''):
                    if not self._running:
                        break
                    line = line.strip()
                    if line:
                        try:
                            metrics = json.loads(line)
                            with self._lock:
                                self._last_metrics = metrics
                        except json.JSONDecodeError:
                            pass
                
                self._process.stdout.close()
                self._process.wait()
                
            except Exception:
                pass
            
            # 如果进程意外退出，等待一会再重启
            if self._running:
                time.sleep(1)

    def stop(self) -> None:
        """停止后台采样"""
        self._running = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        if self._thread:
            self._thread.join(timeout=2)

    def _init_ioreport(self) -> None:
        """初始化 IOReport API (备用方案)"""
        self._ioreport_available = False
        try:
            self._cf = ctypes.CDLL(
                '/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
            self._iokit = ctypes.CDLL(
                '/System/Library/Frameworks/IOKit.framework/IOKit')
            
            self._iokit.IOHIDEventSystemClientCreate.argtypes = [c_void_p]
            self._iokit.IOHIDEventSystemClientCreate.restype = c_void_p
            
            self._iokit.IOHIDEventSystemClientCopyServices.argtypes = [c_void_p]
            self._iokit.IOHIDEventSystemClientCopyServices.restype = c_void_p
            
            self._iokit.IOHIDServiceClientCopyProperty.argtypes = [c_void_p, c_void_p]
            self._iokit.IOHIDServiceClientCopyProperty.restype = c_void_p
            
            self._iokit.IOHIDServiceClientCopyEvent.argtypes = [c_void_p, c_int64, c_int64, c_int64]
            self._iokit.IOHIDServiceClientCopyEvent.restype = c_void_p
            
            self._iokit.IOHIDEventGetFloatValue.argtypes = [c_void_p, c_uint32]
            self._iokit.IOHIDEventGetFloatValue.restype = c_double
            
            self._cf.CFArrayGetCount.argtypes = [c_void_p]
            self._cf.CFArrayGetCount.restype = c_int64
            
            self._cf.CFArrayGetValueAtIndex.argtypes = [c_void_p, c_int64]
            self._cf.CFArrayGetValueAtIndex.restype = c_void_p
            
            self._cf.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint32]
            self._cf.CFStringCreateWithCString.restype = c_void_p
            
            self._cf.CFStringGetCString.argtypes = [c_void_p, c_char_p, c_int64, c_uint32]
            self._cf.CFStringGetCString.restype = ctypes.c_bool
            
            self._cf.CFRelease.argtypes = [c_void_p]
            self._cf.CFRelease.restype = None
            
            self._kCFStringEncodingUTF8 = 0x08000100
            self._kIOHIDEventTypeTemperature = 15
            
            self._ioreport_available = True
        except Exception:
            self._ioreport_available = False

    def _get_iohid_temperatures(self) -> dict[str, float]:
        """通过 IOHID API 获取温度传感器数据"""
        temps: dict[str, float] = {}
        if not self._ioreport_available:
            return temps
            
        try:
            system = self._iokit.IOHIDEventSystemClientCreate(None)
            if not system:
                return temps
                
            services = self._iokit.IOHIDEventSystemClientCopyServices(system)
            if not services:
                self._cf.CFRelease(system)
                return temps
                
            count = self._cf.CFArrayGetCount(services)
            product_key = self._cf.CFStringCreateWithCString(
                None, b"Product", self._kCFStringEncodingUTF8)
            
            for i in range(count):
                sc = self._cf.CFArrayGetValueAtIndex(services, i)
                if not sc:
                    continue
                    
                name_cf = self._iokit.IOHIDServiceClientCopyProperty(sc, product_key)
                if not name_cf:
                    continue
                    
                name_buf = ctypes.create_string_buffer(256)
                if self._cf.CFStringGetCString(name_cf, name_buf, 256, self._kCFStringEncodingUTF8):
                    name = name_buf.value.decode('utf-8')
                else:
                    name = ""
                self._cf.CFRelease(name_cf)
                
                if not name:
                    continue
                    
                event = self._iokit.IOHIDServiceClientCopyEvent(
                    sc, self._kIOHIDEventTypeTemperature, 0, 0)
                if event:
                    field = self._kIOHIDEventTypeTemperature << 16
                    temp = self._iokit.IOHIDEventGetFloatValue(event, field)
                    if 0 < temp < 150:
                        temps[name] = temp
                    self._cf.CFRelease(event)
                    
            self._cf.CFRelease(product_key)
            self._cf.CFRelease(services)
            self._cf.CFRelease(system)
            
        except Exception:
            pass
            
        return temps

    def _get_metrics(self) -> dict[str, Any]:
        """获取当前缓存的指标数据"""
        with self._lock:
            return self._last_metrics.copy()

    @property
    def cpu_power(self) -> float | None:
        """CPU 功耗 (瓦特)"""
        return self._get_metrics().get('cpu_power')

    @property
    def gpu_power(self) -> float | None:
        """GPU 功耗 (瓦特)"""
        return self._get_metrics().get('gpu_power')

    @property
    def cpu_freq_mhz(self) -> float | None:
        """CPU 频率 (MHz) - P-cluster"""
        metrics = self._get_metrics()
        pcpu = metrics.get('pcpu_usage')
        if pcpu and isinstance(pcpu, list) and len(pcpu) >= 1:
            return pcpu[0]
        ecpu = metrics.get('ecpu_usage')
        if ecpu and isinstance(ecpu, list) and len(ecpu) >= 1:
            return ecpu[0]
        return None

    @property
    def gpu_freq_mhz(self) -> float | None:
        """GPU 频率 (MHz)"""
        metrics = self._get_metrics()
        gpu = metrics.get('gpu_usage')
        if gpu and isinstance(gpu, list) and len(gpu) >= 1:
            return gpu[0]
        return None

    @property
    def cpu_usage(self) -> float | None:
        """CPU 使用率 (%) - 基于 residency"""
        metrics = self._get_metrics()
        pcpu = metrics.get('pcpu_usage')
        ecpu = metrics.get('ecpu_usage')
        
        usages = []
        if pcpu and isinstance(pcpu, list) and len(pcpu) >= 2:
            usages.append(pcpu[1] * 100)
        if ecpu and isinstance(ecpu, list) and len(ecpu) >= 2:
            usages.append(ecpu[1] * 100)
            
        if usages:
            return max(usages)
        return None

    @property
    def gpu_usage(self) -> float | None:
        """GPU 使用率 (%)"""
        metrics = self._get_metrics()
        gpu = metrics.get('gpu_usage')
        if gpu and isinstance(gpu, list) and len(gpu) >= 2:
            return gpu[1] * 100
        return None

    def get_cpu_temperature(self) -> float | None:
        """获取 CPU 平均温度"""
        metrics = self._get_metrics()
        temp_data = metrics.get('temp', {})
        if isinstance(temp_data, dict):
            return temp_data.get('cpu_temp_avg')
        
        # 备用: 从 IOHID 温度数据
        if not self._macmon_available and self._ioreport_available:
            temps = self._get_iohid_temperatures()
            cpu_temps = []
            for name, temp in temps.items():
                name_lower = name.lower()
                if any(k in name_lower for k in ['cpu', 'soc', 'die', 'pmu']):
                    if 'gpu' not in name_lower:
                        cpu_temps.append(temp)
            if cpu_temps:
                return sum(cpu_temps) / len(cpu_temps)
        return None

    def get_gpu_temperature(self) -> float | None:
        """获取 GPU 平均温度"""
        metrics = self._get_metrics()
        temp_data = metrics.get('temp', {})
        if isinstance(temp_data, dict):
            return temp_data.get('gpu_temp_avg')
        
        # 备用: 从 IOHID 温度数据
        if not self._macmon_available and self._ioreport_available:
            temps = self._get_iohid_temperatures()
            gpu_temps = []
            for name, temp in temps.items():
                name_lower = name.lower()
                if 'gpu' in name_lower:
                    gpu_temps.append(temp)
            if gpu_temps:
                return sum(gpu_temps) / len(gpu_temps)
        return None

    def is_available(self) -> bool:
        """检查是否可用"""
        return self._macmon_available or getattr(self, '_ioreport_available', False)


# =============================================================================
# macOS 硬件监控
# =============================================================================

class MacOSHardwareMonitor:
    """macOS 硬件监控实现 - 支持 Apple Silicon"""

    def __init__(self) -> None:
        self._cpu_name: str | None = None
        self._gpu_info_cache: list[dict[str, Any]] | None = None
        self._gpu_info_time: float = 0
        self._is_apple_silicon: bool = self._detect_apple_silicon()
        self._last_cpu_temp: float | None = None
        self._last_gpu_temp: float | None = None

        # Apple Silicon 专用监控
        self._apple_monitor: AppleSiliconMonitor | None = None
        if self._is_apple_silicon:
            try:
                self._apple_monitor = AppleSiliconMonitor()
                if not self._apple_monitor.is_available():
                    self._apple_monitor = None
            except Exception:
                self._apple_monitor = None

    def _detect_apple_silicon(self) -> bool:
        """检测是否为 Apple Silicon"""
        try:
            result = subprocess.run(
                ['sysctl', '-n', 'machdep.cpu.brand_string'],
                capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return 'Apple' in result.stdout
        except Exception:
            pass
        return platform.processor() == 'arm'

    def _run_cmd(self, cmd: list[str], timeout: int = 5) -> str | None:
        """运行命令并返回输出"""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout)
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None

    def get_cpu_info(self) -> dict[str, Any]:
        """获取 CPU 信息"""
        if self._cpu_name is None:
            output = self._run_cmd(['sysctl', '-n', 'machdep.cpu.brand_string'])
            if output:
                self._cpu_name = output.strip()
            else:
                output = self._run_cmd(['sysctl', '-n', 'hw.model'])
                self._cpu_name = output.strip() if output else "Apple CPU"

        usage: float | None = psutil.cpu_percent(interval=None)
        clock_mhz: float | None = None
        temp: float | None = None
        power: float | None = None

        if self._is_apple_silicon and self._apple_monitor:
            clock_mhz = self._apple_monitor.cpu_freq_mhz
            power = self._apple_monitor.cpu_power
            temp = self._apple_monitor.get_cpu_temperature()
            
            # 可以使用 IOReport 的使用率，但 psutil 更稳定
            # apple_usage = self._apple_monitor.cpu_usage
            # if apple_usage is not None:
            #     usage = apple_usage

            if temp:
                self._last_cpu_temp = temp

        # 后备方案
        if clock_mhz is None:
            freq = psutil.cpu_freq()
            clock_mhz = freq.current if freq else None

        if temp is None:
            temp = self._get_cpu_temp_fallback()

        return {
            "name": self._cpu_name,
            "usage": usage,
            "temp": temp or self._last_cpu_temp,
            "power": power,
            "clock_mhz": clock_mhz
        }

    def _get_cpu_temp_fallback(self) -> float | None:
        """后备温度获取方法"""
        output = self._run_cmd(['osx-cpu-temp'])
        if output:
            match = re.search(r'(\d+\.?\d*)', output)
            if match:
                return float(match.group(1))

        output = self._run_cmd(['istats', '--no-graphs'])
        if output:
            match = re.search(r'CPU temp:\s*(\d+\.?\d*)', output)
            if match:
                return float(match.group(1))

        return None

    def get_gpu_list(self) -> list[str]:
        """获取 GPU 列表"""
        self._update_gpu_info()
        if self._gpu_info_cache:
            return [g["name"] for g in self._gpu_info_cache]
        return ["Integrated GPU"]

    def _update_gpu_info(self) -> None:
        """使用 system_profiler 获取 GPU 信息"""
        if self._gpu_info_cache and time.time() - self._gpu_info_time < 60:
            return

        output = self._run_cmd(
            ['system_profiler', 'SPDisplaysDataType', '-json'], timeout=10)
        if output:
            try:
                data = json.loads(output)
                displays = data.get('SPDisplaysDataType', [])

                self._gpu_info_cache = []
                for display in displays:
                    gpu_name: str = display.get('sppci_model', 'Unknown GPU')

                    if 'Apple' in gpu_name or self._is_apple_silicon:
                        chip_type = display.get('sppci_model', 'Apple GPU')
                        cores = display.get('sppci_cores', '')
                        if cores:
                            gpu_name = f"{chip_type} ({cores} cores)"

                    vram = display.get('spdisplays_vram', '0')
                    vram_bytes: int = 0
                    match = re.search(r'(\d+)\s*(GB|MB)', str(vram), re.IGNORECASE)
                    if match:
                        size = int(match.group(1))
                        unit = match.group(2).upper()
                        vram_bytes = size * (1024**3 if unit == "GB" else 1024**2)

                    if self._is_apple_silicon and vram_bytes == 0:
                        mem = psutil.virtual_memory()
                        vram_bytes = mem.total

                    self._gpu_info_cache.append({
                        "name": gpu_name,
                        "mem_total_b": vram_bytes,
                        "is_integrated": (self._is_apple_silicon or 'Intel' in gpu_name)
                    })

                self._gpu_info_time = time.time()
            except Exception:
                pass

        if not self._gpu_info_cache:
            gpu_name = "Apple GPU" if self._is_apple_silicon else "Unknown GPU"
            self._gpu_info_cache = [{
                "name": gpu_name,
                "mem_total_b": 0,
                "is_integrated": True
            }]

    def get_gpu_info(self, gpu_index: int = 0) -> dict[str, Any]:
        """获取 GPU 信息"""
        self._update_gpu_info()

        gpu: dict[str, Any] = {}
        if self._gpu_info_cache and gpu_index < len(self._gpu_info_cache):
            gpu = self._gpu_info_cache[gpu_index]

        util: float | None = None
        temp: float | None = None
        power: float | None = None
        clock_mhz: float | None = None
        mem_used: float | None = None

        if self._is_apple_silicon and self._apple_monitor:
            util = self._apple_monitor.gpu_usage
            power = self._apple_monitor.gpu_power
            clock_mhz = self._apple_monitor.gpu_freq_mhz
            temp = self._apple_monitor.get_gpu_temperature()

            if temp:
                self._last_gpu_temp = temp

        return {
            "name": gpu.get("name", "Unknown GPU"),
            "util": util,
            "temp": temp or self._last_gpu_temp,
            "clock_mhz": clock_mhz,
            "mem_used_b": mem_used,
            "mem_total_b": gpu.get("mem_total_b"),
            "power": power
        }

    def get_memory_info(self) -> dict[str, Any]:
        """获取内存信息"""
        mem = psutil.virtual_memory()
        freq: int | None = self._get_memory_freq()

        return {
            "used_b": mem.used,
            "total_b": mem.total,
            "percent": mem.percent,
            "freq_mhz": freq
        }

    def _get_memory_freq(self) -> int | None:
        """获取内存频率"""
        if hasattr(self, '_cached_mem_freq'):
            return self._cached_mem_freq

        output = self._run_cmd(
            ['system_profiler', 'SPMemoryDataType', '-json'], timeout=10)
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
                                self._cached_mem_freq: int | None = int(match.group(1))
                                return self._cached_mem_freq
            except Exception:
                pass

        self._cached_mem_freq = None
        return None


# =============================================================================
# Linux 硬件监控
# =============================================================================

class LinuxHardwareMonitor:
    """Linux 硬件监控实现"""

    def __init__(self) -> None:
        self._cpu_name: str | None = None
        self._gpu_type: str | None = None  # 'nvidia', 'amd', 'intel', None
        self._detect_gpu_type()

    def _detect_gpu_type(self) -> None:
        """检测 GPU 类型"""
        try:
            result = subprocess.run(
                ['lspci'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout.lower()
                if 'nvidia' in output:
                    self._gpu_type = 'nvidia'
                elif 'amd' in output or 'radeon' in output:
                    self._gpu_type = 'amd'
                elif 'intel' in output:
                    self._gpu_type = 'intel'
        except Exception:
            pass

    def _run_cmd(self, cmd: list[str], timeout: int = 5) -> str | None:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout)
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None

    def get_cpu_info(self) -> dict[str, Any]:
        if self._cpu_name is None:
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('model name'):
                            self._cpu_name = line.split(':')[1].strip()
                            break
            except Exception:
                self._cpu_name = "Unknown CPU"

        usage: float | None = psutil.cpu_percent(interval=None)
        freq = psutil.cpu_freq()
        clock_mhz: float | None = freq.current if freq else None
        temp: float | None = self._get_cpu_temp()
        power: float | None = self._get_cpu_power()

        return {
            "name": self._cpu_name,
            "usage": usage,
            "temp": temp,
            "power": power,
            "clock_mhz": clock_mhz
        }

    def _get_cpu_temp(self) -> float | None:
        try:
            temps = psutil.sensors_temperatures()
            for name in ['coretemp', 'k10temp', 'zenpower', 'cpu_thermal']:
                if name in temps:
                    readings = temps[name]
                    if readings:
                        return readings[0].current
        except Exception:
            pass

        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return float(f.read().strip()) / 1000
        except Exception:
            pass

        return None

    def _get_cpu_power(self) -> float | None:
        try:
            rapl_path = '/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj'
            if os.path.exists(rapl_path):
                with open(rapl_path, 'r') as f:
                    energy1 = int(f.read().strip())
                time.sleep(0.1)
                with open(rapl_path, 'r') as f:
                    energy2 = int(f.read().strip())
                return (energy2 - energy1) / 100000  # uJ -> W (over 0.1s)
        except Exception:
            pass
        return None

    def get_gpu_list(self) -> list[str]:
        if self._gpu_type == 'nvidia':
            output = self._run_cmd([
                'nvidia-smi', '--query-gpu=name', '--format=csv,noheader'])
            if output:
                return [line.strip() for line in output.strip().split('\n')]
        return ["Unknown GPU"]

    def get_gpu_info(self, gpu_index: int = 0) -> dict[str, Any]:
        if self._gpu_type == 'nvidia':
            return self._get_nvidia_gpu_info(gpu_index)
        return {
            "name": "Unknown GPU",
            "util": None,
            "temp": None,
            "clock_mhz": None,
            "mem_used_b": None,
            "mem_total_b": None,
            "power": None
        }

    def _get_nvidia_gpu_info(self, gpu_index: int = 0) -> dict[str, Any]:
        output = self._run_cmd([
            'nvidia-smi',
            f'--id={gpu_index}',
            '--query-gpu=name,utilization.gpu,temperature.gpu,'
            'clocks.current.graphics,memory.used,memory.total,power.draw',
            '--format=csv,noheader,nounits'
        ])

        if output:
            try:
                parts = [p.strip() for p in output.strip().split(',')]
                return {
                    "name": parts[0],
                    "util": float(parts[1]) if parts[1] else None,
                    "temp": float(parts[2]) if parts[2] else None,
                    "clock_mhz": float(parts[3]) if parts[3] else None,
                    "mem_used_b": int(float(parts[4]) * 1024 * 1024) if parts[4] else None,
                    "mem_total_b": int(float(parts[5]) * 1024 * 1024) if parts[5] else None,
                    "power": float(parts[6]) if parts[6] else None
                }
            except Exception:
                pass

        return {
            "name": "NVIDIA GPU",
            "util": None,
            "temp": None,
            "clock_mhz": None,
            "mem_used_b": None,
            "mem_total_b": None,
            "power": None
        }

    def get_memory_info(self) -> dict[str, Any]:
        mem = psutil.virtual_memory()
        freq: int | None = None

        output = self._run_cmd(['dmidecode', '-t', 'memory'])
        if output:
            match = re.search(r'Speed:\s*(\d+)\s*MT/s', output)
            if match:
                freq = int(match.group(1))

        return {
            "used_b": mem.used,
            "total_b": mem.total,
            "percent": mem.percent,
            "freq_mhz": freq
        }


# =============================================================================
# 磁盘和网络监控
# =============================================================================

class CachedDisks:
    """带缓存的磁盘信息"""

    def __init__(self) -> None:
        self.prev_io: dict[str, dict[str, int]] = {}
        self.prev_time: float | None = None
        self.disk_info_cache: list[dict[str, Any]] | None = None
        self.disk_info_cache_time: float = 0
        self.disk_info_cache_duration: int = 60

    def _get_disk_info(self) -> list[dict[str, Any]]:
        current_time = time.time()
        if (self.disk_info_cache is None or
                current_time - self.disk_info_cache_time >
                self.disk_info_cache_duration):
            self.disk_info_cache = self._build_disk_info()
            self.disk_info_cache_time = current_time
        return self.disk_info_cache

    def _build_disk_info(self) -> list[dict[str, Any]]:
        disks: list[dict[str, Any]] = []

        # Windows: 使用WMI获取详细信息
        if IS_WINDOWS and wmi_module:
            try:
                w = wmi_module.WMI()
                for d in w.Win32_DiskDrive():
                    disk_info: dict[str, Any] = {
                        'index': int(d.Index) if d.Index else 0,
                        'model': (d.Model or f"PhysicalDrive{d.Index}").strip(),
                        'size': int(d.Size) if d.Size else 0,
                        'device_id': f"PhysicalDrive{d.Index}"
                    }
                    letters: list[str] = []
                    try:
                        assoc = d.associators("Win32_DiskDriveToDiskPartition")
                        for p in assoc:
                            for ld in p.associators("Win32_LogicalDiskToPartition"):
                                if ld.DeviceID:
                                    letters.append(ld.DeviceID)
                    except Exception:
                        pass
                    disk_info['letters'] = sorted(set(letters))
                    disks.append(disk_info)
                return disks
            except Exception:
                pass

        # 通用方法: psutil
        partitions = psutil.disk_partitions()
        seen_devices: set[str] = set()

        for i, partition in enumerate(partitions):
            if partition.fstype in ('squashfs', 'tmpfs', 'devtmpfs', 'overlay'):
                continue
            if IS_WINDOWS and 'cdrom' in partition.opts:
                continue
            if IS_LINUX and partition.mountpoint.startswith('/snap'):
                continue

            device_base = partition.device.split('/')[-1].rstrip('0123456789')
            if device_base in seen_devices and not IS_WINDOWS:
                continue
            seen_devices.add(device_base)

            try:
                usage = psutil.disk_usage(partition.mountpoint)
                model: str
                if IS_LINUX:
                    model = self._get_linux_disk_model(partition.device) or partition.device
                elif IS_MACOS:
                    model = self._get_macos_disk_model(partition.device) or partition.device
                else:
                    model = f"Drive {partition.device}"

                letters_list: list[str] = [partition.mountpoint]
                if IS_WINDOWS:
                    letters_list = [partition.device.replace('\\', '')]

                disks.append({
                    'index': i,
                    'model': model,
                    'size': usage.total,
                    'device': partition.device,
                    'letters': letters_list
                })
            except Exception:
                continue

        return disks

    def _get_linux_disk_model(self, device: str) -> str | None:
        try:
            dev_name = device.split('/')[-1].rstrip('0123456789')
            model_path = f'/sys/block/{dev_name}/device/model'
            if os.path.exists(model_path):
                with open(model_path) as f:
                    return f.read().strip()
        except Exception:
            pass
        return None

    def _get_macos_disk_model(self, device: str) -> str | None:
        try:
            result = subprocess.run(
                ['diskutil', 'info', device],
                capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Device / Media Name:' in line:
                        return line.split(':')[1].strip()
        except Exception:
            pass
        return None

    def get_disk_data(self) -> list[dict[str, Any]]:
        current_time = time.time()
        current_io: dict[str, dict[str, int]] = {}

        try:
            io_counters = psutil.disk_io_counters(perdisk=True)
            for device, io in io_counters.items():
                current_io[device] = {
                    'read_bytes': io.read_bytes,
                    'write_bytes': io.write_bytes
                }
        except Exception:
            pass

        disks = self._get_disk_info()
        disk_data: list[dict[str, Any]] = []

        for disk in disks:
            used: int = 0
            for letter in disk.get('letters', []):
                try:
                    mountpoint: str
                    if IS_WINDOWS:
                        mountpoint = letter + '\\' if len(letter) <= 2 else letter
                    else:
                        mountpoint = letter
                    usage = psutil.disk_usage(mountpoint)
                    used += usage.used
                except Exception:
                    continue

            read_speed: float | None = None
            write_speed: float | None = None

            if self.prev_io and self.prev_time and current_time > self.prev_time:
                dt = current_time - self.prev_time
                device_key: str | None = None
                if IS_WINDOWS:
                    device_key = f"PhysicalDrive{disk['index']}"
                else:
                    device_str = disk.get('device', disk.get('model', ''))
                    dev_name = device_str.split('/')[-1].rstrip('0123456789')
                    for key in current_io:
                        if key == dev_name or key.startswith(dev_name):
                            device_key = key
                            break

                if (device_key and device_key in current_io and
                        device_key in self.prev_io and dt > 0):
                    read_speed = max(0.0, (
                        current_io[device_key]['read_bytes'] -
                        self.prev_io[device_key]['read_bytes']) / dt)
                    write_speed = max(0.0, (
                        current_io[device_key]['write_bytes'] -
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
    """带缓存的网络信息"""

    def __init__(self) -> None:
        self.prev_stats: Any | None = None
        self.prev_time: float | None = None

    def get_network_data(self) -> dict[str, float | None]:
        current_time = time.time()

        try:
            current_stats = psutil.net_io_counters(pernic=False)
        except Exception:
            return {"up": None, "down": None}

        up_speed: float | None = None
        down_speed: float | None = None

        if (self.prev_stats and self.prev_time and
                current_time > self.prev_time):
            dt = current_time - self.prev_time
            if dt > 0:
                up_speed = max(0.0, (
                    current_stats.bytes_sent - self.prev_stats.bytes_sent) / dt)
                down_speed = max(0.0, (
                    current_stats.bytes_recv - self.prev_stats.bytes_recv) / dt)

        self.prev_stats = current_stats
        self.prev_time = current_time

        return {"up": up_speed, "down": down_speed}


# =============================================================================
# 统一接口
# =============================================================================

class HardwareMonitor:
    """统一的跨平台硬件监控器"""

    def __init__(self, lazy_init: bool = False) -> None:
        """初始化硬件监控器

        Args:
            lazy_init: 如果为True，则延迟初始化平台监控器（用于异步启动）
        """
        self.disks: CachedDisks = CachedDisks()
        self.network: CachedNetwork = CachedNetwork()

        self._cpu_percent_cache: float | None = None
        self._cpu_percent_cache_time: float = 0
        self._initialized: bool = False
        self._init_lock: threading.Lock = threading.Lock()

        # 根据平台初始化不同的监控器
        self.lhm: OptimizedLHM | None = None
        self._platform_monitor: (
            Union[MacOSHardwareMonitor, LinuxHardwareMonitor] | None
        ) = None

        if not lazy_init:
            self._do_init()

    def _do_init(self) -> None:
        """执行实际的初始化（可在后台线程调用）"""
        with self._init_lock:
            if self._initialized:
                return

            if IS_WINDOWS:
                self.lhm = OptimizedLHM()
                self._platform_monitor = None
            elif IS_MACOS:
                self.lhm = None
                self._platform_monitor = MacOSHardwareMonitor()
            elif IS_LINUX:
                self.lhm = None
                self._platform_monitor = LinuxHardwareMonitor()

            # 初始化 psutil CPU 百分比（首次调用返回0）
            try:
                psutil.cpu_percent(interval=None)
            except Exception:
                pass

            self._initialized = True

    def ensure_initialized(self) -> None:
        """确保已初始化（阻塞直到完成）"""
        if not self._initialized:
            self._do_init()

    def is_initialized(self) -> bool:
        """检查是否已完成初始化"""
        return self._initialized

    def is_lhm_loaded(self) -> bool:
        """检查LHM是否加载 (仅Windows)"""
        if IS_WINDOWS and self.lhm:
            return self.lhm.available
        return False

    def get_platform_name(self) -> str:
        """获取当前平台名称"""
        if IS_WINDOWS:
            return f"Windows {platform.release()}"
        elif IS_MACOS:
            return f"macOS {platform.mac_ver()[0]}"
        elif IS_LINUX:
            try:
                with open('/etc/os-release') as f:
                    for line in f:
                        if line.startswith('PRETTY_NAME='):
                            return line.split('=')[1].strip().strip('"')
            except Exception:
                pass
            return f"Linux {platform.release()}"
        return "Unknown"

    def get_cpu_name(self) -> str:
        cpu_info = self.get_cpu_data()
        return cpu_info.get("name", "CPU")

    def get_cpu_data(self) -> dict[str, Any]:
        # Windows: 使用LHM
        if IS_WINDOWS and self.lhm:
            cpu_info = self.lhm.get_cpu_info()

            # 如果LHM没有使用率，使用psutil
            if cpu_info.get("usage") is None:
                current_time = time.time()
                if (self._cpu_percent_cache is None or
                        current_time - self._cpu_percent_cache_time > 1.0):
                    try:
                        self._cpu_percent_cache = psutil.cpu_percent(interval=None)
                        self._cpu_percent_cache_time = current_time
                    except Exception:
                        pass
                cpu_info["usage"] = self._cpu_percent_cache

            return cpu_info

        # macOS/Linux: 使用平台特定监控器
        elif self._platform_monitor:
            return self._platform_monitor.get_cpu_info()

        # 后备: 基本psutil
        freq = psutil.cpu_freq()
        return {
            "name": "CPU",
            "usage": psutil.cpu_percent(interval=None),
            "temp": None,
            "power": None,
            "clock_mhz": freq.current if freq else None
        }

    def get_gpu_data(self, gpu_index: int = 0) -> dict[str, Any]:
        if IS_WINDOWS and self.lhm:
            return self.lhm.get_gpu_info(gpu_index)
        elif self._platform_monitor:
            return self._platform_monitor.get_gpu_info(gpu_index)
        return {
            "name": "GPU", "util": None, "temp": None, "clock_mhz": None,
            "mem_used_b": None, "mem_total_b": None, "power": None
        }

    @property
    def gpu_names(self) -> list[str]:
        if IS_WINDOWS and self.lhm:
            return self.lhm.get_gpu_names()
        elif self._platform_monitor:
            return self._platform_monitor.get_gpu_list()
        return ["未检测到GPU"]

    def get_memory_data(self) -> dict[str, Any]:
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

    def get_disk_data(self) -> list[dict[str, Any]]:
        return self.disks.get_disk_data()

    def get_network_data(self) -> dict[str, float | None]:
        return self.network.get_network_data()


# =============================================================================
# 辅助函数
# =============================================================================

def convert_memory_to_bytes(
    value: float | None,
    data_type: str = "auto"
) -> float | None:
    """智能内存单位转换"""
    if value is None or value < 0:
        return None

    if value == 0:
        return 0.0

    if data_type == "gpu_mem":
        if value < 1 or value < 200:
            return value * (1024 ** 3)
        elif value < 200000:
            return value * (1024 ** 2)
        else:
            return value

    elif data_type == "system_mem":
        if value < 1 or value < 1024:
            return value * (1024 ** 3)
        elif value < 1048576:
            return value * (1024 ** 2)
        else:
            return value

    else:
        if value < 1 or value < 200:
            return value * (1024 ** 3)
        elif value < 200000:
            return value * (1024 ** 2)
        elif value < 1073741824:
            return value * 1024
        else:
            return value


def validate_memory_value(
    value: float | None,
    expected_range_gb: tuple[float, float] = (0.1, 256)
) -> bool:
    if value is None or value <= 0:
        return False
    value_gb = value / (1024 ** 3)
    return expected_range_gb[0] <= value_gb <= expected_range_gb[1]


def bytes2human(n: float | None) -> str:
    if n is None:
        return "—"
    n = float(n)
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.1f} {units[i]}" if i else f"{int(n)} {units[i]}"


def pct_str(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:.0f}%"


def mhz_str(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:.0f} MHz"


def temp_str(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:.0f} °C"


def watt_str(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:.0f} W"


# Windows 专用类 (如果在 Windows 上)
if IS_WINDOWS:
    class WindowsHardwareMonitor:
        """Windows 硬件监控实现"""

        def __init__(self) -> None:
            self._lhm: OptimizedLHM = OptimizedLHM()
            self._cpu_name: str | None = None
            self._init_cpu_name()

        def _init_cpu_name(self) -> None:
            if self._lhm.available:
                names = self._lhm.get_cpu_names()
                if names:
                    self._cpu_name = names[0]

            if not self._cpu_name:
                try:
                    import winreg
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                    self._cpu_name, _ = winreg.QueryValueEx(
                        key, "ProcessorNameString")
                    winreg.CloseKey(key)
                except Exception:
                    self._cpu_name = "Unknown CPU"

        def get_cpu_info(self) -> dict[str, Any]:
            usage: float | None = None
            temp: float | None = None
            power: float | None = None
            clock_mhz: float | None = None

            if self._lhm.available:
                usage = self._lhm.get_cpu_load()
                temp = self._lhm.get_cpu_temp()
                power = self._lhm.get_cpu_power()
                clock_mhz = self._lhm.get_cpu_clock()

            if usage is None:
                usage = psutil.cpu_percent()

            if clock_mhz is None:
                freq = psutil.cpu_freq()
                clock_mhz = freq.current if freq else None

            return {
                "name": self._cpu_name,
                "usage": usage,
                "temp": temp,
                "power": power,
                "clock_mhz": clock_mhz
            }

        def get_gpu_list(self) -> list[str]:
            if self._lhm.available:
                return self._lhm.get_gpu_names()
            return []

        def get_gpu_info(self, gpu_index: int = 0) -> dict[str, Any]:
            if self._lhm.available:
                names = self._lhm.get_gpu_names()
                name = names[gpu_index] if gpu_index < len(names) else "Unknown"
                return {
                    "name": name,
                    "util": self._lhm.get_gpu_load(gpu_index),
                    "temp": self._lhm.get_gpu_temp(gpu_index),
                    "clock_mhz": self._lhm.get_gpu_clock(gpu_index),
                    "mem_used_b": self._lhm.get_gpu_mem_used(gpu_index),
                    "mem_total_b": self._lhm.get_gpu_mem_total(gpu_index),
                    "power": self._lhm.get_gpu_power(gpu_index)
                }
            return {
                "name": "Unknown",
                "util": None,
                "temp": None,
                "clock_mhz": None,
                "mem_used_b": None,
                "mem_total_b": None,
                "power": None
            }

        def get_memory_info(self) -> dict[str, Any]:
            mem = psutil.virtual_memory()
            freq_mhz = None
            if self._lhm.available:
                freq_mhz = self._lhm.get_memory_clock()
            return {
                "used_b": mem.used,
                "total_b": mem.total,
                "percent": mem.percent,
                "freq_mhz": freq_mhz
            }