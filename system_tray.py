#!/usr/bin/env python3
"""
系统托盘模块
"""
from __future__ import annotations

import os
import platform
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

# 平台检测
SYSTEM: str = platform.system().lower()
IS_WINDOWS: bool = SYSTEM == 'windows'
IS_MACOS: bool = SYSTEM == 'darwin'
IS_LINUX: bool = SYSTEM == 'linux'

# 尝试导入托盘库
TRAY_AVAILABLE: bool = False
_pystray: Any | None = None
_Image: Any | None = None

try:
    import pystray as _pystray_module
    from PIL import Image as _Image_module
    _pystray = _pystray_module
    _Image = _Image_module
    TRAY_AVAILABLE = True
except ImportError:
    pass

# Linux额外检查: 需要显示服务器
if IS_LINUX and TRAY_AVAILABLE:
    display: str | None = (
        os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')
    )
    if not display:
        TRAY_AVAILABLE = False

# 类型别名 - 用于可选依赖
if TYPE_CHECKING:
    from PIL.Image import Image as PILImage
    from pystray import Icon, Menu, MenuItem
else:
    PILImage = Any
    Icon = Any
    Menu = Any
    MenuItem = Any


class SystemTray:
    """跨平台系统托盘管理器"""

    def __init__(
        self,
        app_name: str = "SuperKey",
        icon_path: str | None = None,
        on_show: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None
    ) -> None:
        self.app_name: str = app_name
        self.icon_path: str | None = icon_path
        self.on_show: Callable[[], None] | None = on_show
        self.on_quit: Callable[[], None] | None = on_quit

        self._icon: Icon | None = None
        self._running: bool = False

    @property
    def is_available(self) -> bool:
        return TRAY_AVAILABLE

    def _create_icon_image(self) -> PILImage | None:
        """创建托盘图标"""
        if not TRAY_AVAILABLE or _Image is None:
            return None

        # 尝试加载指定图标
        if self.icon_path and os.path.exists(self.icon_path):
            try:
                # type: ignore[no-any-return]
                return _Image.open(self.icon_path)
            except Exception:
                pass

        # 若找不到图标，则创建默认图标（蓝色方块）
        try:
            img: PILImage = _Image.new('RGBA', (64, 64), (59, 130, 246, 255))
            return img
        except Exception:
            return None

    def _create_menu(self) -> Menu | None:
        """创建托盘菜单"""
        if not TRAY_AVAILABLE or _pystray is None:
            return None

        # 根据平台使用不同语言
        if IS_MACOS:
            show_text: str = "Show Window"
            quit_text: str = "Quit"
        else:
            show_text = "显示窗口"
            quit_text = "退出"

        return _pystray.Menu(  # type: ignore[no-any-return]
            _pystray.MenuItem(show_text, self._on_show),
            _pystray.Menu.SEPARATOR,
            _pystray.MenuItem(quit_text, self._on_quit),
        )

    def _on_show(
        self,
        icon: Icon | None = None,
        item: MenuItem | None = None
    ) -> None:
        """显示窗口"""
        if self.on_show:
            self.on_show()

    def _on_quit(
        self,
        icon: Icon | None = None,
        item: MenuItem | None = None
    ) -> None:
        """退出应用"""
        self._running = False
        if self.on_quit:
            self.on_quit()
        self.stop()

    def start(self) -> bool:
        """启动系统托盘"""
        if not self.is_available or _pystray is None:
            return False

        if self._running:
            return True

        icon_image: PILImage | None = self._create_icon_image()
        if icon_image is None:
            return False

        self._running = True

        self._icon = _pystray.Icon(
            name=self.app_name,
            icon=icon_image,
            title=self.app_name,
            menu=self._create_menu()
        )

        # 在后台线程运行托盘
        thread: threading.Thread = threading.Thread(
            target=self._icon.run, daemon=True
        )
        thread.start()

        return True

    def stop(self) -> None:
        """停止系统托盘"""
        self._running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None

    def show_notification(self, title: str, message: str) -> None:
        """显示托盘通知"""
        if self._icon and hasattr(self._icon, 'notify'):
            try:
                self._icon.notify(message, title)
            except Exception:
                pass


