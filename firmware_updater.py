#!/usr/bin/env python3
"""
固件更新模块 (v3 - 基于时间间隔的进度追踪)

根据实际测试，sftool 的输出特点：
- Spinner: 0% 和 100% 几乎同时出现（间隔 < 0.5 秒）
- Bar: 0% 后面跟着中间值（10%, 20%, 31%...），每次间隔约 1-2 秒
"""
from __future__ import annotations

import contextlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from serial_assistant import SerialAssistant

# 平台检测
SYSTEM: str = platform.system().lower()
IS_WINDOWS: bool = SYSTEM == 'windows'


class FirmwareUpdateStatus(Enum):
    """固件更新状态"""
    IDLE = "idle"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    PREPARING = "preparing"
    FLASHING = "flashing"
    SUCCESS = "success"
    FAILED = "failed"
    RECONNECTING = "reconnecting"


@dataclass
class FirmwareFile:
    """固件文件信息"""
    name: str
    address: str
    required: bool = True


# 固件文件配置
FIRMWARE_FILES: list[FirmwareFile] = [
    FirmwareFile("bootloader.bin", "0x12208000", required=True),
    FirmwareFile("ER_IROM1.bin", "0x12218000", required=True),
    FirmwareFile("ER_IROM2.bin", "0x12660000", required=True),
    FirmwareFile("ER_IROM3.bin", "0x12460000", required=True),
    FirmwareFile("dfu_pan.bin", "0x12008000", required=True),
    FirmwareFile("ftab.bin", "0x12000000", required=True),
]

# sftool 配置
SFTOOL_CHIP: str = "SF32LB52"


@dataclass
class ProgressTracker:
    """
    sftool 进度追踪器 (基于时间和中间值检测)
    
    检测策略：
    1. 当看到 0% 时，记录时间，等待下一个值
    2. 如果下一个值是 100% 且间隔 < 0.5 秒，这是 Spinner，忽略
    3. 如果下一个值是中间值（1-99%），这是 Bar，开始追踪
    4. Bar 完成时（看到 100%），增加已完成文件计数
    """
    total_files: int = 0
    completed_bars: int = 0  # 完成的 Bar 数量（对应已完成的文件）
    current_bar_progress: int = 0  # 当前 Bar 的进度 (0-100)
    
    # 状态追踪
    last_zero_time: float = 0  # 上次看到 0% 的时间
    is_in_bar: bool = False  # 是否正在追踪一个 Bar
    waiting_for_next: bool = False  # 是否在等待 0% 后的下一个值
    
    # 阈值配置
    SPINNER_MAX_DURATION: float = 0.5  # Spinner 的 0% 到 100% 最大间隔（秒）
    
    def process_percent(self, percent: int, timestamp: float) -> tuple[bool, int]:
        """
        处理一个百分比值
        
        Args:
            percent: 百分比值 (0-100)
            timestamp: 时间戳
            
        Returns:
            (是否应该更新 UI 进度, 当前总体进度百分比 0-100)
        """
        should_update = False
        
        if percent == 0:
            # 新的序列开始
            self.last_zero_time = timestamp
            self.waiting_for_next = True
            
            # 如果之前在 Bar 中且进度已经很高，认为上一个 Bar 完成了
            if self.is_in_bar and self.current_bar_progress >= 90:
                self.completed_bars += 1
                should_update = True
            
            self.is_in_bar = False
            self.current_bar_progress = 0
            
        elif percent == 100:
            if self.waiting_for_next:
                # 0% 后直接是 100%
                duration = timestamp - self.last_zero_time
                if duration < self.SPINNER_MAX_DURATION:
                    # 这是 Spinner，忽略
                    self.waiting_for_next = False
                else:
                    # 间隔较长，可能是 Bar 完成（虽然没看到中间值）
                    if self.is_in_bar:
                        self.completed_bars += 1
                        self.current_bar_progress = 0  # 重置为0，不是100
                        should_update = True
                    self.waiting_for_next = False
                    self.is_in_bar = False
            elif self.is_in_bar:
                # Bar 正常完成
                self.completed_bars += 1
                self.current_bar_progress = 0  # 重置为0，不是100
                should_update = True
                self.is_in_bar = False
                self.waiting_for_next = False
        else:
            # 中间值 (1-99%)，这肯定是 Bar
            self.is_in_bar = True
            self.waiting_for_next = False
            self.current_bar_progress = percent
            should_update = True
        
        return should_update, self._calculate_total_progress()
    
    def _calculate_total_progress(self) -> int:
        """计算总体进度 (0-100)"""
        if self.total_files == 0:
            return 0
        
        # 总进度 = (已完成的 Bar 数 * 100 + 当前 Bar 进度) / 总文件数
        raw = (self.completed_bars * 100 + self.current_bar_progress) / self.total_files
        return min(int(raw), 100)
    
    def reset(self, total_files: int):
        """重置追踪器"""
        self.total_files = total_files
        self.completed_bars = 0
        self.current_bar_progress = 0
        self.last_zero_time = 0
        self.is_in_bar = False
        self.waiting_for_next = False


