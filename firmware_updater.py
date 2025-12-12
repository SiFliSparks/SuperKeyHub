#!/usr/bin/env python3
"""
固件更新模块
使用 sftool.exe 进行固件烧录
"""
from __future__ import annotations

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
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from serial_assistant import SerialAssistant

# 平台检测
SYSTEM: str = platform.system().lower()
IS_WINDOWS: bool = SYSTEM == 'windows'


class FirmwareUpdateStatus(Enum):
    """固件更新状态"""
    IDLE = "idle"                       # 空闲
    VALIDATING = "validating"           # 正在验证文件
    VALID = "valid"                     # 文件有效
    INVALID = "invalid"                 # 文件无效
    PREPARING = "preparing"             # 准备中
    FLASHING = "flashing"               # 正在烧录
    SUCCESS = "success"                 # 烧录成功
    FAILED = "failed"                   # 烧录失败
    RECONNECTING = "reconnecting"       # 正在重连


@dataclass
class FirmwareFile:
    """固件文件信息"""
    name: str
    address: str
    required: bool = True


# 固件文件配置
FIRMWARE_FILES: list[FirmwareFile] = [
    FirmwareFile("ftab.bin", "0x12000000", required=True),
    FirmwareFile("bootloader.bin", "0x12010000", required=True),
    FirmwareFile("main.bin", "0x12020000", required=True),
]

# sftool 配置
SFTOOL_CHIP: str = "SF32LB52"


