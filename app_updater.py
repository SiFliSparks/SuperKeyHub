#!/usr/bin/env python3
"""
应用自更新模块

"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

# 平台检测
SYSTEM: str = platform.system().lower()
IS_WINDOWS: bool = SYSTEM == 'windows'
IS_MACOS: bool = SYSTEM == 'darwin'

# 版本检查URL
VERSION_CHECK_URL: str = "https://sparks.sifli.com/projects/superkey/download/root_artifacts/hub_verid.json"

# 下载链接模板
DOWNLOAD_URL_WINDOWS: str = "https://sparks.sifli.com/projects/superkey/download/software/v{version}/version_artifacts/SuperKeyHUB-{version}-Setup.exe"
DOWNLOAD_URL_MACOS: str = "https://sparks.sifli.com/projects/superkey/download/software/v{version}/version_artifacts/SuperKeyHUB-{version}-macOS.dmg"


class AppUpdateStatus(Enum):
    """应用更新状态"""
    IDLE = "idle"                     # 空闲状态
    CHECKING = "checking"             # 正在检查更新
    UP_TO_DATE = "up_to_date"         # 已是最新版本
    UPDATE_AVAILABLE = "available"    # 有新版本可用
    DOWNLOADING = "downloading"       # 正在下载
    DOWNLOAD_COMPLETE = "complete"    # 下载完成
    INSTALLING = "installing"         # 正在安装
    CHECK_FAILED = "check_failed"     # 检查失败
    DOWNLOAD_FAILED = "download_failed"  # 下载失败


@dataclass
class VersionInfo:
    """版本信息"""
    version: str
    firmware_compat: str
    build_time: str


class AppUpdater:
    """应用自更新器"""
    
    def __init__(self, current_version: str) -> None:
        self.current_version: str = current_version
        self.remote_version: Optional[VersionInfo] = None
        self.status: AppUpdateStatus = AppUpdateStatus.IDLE
        self.progress: int = 0  # 下载进度 0-100
        self.error_message: str = ""
        self.download_path: Optional[Path] = None
        
        # 回调函数
        self.on_status_changed: Optional[Callable[[AppUpdateStatus, str], None]] = None
        self.on_progress_changed: Optional[Callable[[int], None]] = None
        
        # 线程锁
        self._lock = threading.Lock()
        self._download_thread: Optional[threading.Thread] = None
        self._check_thread: Optional[threading.Thread] = None
    
    def _set_status(self, status: AppUpdateStatus, message: str = "") -> None:
        """设置状态并触发回调"""
        with self._lock:
            self.status = status
            self.error_message = message
        if self.on_status_changed:
            self.on_status_changed(status, message)
    
    def _set_progress(self, progress: int) -> None:
        """设置进度并触发回调"""
        with self._lock:
            self.progress = progress
        if self.on_progress_changed:
            self.on_progress_changed(progress)
    
    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        """
        比较版本号
        
        返回:
            1: v1 > v2
            0: v1 == v2
            -1: v1 < v2
        """
        def parse_version(v: str) -> list[int]:
            # 移除可能的'v'前缀
            v = v.lstrip('v').lstrip('V')
            parts = v.split('.')
            result = []
            for p in parts:
                # 只取数字部分
                num_str = ''.join(c for c in p if c.isdigit())
                result.append(int(num_str) if num_str else 0)
            return result
        
        v1_parts = parse_version(v1)
        v2_parts = parse_version(v2)
        
        # 补齐长度
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))
        
        for i in range(max_len):
            if v1_parts[i] > v2_parts[i]:
                return 1
            elif v1_parts[i] < v2_parts[i]:
                return -1
        return 0
    
    def check_update(self) -> None:
        """检查更新（异步）"""
        if self._check_thread and self._check_thread.is_alive():
            return
        
        self._check_thread = threading.Thread(target=self._check_update_thread, daemon=True)
        self._check_thread.start()
    
    def _check_update_thread(self) -> None:
        """检查更新线程"""
        self._set_status(AppUpdateStatus.CHECKING)
        
        try:
            # 创建请求
            req = urllib.request.Request(
                VERSION_CHECK_URL,
                headers={'User-Agent': 'SuperKeyHUB Updater'}
            )
            
            # 设置超时
            with urllib.request.urlopen(req, timeout=15) as response:
                data = response.read().decode('utf-8')
            
            # 解析JSON
            version_data = json.loads(data)
            
            self.remote_version = VersionInfo(
                version=version_data.get('version', ''),
                firmware_compat=version_data.get('firmware_compat', ''),
                build_time=version_data.get('build_time', '')
            )
            
            if not self.remote_version.version:
                self._set_status(AppUpdateStatus.CHECK_FAILED, "版本信息无效")
                return
            
            # 比较版本
            cmp_result = self.compare_versions(
                self.remote_version.version,
                self.current_version
            )
            
            if cmp_result > 0:
                # 有新版本
                self._set_status(
                    AppUpdateStatus.UPDATE_AVAILABLE,
                    f"发现新版本 v{self.remote_version.version}"
                )
            else:
                # 已是最新
                self._set_status(
                    AppUpdateStatus.UP_TO_DATE,
                    f"当前已是最新版本 v{self.current_version}"
                )
                
        except urllib.error.URLError as e:
            self._set_status(AppUpdateStatus.CHECK_FAILED, f"网络错误: {str(e.reason)}")
        except json.JSONDecodeError:
            self._set_status(AppUpdateStatus.CHECK_FAILED, "版本信息格式错误")
        except TimeoutError:
            self._set_status(AppUpdateStatus.CHECK_FAILED, "检查更新超时")
        except Exception as e:
            self._set_status(AppUpdateStatus.CHECK_FAILED, f"检查失败: {str(e)}")
    
    def get_download_url(self) -> Optional[str]:
        """获取当前平台的下载链接"""
        if not self.remote_version:
            return None
        
        version = self.remote_version.version
        
        if IS_WINDOWS:
            return DOWNLOAD_URL_WINDOWS.format(version=version)
        elif IS_MACOS:
            return DOWNLOAD_URL_MACOS.format(version=version)
        else:
            # Linux 暂不支持
            return None
    
    def download_and_install(self) -> None:
        """下载并安装更新（异步）"""
        if self._download_thread and self._download_thread.is_alive():
            return
        
        if self.status != AppUpdateStatus.UPDATE_AVAILABLE:
            return
        
        self._download_thread = threading.Thread(
            target=self._download_and_install_thread,
            daemon=True
        )
        self._download_thread.start()
    
    def _download_and_install_thread(self) -> None:
        """下载并安装线程"""
        url = self.get_download_url()
        if not url:
            self._set_status(AppUpdateStatus.DOWNLOAD_FAILED, "当前平台不支持自动更新")
            return
        
        self._set_status(AppUpdateStatus.DOWNLOADING)
        self._set_progress(0)
        
        try:
            # 确定文件名
            if IS_WINDOWS:
                filename = f"SuperKeyHUB-{self.remote_version.version}-Setup.exe"
            else:
                filename = f"SuperKeyHUB-{self.remote_version.version}-macOS.dmg"
            
            # 下载到临时目录
            temp_dir = tempfile.gettempdir()
            download_path = Path(temp_dir) / filename
            
            # 创建请求
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'SuperKeyHUB Updater'}
            )
            
            # 下载文件
            with urllib.request.urlopen(req, timeout=300) as response:
                total_size = response.getheader('Content-Length')
                total_size = int(total_size) if total_size else 0
                
                downloaded = 0
                block_size = 8192
                
                with open(download_path, 'wb') as f:
                    while True:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self._set_progress(progress)
            
            self.download_path = download_path
            self._set_progress(100)
            self._set_status(AppUpdateStatus.DOWNLOAD_COMPLETE, "下载完成，准备安装...")
            
            # 短暂延迟后开始安装
            time.sleep(1)
            self._run_installer()
            
        except urllib.error.URLError as e:
            self._set_status(AppUpdateStatus.DOWNLOAD_FAILED, f"下载失败: {str(e.reason)}")
        except TimeoutError:
            self._set_status(AppUpdateStatus.DOWNLOAD_FAILED, "下载超时")
        except Exception as e:
            self._set_status(AppUpdateStatus.DOWNLOAD_FAILED, f"下载失败: {str(e)}")
    
    def _run_installer(self) -> None:
        """运行安装程序并退出应用"""
        if not self.download_path or not self.download_path.exists():
            self._set_status(AppUpdateStatus.DOWNLOAD_FAILED, "安装包不存在")
            return
        
        self._set_status(AppUpdateStatus.INSTALLING, "正在启动安装程序...")
        
        try:
            if IS_WINDOWS:
                # Windows: 使用 cmd /c start 启动安装程序，然后退出
                # 添加延迟确保主程序有时间退出
                installer_path = str(self.download_path)
                
                # 创建批处理文件来延迟启动安装程序
                batch_content = f'''@echo off
timeout /t 2 /nobreak > nul
start "" "{installer_path}"
'''
                batch_path = Path(tempfile.gettempdir()) / "superkey_update.bat"
                with open(batch_path, 'w') as f:
                    f.write(batch_content)
                
                # 启动批处理（分离进程）
                subprocess.Popen(
                    ['cmd', '/c', str(batch_path)],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                    close_fds=True
                )
                
            elif IS_MACOS:
                # macOS: 打开DMG文件
                installer_path = str(self.download_path)
                
                # 创建脚本来延迟打开DMG
                script_content = f'''#!/bin/bash
sleep 2
open "{installer_path}"
'''
                script_path = Path(tempfile.gettempdir()) / "superkey_update.sh"
                with open(script_path, 'w') as f:
                    f.write(script_content)
                os.chmod(script_path, 0o755)
                
                # 启动脚本（分离进程）
                subprocess.Popen(
                    ['/bin/bash', str(script_path)],
                    start_new_session=True,
                    close_fds=True
                )
            
            # 退出当前应用
            time.sleep(0.5)
            os._exit(0)
            
        except Exception as e:
            self._set_status(AppUpdateStatus.DOWNLOAD_FAILED, f"启动安装程序失败: {str(e)}")
    
    def get_status_display(self) -> tuple[str, str]:
        """
        获取状态显示文本和颜色类型
        
        返回: (状态文本, 颜色类型)
        颜色类型: "good", "warn", "bad", "neutral", "accent"
        """
        status_map = {
            AppUpdateStatus.IDLE: ("点击检查更新", "neutral"),
            AppUpdateStatus.CHECKING: ("正在检查更新...", "accent"),
            AppUpdateStatus.UP_TO_DATE: (f"当前已是最新版本 v{self.current_version}", "good"),
            AppUpdateStatus.UPDATE_AVAILABLE: (
                f"发现新版本 v{self.remote_version.version if self.remote_version else ''}",
                "warn"
            ),
            AppUpdateStatus.DOWNLOADING: (f"正在下载... {self.progress}%", "accent"),
            AppUpdateStatus.DOWNLOAD_COMPLETE: ("下载完成，准备安装...", "good"),
            AppUpdateStatus.INSTALLING: ("正在启动安装程序...", "accent"),
            AppUpdateStatus.CHECK_FAILED: (f"检查失败: {self.error_message}", "bad"),
            AppUpdateStatus.DOWNLOAD_FAILED: (f"下载失败: {self.error_message}", "bad"),
        }
        
        return status_map.get(self.status, ("未知状态", "neutral"))
    
    @property
    def is_busy(self) -> bool:
        """是否正忙（检查中或下载中）"""
        return self.status in (
            AppUpdateStatus.CHECKING,
            AppUpdateStatus.DOWNLOADING,
            AppUpdateStatus.INSTALLING
        )
    
    @property
    def can_download(self) -> bool:
        """是否可以下载"""
        return self.status == AppUpdateStatus.UPDATE_AVAILABLE


# 单例模式
_app_updater: Optional[AppUpdater] = None


def get_app_updater(current_version: str = "") -> AppUpdater:
    """获取应用更新器单例"""
    global _app_updater
    if _app_updater is None:
        if not current_version:
            raise ValueError("首次调用必须提供当前版本号")
        _app_updater = AppUpdater(current_version)
    return _app_updater