class FirmwareUpdater:
    """固件更新器类"""

    def __init__(
        self,
        serial_assistant: SerialAssistant | None = None,
        sftool_path: str | None = None
    ) -> None:
        self.serial_assistant: SerialAssistant | None = serial_assistant
        self._sftool_path: str | None = sftool_path
        
        self._status: FirmwareUpdateStatus = FirmwareUpdateStatus.IDLE
        self._status_message: str = ""
        self._progress: int = 0
        
        self._temp_dir: str | None = None
        self._extracted_files: dict[str, str] = {}
        
        self.on_status_changed: Callable[[FirmwareUpdateStatus, str], None] | None = None
        self.on_progress_changed: Callable[[int], None] | None = None
        
        self._lock: threading.Lock = threading.Lock()
        self._update_thread: threading.Thread | None = None
        
        # 进度追踪器
        self._progress_tracker = ProgressTracker()

    @property
    def status(self) -> FirmwareUpdateStatus:
        return self._status

    @property
    def status_message(self) -> str:
        return self._status_message

    @property
    def progress(self) -> int:
        return self._progress

    @property
    def is_busy(self) -> bool:
        return self._status in [
            FirmwareUpdateStatus.VALIDATING,
            FirmwareUpdateStatus.PREPARING,
            FirmwareUpdateStatus.FLASHING,
            FirmwareUpdateStatus.RECONNECTING,
        ]

    def set_serial_assistant(self, serial_assistant: SerialAssistant) -> None:
        self.serial_assistant = serial_assistant

    def _set_status(self, status: FirmwareUpdateStatus, message: str = "") -> None:
        self._status = status
        self._status_message = message
        if self.on_status_changed:
            with contextlib.suppress(Exception):
                self.on_status_changed(status, message)

    def _set_progress(self, progress: int) -> None:
        self._progress = max(0, min(100, progress))
        if self.on_progress_changed:
            with contextlib.suppress(Exception):
                self.on_progress_changed(self._progress)

    def _find_sftool(self) -> str | None:
        if self._sftool_path and os.path.isfile(self._sftool_path):
            return self._sftool_path

        system = platform.system()
        if system == 'Windows':
            sftool_names = ['sftool.exe']
        else:
            sftool_names = ['sftool', 'sftool.bin']

        search_paths: list[Path] = []

        if getattr(sys, 'frozen', False):
            exe_path = Path(sys.executable)
            
            if system == 'Darwin' and '.app' in str(exe_path):
                macos_dir = exe_path.parent
                contents_dir = macos_dir.parent
                resources_dir = contents_dir / "Resources"
                
                for name in sftool_names:
                    search_paths.append(resources_dir / "tools" / name)
                    search_paths.append(resources_dir / name)
                
                for name in sftool_names:
                    search_paths.append(macos_dir / "tools" / name)
                    search_paths.append(macos_dir / name)
                
                if hasattr(sys, '_MEIPASS'):
                    meipass_dir = Path(sys._MEIPASS)
                    for name in sftool_names:
                        search_paths.append(meipass_dir / "tools" / name)
                        search_paths.append(meipass_dir / name)
            else:
                app_dir = exe_path.parent
                for name in sftool_names:
                    search_paths.append(app_dir / name)
                    search_paths.append(app_dir / "tools" / name)
                    search_paths.append(app_dir / "bin" / name)
                
                if hasattr(sys, '_MEIPASS'):
                    meipass_dir = Path(sys._MEIPASS)
                    for name in sftool_names:
                        search_paths.append(meipass_dir / "tools" / name)
                        search_paths.append(meipass_dir / name)
        else:
            app_dir = Path(__file__).parent
            for name in sftool_names:
                search_paths.append(app_dir / name)
                search_paths.append(app_dir / "tools" / name)
                search_paths.append(app_dir / "bin" / name)

        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for path_dir in path_dirs:
            for name in sftool_names:
                search_paths.append(Path(path_dir) / name)

        if system == 'Darwin':
            homebrew_paths = [
                Path('/opt/homebrew/bin'),
                Path('/usr/local/bin'),
            ]
            for brew_path in homebrew_paths:
                for name in sftool_names:
                    search_paths.append(brew_path / name)

        for path in search_paths:
            if path.is_file():
                if system != 'Windows' and not os.access(path, os.X_OK):
                    try:
                        os.chmod(path, 0o755)
                    except Exception:
                        continue
                self._sftool_path = str(path)
                return self._sftool_path

        return None

    def _cleanup_temp(self) -> None:
        if self._temp_dir and os.path.exists(self._temp_dir):
            with contextlib.suppress(Exception):
                shutil.rmtree(self._temp_dir)
        self._temp_dir = None
        self._extracted_files.clear()

    def validate_firmware_zip(self, zip_path: str) -> tuple[bool, str, list[str]]:
        self._set_status(FirmwareUpdateStatus.VALIDATING, "正在验证固件文件...")
        self._set_progress(0)
        
        self._cleanup_temp()
        
        found_files: list[str] = []
        missing_files: list[str] = []

        try:
            if not os.path.isfile(zip_path):
                self._set_status(FirmwareUpdateStatus.INVALID, "文件不存在")
                return False, "文件不存在", []

            if not zipfile.is_zipfile(zip_path):
                self._set_status(FirmwareUpdateStatus.INVALID, "不是有效的 ZIP 文件")
                return False, "不是有效的 ZIP 文件", []

            self._set_progress(20)

            self._temp_dir = tempfile.mkdtemp(prefix="superkey_fw_")

            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(self._temp_dir)

            self._set_progress(50)

            for fw_file in FIRMWARE_FILES:
                file_found = False
                
                for root, _dirs, files in os.walk(self._temp_dir):
                    if fw_file.name in files:
                        file_path = os.path.join(root, fw_file.name)
                        self._extracted_files[fw_file.name] = file_path
                        found_files.append(fw_file.name)
                        file_found = True
                        break
                
                if not file_found and fw_file.required:
                    missing_files.append(fw_file.name)

            self._set_progress(80)

            if missing_files:
                msg = f"缺少必需文件: {', '.join(missing_files)}"
                self._set_status(FirmwareUpdateStatus.INVALID, msg)
                return False, msg, found_files

            self._set_progress(100)
            self._set_status(
                FirmwareUpdateStatus.VALID,
                f"固件文件验证通过 ({len(found_files)} 个文件)"
            )
            return True, "固件文件验证通过", found_files

        except zipfile.BadZipFile:
            self._set_status(FirmwareUpdateStatus.INVALID, "ZIP 文件损坏")
            return False, "ZIP 文件损坏", []
        except Exception as e:
            self._set_status(FirmwareUpdateStatus.INVALID, f"验证失败: {str(e)}")
            return False, f"验证失败: {str(e)}", []

    def _build_flash_command(self, port: str) -> list[str]:
        sftool_path = self._find_sftool()
        if not sftool_path:
            sftool_name = "sftool.exe" if platform.system() == "Windows" else "sftool"
            raise FileNotFoundError(f"找不到 {sftool_name}")

        cmd: list[str] = [
            sftool_path,
            "-c", SFTOOL_CHIP,
            "-p", port,
            "write_flash",
        ]

        for fw_file in FIRMWARE_FILES:
            if fw_file.name in self._extracted_files:
                file_path = self._extracted_files[fw_file.name]
                cmd.append(f"{file_path}@{fw_file.address}")

        return cmd

    def _get_flash_file_count(self) -> int:
        return len(self._extracted_files)

    def start_update(self) -> bool:
        with self._lock:
            if self.is_busy:
                return False

            if self._status != FirmwareUpdateStatus.VALID:
                self._set_status(FirmwareUpdateStatus.FAILED, "请先验证固件文件")
                return False

            if not self._extracted_files:
                self._set_status(FirmwareUpdateStatus.FAILED, "没有可用的固件文件")
                return False

            if not self._find_sftool():
                sftool_name = "sftool.exe" if platform.system() == "Windows" else "sftool"
                self._set_status(FirmwareUpdateStatus.FAILED, f"找不到 {sftool_name}，请将其放在程序目录下")
                return False

            if not self.serial_assistant:
                self._set_status(FirmwareUpdateStatus.FAILED, "串口助手未初始化")
                return False

            if not self.serial_assistant.is_connected:
                self._set_status(FirmwareUpdateStatus.FAILED, "请先连接设备")
                return False

            self._update_thread = threading.Thread(target=self._update_worker, daemon=True)
            self._update_thread.start()
            return True

    def _read_stdout_thread(
        self,
        process: subprocess.Popen,
        total_files: int,
        stop_event: threading.Event
    ):
        """
        在独立线程中读取 sftool 的 stdout 输出
        """
        percent_pattern = re.compile(r'^(\d+)%$')
        
        # 重置进度追踪器
        self._progress_tracker.reset(total_files)
        
        try:
            for line in iter(process.stdout.readline, ''):
                if stop_event.is_set():
                    break
                    
                line = line.strip()
                if not line:
                    continue
                
                # 记录当前时间戳
                current_time = time.time()
                
                # 尝试匹配百分比
                match = percent_pattern.match(line)
                if match:
                    percent = int(match.group(1))
                    
                    # 使用追踪器处理百分比（带时间戳）
                    should_update, total_progress = self._progress_tracker.process_percent(
                        percent, current_time
                    )
                    
                    if should_update:
                        # 映射到 UI 进度范围 (30% - 95%)
                        ui_progress = 30 + int(total_progress * 65 / 100)
                        self._set_progress(ui_progress)
                        
                        # 更新状态消息，包含总进度百分比
                        completed = self._progress_tracker.completed_bars
                        current = self._progress_tracker.current_bar_progress
                        
                        if self._progress_tracker.is_in_bar:
                            # 显示: 正在烧录 (2/6) 文件进度 41% | 总进度 35%
                            self._set_status(
                                FirmwareUpdateStatus.FLASHING,
                                f"正在烧录 ({completed + 1}/{total_files}) 文件:{current}%"
                            )
                        elif completed < total_files:
                            self._set_status(
                                FirmwareUpdateStatus.FLASHING,
                                f"正在烧录固件 ({completed + 1}/{total_files})..."
                            )
                
        except Exception:
            pass

    def _update_worker(self) -> None:
        """更新工作线程"""
        port: str = ""
        
        try:
            self._set_status(FirmwareUpdateStatus.PREPARING, "准备烧录...")
            self._set_progress(0)

            if self.serial_assistant and self.serial_assistant.is_connected:
                port = self.serial_assistant.config.get('port', '')
            
            if not port:
                self._set_status(FirmwareUpdateStatus.FAILED, "无法获取当前端口")
                return

            self._set_progress(10)

            auto_reconnect_was_enabled = False
            if self.serial_assistant:
                auto_reconnect_was_enabled = self.serial_assistant.is_auto_reconnect_enabled()
                self.serial_assistant.enable_auto_reconnect(False)

            self._set_status(FirmwareUpdateStatus.PREPARING, "断开设备连接...")
            if self.serial_assistant and self.serial_assistant.is_connected:
                self.serial_assistant.disconnect()
            
            time.sleep(0.5)
            self._set_progress(20)

            self._set_status(FirmwareUpdateStatus.FLASHING, "正在烧录固件...")
            cmd = self._build_flash_command(port)
            
            total_files = self._get_flash_file_count()

            self._set_progress(30)
            
            # Windows 下隐藏控制台窗口
            startupinfo = None
            creationflags = 0
            if IS_WINDOWS:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW

            # 启动 sftool 进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=creationflags,
                text=True,
                bufsize=1,
            )

            # 创建停止事件
            stop_event = threading.Event()
            
            # 启动 stdout 读取线程
            stdout_thread = threading.Thread(
                target=self._read_stdout_thread,
                args=(process, total_files, stop_event),
                daemon=True
            )
            stdout_thread.start()

            # 等待进程结束
            process.wait()
            
            # 通知读取线程停止
            stop_event.set()
            stdout_thread.join(timeout=2)
            
            # 读取 stderr
            _, stderr = process.communicate()
            
            self._set_progress(95)

            if process.returncode != 0:
                error_msg = stderr.strip() if stderr else "未知错误"
                if len(error_msg) > 50:
                    error_msg = "烧录过程中出错"
                self._set_status(FirmwareUpdateStatus.FAILED, f"烧录失败: {error_msg}")
                
                if self.serial_assistant and auto_reconnect_was_enabled:
                    self.serial_assistant.enable_auto_reconnect(True)
                return

            self._set_progress(100)
            self._set_status(FirmwareUpdateStatus.SUCCESS, "固件烧录完成！")

            self._set_status(FirmwareUpdateStatus.RECONNECTING, "正在重新连接设备...")
            time.sleep(1.0)

            if self.serial_assistant:
                self.serial_assistant.configure(
                    port=port,
                    baudrate=1000000,
                    bytesize=8,
                    stopbits=1,
                    parity='N'
                )
                
                reconnect_attempts = 0
                max_attempts = 5
                
                while reconnect_attempts < max_attempts:
                    if self.serial_assistant.connect():
                        self._set_status(
                            FirmwareUpdateStatus.SUCCESS,
                            "固件更新完成，设备已重新连接"
                        )
                        break
                    reconnect_attempts += 1
                    time.sleep(1.0)
                
                if not self.serial_assistant.is_connected:
                    self._set_status(
                        FirmwareUpdateStatus.SUCCESS,
                        "固件更新完成，请手动重新连接设备"
                    )
                
                if auto_reconnect_was_enabled:
                    self.serial_assistant.enable_auto_reconnect(True)

        except FileNotFoundError as e:
            self._set_status(FirmwareUpdateStatus.FAILED, str(e))
        except Exception as e:
            self._set_status(FirmwareUpdateStatus.FAILED, f"更新失败: {str(e)}")
        finally:
            self._cleanup_temp()

    def cancel(self) -> None:
        self._cleanup_temp()
        self._set_status(FirmwareUpdateStatus.IDLE, "")
        self._set_progress(0)

    def get_status_display(self) -> tuple[str, str]:
        status_map: dict[FirmwareUpdateStatus, tuple[str, str]] = {
            FirmwareUpdateStatus.IDLE: ("等待选择固件文件", "neutral"),
            FirmwareUpdateStatus.VALIDATING: ("正在验证...", "neutral"),
            FirmwareUpdateStatus.VALID: ("✓ 固件文件有效，可以开始更新", "good"),
            FirmwareUpdateStatus.INVALID: (f"✗ {self._status_message}", "bad"),
            FirmwareUpdateStatus.PREPARING: ("准备中...", "neutral"),
            FirmwareUpdateStatus.FLASHING: (self._status_message or "正在烧录固件...", "warn"),
            FirmwareUpdateStatus.SUCCESS: (f"✓ {self._status_message}", "good"),
            FirmwareUpdateStatus.FAILED: (f"✗ {self._status_message}", "bad"),
            FirmwareUpdateStatus.RECONNECTING: ("正在重新连接...", "neutral"),
        }
        
        return status_map.get(
            self._status,
            (self._status_message or "未知状态", "neutral")
        )