class FirmwareUpdater:
    """固件更新器类"""

    def __init__(
        self,
        serial_assistant: SerialAssistant | None = None,
        sftool_path: str | None = None
    ) -> None:
        """初始化固件更新器

        Args:
            serial_assistant: 串口助手实例
            sftool_path: sftool.exe 的路径，默认自动查找
        """
        self.serial_assistant: SerialAssistant | None = serial_assistant
        self._sftool_path: str | None = sftool_path
        
        # 状态
        self._status: FirmwareUpdateStatus = FirmwareUpdateStatus.IDLE
        self._status_message: str = ""
        self._progress: int = 0  # 0-100
        
        # 临时目录
        self._temp_dir: str | None = None
        self._extracted_files: dict[str, str] = {}  # name -> path
        
        # 回调
        self.on_status_changed: Callable[[FirmwareUpdateStatus, str], None] | None = None
        self.on_progress_changed: Callable[[int], None] | None = None
        
        # 线程锁
        self._lock: threading.Lock = threading.Lock()
        self._update_thread: threading.Thread | None = None

    @property
    def status(self) -> FirmwareUpdateStatus:
        """获取当前状态"""
        return self._status

    @property
    def status_message(self) -> str:
        """获取状态消息"""
        return self._status_message

    @property
    def progress(self) -> int:
        """获取进度"""
        return self._progress

    @property
    def is_busy(self) -> bool:
        """是否正在执行操作"""
        return self._status in [
            FirmwareUpdateStatus.VALIDATING,
            FirmwareUpdateStatus.PREPARING,
            FirmwareUpdateStatus.FLASHING,
            FirmwareUpdateStatus.RECONNECTING,
        ]

    def set_serial_assistant(self, serial_assistant: SerialAssistant) -> None:
        """设置串口助手

        Args:
            serial_assistant: 串口助手实例
        """
        self.serial_assistant = serial_assistant

    def _set_status(
        self,
        status: FirmwareUpdateStatus,
        message: str = ""
    ) -> None:
        """设置状态并触发回调"""
        self._status = status
        self._status_message = message
        if self.on_status_changed:
            try:
                self.on_status_changed(status, message)
            except Exception:
                pass

    def _set_progress(self, progress: int) -> None:
        """设置进度并触发回调"""
        self._progress = max(0, min(100, progress))
        if self.on_progress_changed:
            try:
                self.on_progress_changed(self._progress)
            except Exception:
                pass

    def _find_sftool(self) -> str | None:
        """查找 sftool.exe

        Returns:
            sftool 路径，找不到返回 None
        """
        if self._sftool_path and os.path.isfile(self._sftool_path):
            return self._sftool_path

        # 可能的搜索路径
        search_paths: list[Path] = []

        # 1. 当前程序目录
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后
            app_dir = Path(sys.executable).parent
        else:
            # 开发环境
            app_dir = Path(__file__).parent

        search_paths.append(app_dir / "sftool.exe")
        search_paths.append(app_dir / "tools" / "sftool.exe")
        search_paths.append(app_dir / "bin" / "sftool.exe")

        # 2. PATH 环境变量
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for path_dir in path_dirs:
            search_paths.append(Path(path_dir) / "sftool.exe")

        # 搜索
        for path in search_paths:
            if path.is_file():
                self._sftool_path = str(path)
                return self._sftool_path

        return None

    def _cleanup_temp(self) -> None:
        """清理临时目录"""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
            except Exception:
                pass
        self._temp_dir = None
        self._extracted_files.clear()

    def validate_firmware_zip(self, zip_path: str) -> tuple[bool, str, list[str]]:
        """验证固件 ZIP 文件

        Args:
            zip_path: ZIP 文件路径

        Returns:
            (是否有效, 消息, 找到的文件列表)
        """
        self._set_status(FirmwareUpdateStatus.VALIDATING, "正在验证固件文件...")
        self._set_progress(0)
        
        # 清理之前的临时文件
        self._cleanup_temp()
        
        found_files: list[str] = []
        missing_files: list[str] = []

        try:
            # 检查文件是否存在
            if not os.path.isfile(zip_path):
                self._set_status(FirmwareUpdateStatus.INVALID, "文件不存在")
                return False, "文件不存在", []

            # 检查是否是 ZIP 文件
            if not zipfile.is_zipfile(zip_path):
                self._set_status(FirmwareUpdateStatus.INVALID, "不是有效的 ZIP 文件")
                return False, "不是有效的 ZIP 文件", []

            self._set_progress(20)

            # 创建临时目录
            self._temp_dir = tempfile.mkdtemp(prefix="superkey_fw_")

            # 解压 ZIP 文件
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(self._temp_dir)

            self._set_progress(50)

            # 在解压目录中查找所需的 bin 文件
            for fw_file in FIRMWARE_FILES:
                file_found = False
                
                # 递归搜索文件
                for root, dirs, files in os.walk(self._temp_dir):
                    if fw_file.name in files:
                        file_path = os.path.join(root, fw_file.name)
                        self._extracted_files[fw_file.name] = file_path
                        found_files.append(fw_file.name)
                        file_found = True
                        break
                
                if not file_found and fw_file.required:
                    missing_files.append(fw_file.name)

            self._set_progress(80)

            # 检查是否所有必需文件都找到了
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
        """构建烧录命令

        Args:
            port: COM 端口

        Returns:
            命令参数列表
        """
        sftool_path = self._find_sftool()
        if not sftool_path:
            raise FileNotFoundError("找不到 sftool.exe")

        cmd: list[str] = [
            sftool_path,
            "-c", SFTOOL_CHIP,
            "-p", port,
            "write_flash",
        ]

        # 按地址顺序添加文件
        for fw_file in FIRMWARE_FILES:
            if fw_file.name in self._extracted_files:
                file_path = self._extracted_files[fw_file.name]
                cmd.append(f"{file_path}@{fw_file.address}")

        return cmd

    def start_update(self) -> bool:
        """开始固件更新

        Returns:
            是否成功启动更新
        """
        with self._lock:
            if self.is_busy:
                return False

            if self._status != FirmwareUpdateStatus.VALID:
                self._set_status(
                    FirmwareUpdateStatus.FAILED,
                    "请先验证固件文件"
                )
                return False

            if not self._extracted_files:
                self._set_status(
                    FirmwareUpdateStatus.FAILED,
                    "没有可用的固件文件"
                )
                return False

            # 检查 sftool
            if not self._find_sftool():
                self._set_status(
                    FirmwareUpdateStatus.FAILED,
                    "找不到 sftool.exe，请将其放在程序目录下"
                )
                return False

            # 检查串口连接
            if not self.serial_assistant:
                self._set_status(
                    FirmwareUpdateStatus.FAILED,
                    "串口助手未初始化"
                )
                return False

            if not self.serial_assistant.is_connected:
                self._set_status(
                    FirmwareUpdateStatus.FAILED,
                    "请先连接设备"
                )
                return False

            # 启动更新线程
            self._update_thread = threading.Thread(
                target=self._update_worker,
                daemon=True
            )
            self._update_thread.start()
            return True

    def _update_worker(self) -> None:
        """更新工作线程"""
        port: str = ""
        
        try:
            self._set_status(FirmwareUpdateStatus.PREPARING, "准备烧录...")
            self._set_progress(0)

            # 获取当前连接的端口
            if self.serial_assistant and self.serial_assistant.is_connected:
                port = self.serial_assistant.config.get('port', '')
            
            if not port:
                self._set_status(FirmwareUpdateStatus.FAILED, "无法获取当前端口")
                return

            self._set_progress(10)

            # 暂时禁用自动重连
            auto_reconnect_was_enabled = False
            if self.serial_assistant:
                auto_reconnect_was_enabled = self.serial_assistant.is_auto_reconnect_enabled()
                self.serial_assistant.enable_auto_reconnect(False)

            # 断开串口连接
            self._set_status(FirmwareUpdateStatus.PREPARING, "断开设备连接...")
            if self.serial_assistant and self.serial_assistant.is_connected:
                self.serial_assistant.disconnect()
            
            # 等待端口释放
            time.sleep(0.5)
            self._set_progress(20)

            # 构建烧录命令
            self._set_status(FirmwareUpdateStatus.FLASHING, "正在烧录固件...")
            cmd = self._build_flash_command(port)

            # 执行烧录命令（静默模式）
            self._set_progress(30)
            
            # Windows 下隐藏控制台窗口
            startupinfo = None
            creationflags = 0
            if IS_WINDOWS:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=creationflags,
                text=True,
            )

            # 等待烧录完成，同时更新进度
            while process.poll() is None:
                # 模拟进度更新
                if self._progress < 90:
                    self._set_progress(self._progress + 2)
                time.sleep(0.5)

            stdout, stderr = process.communicate()
            
            self._set_progress(95)

            # 检查烧录结果
            if process.returncode != 0:
                error_msg = stderr.strip() if stderr else "未知错误"
                # 只显示简短的错误信息
                if len(error_msg) > 50:
                    error_msg = "烧录过程中出错"
                self._set_status(FirmwareUpdateStatus.FAILED, f"烧录失败: {error_msg}")
                
                # 恢复自动重连
                if self.serial_assistant and auto_reconnect_was_enabled:
                    self.serial_assistant.enable_auto_reconnect(True)
                return

            self._set_progress(100)
            self._set_status(FirmwareUpdateStatus.SUCCESS, "固件烧录完成！")

            # 等待 1 秒后重连
            self._set_status(FirmwareUpdateStatus.RECONNECTING, "正在重新连接设备...")
            time.sleep(1.0)

            # 恢复串口连接
            if self.serial_assistant:
                self.serial_assistant.configure(
                    port=port,
                    baudrate=1000000,
                    bytesize=8,
                    stopbits=1,
                    parity='N'
                )
                
                # 尝试重连
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
                
                # 恢复自动重连设置
                if auto_reconnect_was_enabled:
                    self.serial_assistant.enable_auto_reconnect(True)

        except FileNotFoundError as e:
            self._set_status(FirmwareUpdateStatus.FAILED, str(e))
        except Exception as e:
            self._set_status(FirmwareUpdateStatus.FAILED, f"更新失败: {str(e)}")
        finally:
            # 清理临时文件
            self._cleanup_temp()

    def cancel(self) -> None:
        """取消操作并清理"""
        self._cleanup_temp()
        self._set_status(FirmwareUpdateStatus.IDLE, "")
        self._set_progress(0)

    def get_status_display(self) -> tuple[str, str]:
        """获取用于显示的状态信息

        Returns:
            (状态文本, 颜色类型: "good"/"warn"/"bad"/"neutral")
        """
        status_map: dict[FirmwareUpdateStatus, tuple[str, str]] = {
            FirmwareUpdateStatus.IDLE: ("等待选择固件文件", "neutral"),
            FirmwareUpdateStatus.VALIDATING: ("正在验证...", "neutral"),
            FirmwareUpdateStatus.VALID: ("✓ 固件文件有效，可以开始更新", "good"),
            FirmwareUpdateStatus.INVALID: (f"✗ {self._status_message}", "bad"),
            FirmwareUpdateStatus.PREPARING: ("准备中...", "neutral"),
            FirmwareUpdateStatus.FLASHING: ("正在烧录固件...", "warn"),
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
    """获取全局固件更新器实例"""
    global _firmware_updater
    if _firmware_updater is None:
        _firmware_updater = FirmwareUpdater()
    return _firmware_updater


def set_firmware_updater_serial(serial_assistant: SerialAssistant) -> None:
    """设置固件更新器的串口助手"""
    updater = get_firmware_updater()
    updater.set_serial_assistant(serial_assistant)


# ============================================================================
# 固件版本检测器
# ============================================================================

class FirmwareVersionChecker:
    """固件版本检测器 - 用于查询设备固件版本"""

    # 版本响应的正则匹配: FW_VERSION:release1.1.2 或 FW_VERSION:dev1.0.0
    VERSION_PATTERN: re.Pattern[str] = re.compile(
        r'FW_VERSION:(release|dev)(\d+)\.(\d+)\.(\d+)'
    )

    def __init__(self, serial_assistant: SerialAssistant | None = None) -> None:
        """初始化版本检测器"""
        self.serial_assistant: SerialAssistant | None = serial_assistant
        self._version_string: str = ""  # 格式化后的版本字符串
        self._raw_version: str = ""     # 原始版本信息
        self._check_lock: threading.Lock = threading.Lock()
        self._response_event: threading.Event = threading.Event()
        self._response_buffer: str = ""

        # 版本检测完成回调
        self.on_version_checked: Callable[[str], None] | None = None

    @property
    def version_string(self) -> str:
        """获取格式化的版本字符串"""
        return self._version_string

    def set_serial_assistant(self, serial_assistant: SerialAssistant) -> None:
        """设置串口助手"""
        self.serial_assistant = serial_assistant

    def _format_version(self, version_type: str, major: str, minor: str, patch: str) -> str:
        """格式化版本字符串为 'release v1.1.2' 或 'dev v1.0.0' 格式"""
        return f"{version_type} v{major}.{minor}.{patch}"

    def check_version_async(self) -> None:
        """异步检测固件版本（在后台线程执行）"""
        thread = threading.Thread(target=self._check_version_worker, daemon=True)
        thread.start()

    def _check_version_worker(self) -> None:
        """版本检测工作线程"""
        with self._check_lock:
            version = self._do_check_version()
            self._version_string = version

            # 触发回调
            if self.on_version_checked:
                try:
                    self.on_version_checked(version)
                except Exception:
                    pass

    def _do_check_version(self) -> str:
        """执行版本检测，返回版本字符串或"未知" """
        if not self.serial_assistant or not self.serial_assistant.is_connected:
            return "未知"

        try:
            # 清空接收缓冲区
            self.serial_assistant.clear_rx_buffer()
            self._response_buffer = ""
            self._response_event.clear()

            # 保存原有的数据接收回调
            original_callback = self.serial_assistant.on_data_received

            # 设置临时回调来捕获响应
            def capture_response(data: bytes) -> None:
                try:
                    text = data.decode('utf-8', errors='ignore')
                    self._response_buffer += text
                    # 检查是否包含版本信息
                    if 'FW_VERSION:' in self._response_buffer:
                        self._response_event.set()
                except Exception:
                    pass
                # 调用原有回调
                if original_callback:
                    original_callback(data)

            self.serial_assistant.on_data_received = capture_response

            # 发送版本查询命令
            self.serial_assistant.send_data("sys_get version\n")

            # 等待响应（最多500ms）
            got_response = self._response_event.wait(timeout=0.5)

            # 恢复原有回调
            self.serial_assistant.on_data_received = original_callback

            if got_response:
                # 解析版本信息
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


# 全局版本检测器实例
_version_checker: FirmwareVersionChecker | None = None


def get_version_checker() -> FirmwareVersionChecker:
    """获取全局版本检测器实例"""
    global _version_checker
    if _version_checker is None:
        _version_checker = FirmwareVersionChecker()
    return _version_checker


def set_version_checker_serial(serial_assistant: SerialAssistant) -> None:
    """设置版本检测器的串口助手"""
    checker = get_version_checker()
    checker.set_serial_assistant(serial_assistant)