class AutoStartManager:
    """跨平台开机自启动管理器"""

    APP_NAME: str = "SuperKeyHUB"
    # 公共接口

    @classmethod
    def is_supported(cls) -> bool:
        """检查当前平台是否支持自启动"""
        return IS_WINDOWS or IS_MACOS or IS_LINUX

    @classmethod
    def is_enabled(cls) -> bool:
        """检查是否已设置开机自启动"""
        if IS_WINDOWS:
            return cls._windows_is_enabled()
        elif IS_MACOS:
            return cls._macos_is_enabled()
        elif IS_LINUX:
            return cls._linux_is_enabled()
        return False

    @classmethod
    def enable(cls, exe_path: str | None = None) -> bool:
        """启用开机自启动"""
        if IS_WINDOWS:
            return cls._windows_enable(exe_path)
        elif IS_MACOS:
            return cls._macos_enable(exe_path)
        elif IS_LINUX:
            return cls._linux_enable(exe_path)
        return False

    @classmethod
    def disable(cls) -> bool:
        """禁用开机自启动"""
        if IS_WINDOWS:
            return cls._windows_disable()
        elif IS_MACOS:
            return cls._macos_disable()
        elif IS_LINUX:
            return cls._linux_disable()
        return False

    @classmethod
    def set_enabled(cls, enabled: bool) -> bool:
        """设置开机自启动状态"""
        if enabled:
            return cls.enable()
        else:
            return cls.disable()

    # Windows 实现 (任务计划程序 - 支持管理员权限自启动)

    TASK_NAME: str = "SuperKeyHUB_AutoStart"
    # 用于清理旧版
    REG_PATH: str = r"Software\Microsoft\Windows\CurrentVersion\Run"

    @classmethod
    def _windows_cleanup_old_registry(cls) -> None:
        """清理旧版本使用的注册表自启动项"""
        if not IS_WINDOWS:
            return
        try:
            import winreg as _winreg  # type: ignore[import]
            winreg: Any = _winreg
            key: Any = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                cls.REG_PATH,
                0,
                winreg.KEY_SET_VALUE
            )
            try:
                winreg.DeleteValue(key, cls.APP_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        except Exception:
            pass

    @classmethod
    def _windows_is_enabled(cls) -> bool:
        """检查任务计划程序中是否存在自启动任务"""
        try:
            import subprocess
            result: subprocess.CompletedProcess[str] = subprocess.run(
                ['schtasks', '/Query', '/TN', cls.TASK_NAME],
                capture_output=True, text=True,
                creationflags=0x08000000  # CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception:
            return False

    @classmethod
    def _windows_enable(cls, exe_path: str | None = None) -> bool:
        """使用任务计划程序创建管理员权限自启动任务"""
        # 先清理旧版注册表项
        cls._windows_cleanup_old_registry()

        script_path: str = ""
        if exe_path is None:
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                # 开发模式：使用 pythonw 避免控制台窗口
                python_exe: str = sys.executable.replace(
                    'python.exe', 'pythonw.exe'
                )
                if not os.path.exists(python_exe):
                    python_exe = sys.executable
                exe_path = python_exe
                script_path = os.path.abspath(sys.argv[0])

        try:
            import getpass  # noqa: F401
            import subprocess

            # 先删除可能存在的旧任务
            subprocess.run(
                ['schtasks', '/Delete', '/TN', cls.TASK_NAME, '/F'],
                capture_output=True, creationflags=0x08000000
            )

            # 构建命令
            command: str
            if getattr(sys, 'frozen', False):
                # 打包后的 exe
                command = f'"{exe_path}" --minimized'
            else:
                # 开发模式
                command = f'"{exe_path}" "{script_path}" --minimized'

            # 创建任务计划程序任务
            # /SC ONLOGON - 用户登录时运行
            # /RL HIGHEST - 使用最高权限运行（管理员）
            # /DELAY 0000:5 - 延迟5秒启动（等待系统完全加载）
            result: subprocess.CompletedProcess[str] = subprocess.run([
                'schtasks', '/Create',
                '/TN', cls.TASK_NAME,
                '/TR', command,
                '/SC', 'ONLOGON',
                '/RL', 'HIGHEST',
                '/DELAY', '0000:5',
                '/F'  # 强制覆盖
            ], capture_output=True, text=True, creationflags=0x08000000)

            return result.returncode == 0
        except Exception:
            return False

    @classmethod
    def _windows_disable(cls) -> bool:
        """删除任务计划程序中的自启动任务"""
        # 同时清理旧版注册表项
        cls._windows_cleanup_old_registry()

        try:
            import subprocess
            subprocess.run(
                ['schtasks', '/Delete', '/TN', cls.TASK_NAME, '/F'],
                capture_output=True, creationflags=0x08000000
            )
            return True  # 即使任务不存在也返回成功
        except Exception:
            return False

    # =========================================================================
    # macOS 实现 (LaunchAgents)
    # =========================================================================

    @classmethod
    def _macos_plist_path(cls) -> Path:
        """获取 LaunchAgent plist 文件路径"""
        return (Path.home() / "Library" / "LaunchAgents" /
                f"com.{cls.APP_NAME.lower()}.plist")

    @classmethod
    def _macos_is_enabled(cls) -> bool:
        """检查 macOS 是否已设置自启动"""
        return cls._macos_plist_path().exists()

    @classmethod
    def _macos_enable(cls, exe_path: str | None = None) -> bool:
        """启用 macOS 开机自启动"""
        script_path: str = ""
        if exe_path is None:
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = sys.executable
                script_path = os.path.abspath(sys.argv[0])

        plist_path: Path = cls._macos_plist_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)

        # 构建 plist 内容，添加 --minimized 参数实现静默启动
        program_args: str
        if getattr(sys, 'frozen', False):
            program_args = f"""    <array>
        <string>{exe_path}</string>
        <string>--minimized</string>
    </array>"""
        else:
            program_args = f"""    <array>
        <string>{exe_path}</string>
        <string>{script_path}</string>
        <string>--minimized</string>
    </array>"""

        app_label: str = cls.APP_NAME.lower()
        plist_content: str = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{app_label}</string>
    <key>ProgramArguments</key>
{program_args}
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""

        try:
            with open(plist_path, 'w') as f:
                f.write(plist_content)

            # 加载 LaunchAgent
            import subprocess
            subprocess.run(['launchctl', 'load', str(plist_path)], check=False)

            return True
        except Exception:
            return False

    @classmethod
    def _macos_disable(cls) -> bool:
        """禁用 macOS 开机自启动"""
        plist_path: Path = cls._macos_plist_path()

        try:
            if plist_path.exists():
                # 卸载 LaunchAgent
                import subprocess
                subprocess.run(
                    ['launchctl', 'unload', str(plist_path)],
                    check=False
                )

                plist_path.unlink()
            return True
        except Exception:
            return False

    # Linux 实现 (XDG autostart)
    @classmethod
    def _linux_desktop_path(cls) -> Path:
        """获取 XDG autostart desktop 文件路径"""
        config_home: Union[str, Path] = os.environ.get(
            'XDG_CONFIG_HOME',
            Path.home() / '.config'
        )
        return (Path(config_home) / "autostart" /
                f"{cls.APP_NAME.lower()}.desktop")

    @classmethod
    def _linux_is_enabled(cls) -> bool:
        """检查 Linux 是否已设置自启动"""
        return cls._linux_desktop_path().exists()

    @classmethod
    def _linux_enable(cls, exe_path: str | None = None) -> bool:
        """启用 Linux 开机自启动"""
        if exe_path is None:
            if getattr(sys, 'frozen', False):
                exe_path = f"{sys.executable} --minimized"
            else:
                script: str = os.path.abspath(sys.argv[0])
                exe_path = f"{sys.executable} {script} --minimized"
        else:
            # 如果传入了自定义路径，也添加 --minimized 参数
            exe_path = f"{exe_path} --minimized"

        desktop_path: Path = cls._linux_desktop_path()
        desktop_path.parent.mkdir(parents=True, exist_ok=True)

        desktop_content: str = f"""[Desktop Entry]
Type=Application
Name={cls.APP_NAME}
Exec={exe_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=SuperKey Hardware Monitor
"""

        try:
            with open(desktop_path, 'w') as f:
                f.write(desktop_content)

            # 设置可执行权限
            os.chmod(desktop_path, 0o755)

            return True
        except Exception:
            return False

    @classmethod
    def _linux_disable(cls) -> bool:
        """禁用 Linux 开机自启动"""
        desktop_path: Path = cls._linux_desktop_path()

        try:
            if desktop_path.exists():
                desktop_path.unlink()
            return True
        except Exception:
            return False


def is_tray_available() -> bool:
    """检查系统托盘是否可用"""
    return TRAY_AVAILABLE


if __name__ == "__main__":
    print(f"平台: {SYSTEM}")
    print(f"托盘可用: {is_tray_available()}")
    print(f"自启动支持: {AutoStartManager.is_supported()}")
    print(f"自启动已启用: {AutoStartManager.is_enabled()}")
    if IS_WINDOWS:
        print("自启动方式: 任务计划程序 (管理员权限)")
        print(f"任务名称: {AutoStartManager.TASK_NAME}")