# 全局实例
_firmware_updater: FirmwareUpdater | None = None


def get_firmware_updater() -> FirmwareUpdater:
    global _firmware_updater
    if _firmware_updater is None:
        _firmware_updater = FirmwareUpdater()
    return _firmware_updater


def set_firmware_updater_serial(serial_assistant: SerialAssistant) -> None:
    updater = get_firmware_updater()
    updater.set_serial_assistant(serial_assistant)


# ============================================================================
# 固件版本检测器
# ============================================================================

class FirmwareVersionChecker:
    """固件版本检测器"""

    VERSION_PATTERN: re.Pattern[str] = re.compile(
        r'FW_VERSION:(release|dev)(\d+)\.(\d+)\.(\d+)'
    )

    def __init__(self, serial_assistant: SerialAssistant | None = None) -> None:
        self.serial_assistant: SerialAssistant | None = serial_assistant
        self._version_string: str = ""
        self._raw_version: str = ""
        self._check_lock: threading.Lock = threading.Lock()
        self._response_event: threading.Event = threading.Event()
        self._response_buffer: str = ""
        self.on_version_checked: Callable[[str], None] | None = None

    @property
    def version_string(self) -> str:
        return self._version_string

    def set_serial_assistant(self, serial_assistant: SerialAssistant) -> None:
        self.serial_assistant = serial_assistant

    def _format_version(self, version_type: str, major: str, minor: str, patch: str) -> str:
        return f"{version_type} v{major}.{minor}.{patch}"

    def check_version_async(self) -> None:
        thread = threading.Thread(target=self._check_version_worker, daemon=True)
        thread.start()

    def _check_version_worker(self) -> None:
        with self._check_lock:
            version = self._do_check_version()
            self._version_string = version

            if self.on_version_checked:
                with contextlib.suppress(Exception):
                    self.on_version_checked(version)

    def _do_check_version(self) -> str:
        if not self.serial_assistant or not self.serial_assistant.is_connected:
            return "未知"

        try:
            self.serial_assistant.clear_rx_buffer()
            self._response_buffer = ""
            self._response_event.clear()

            original_callback = self.serial_assistant.on_data_received

            def capture_response(data: bytes) -> None:
                try:
                    text = data.decode('utf-8', errors='ignore')
                    self._response_buffer += text
                    if 'FW_VERSION:' in self._response_buffer:
                        self._response_event.set()
                except Exception:
                    pass
                if original_callback:
                    original_callback(data)

            self.serial_assistant.on_data_received = capture_response
            self.serial_assistant.send_data("sys_get version\n")
            got_response = self._response_event.wait(timeout=0.5)
            self.serial_assistant.on_data_received = original_callback

            if got_response:
                match = self.VERSION_PATTERN.search(self._response_buffer)
                if match:
                    version_type = match.group(1)
                    major = match.group(2)
                    minor = match.group(3)
                    patch = match.group(4)
                    return self._format_version(version_type, major, minor, patch)

            return "未知"

        except Exception:
            return "未知"


_version_checker: FirmwareVersionChecker | None = None


def get_version_checker() -> FirmwareVersionChecker:
    global _version_checker
    if _version_checker is None:
        _version_checker = FirmwareVersionChecker()
    return _version_checker


def set_version_checker_serial(serial_assistant: SerialAssistant) -> None:
    checker = get_version_checker()
    checker.set_serial_assistant(serial_assistant)