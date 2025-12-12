#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os
import platform
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

import flet as ft

from config_manager import get_config_manager
from custom_key_manager import (
    PRESET_SHORTCUTS,
    flet_key_to_hid,
    get_custom_key_manager,
    get_key_display_name,
    get_modifier_options,
)
from finsh_data_sender import FinshDataSender
from hw_monitor import (
    HardwareMonitor,
    bytes2human,
    mhz_str,
    pct_str,
    temp_str,
    watt_str,
)
from serial_assistant import SerialAssistant
from system_tray import AutoStartManager, SystemTray, is_tray_available
from weather_api import QWeatherAPI as WeatherAPI
from led_controller import (
    LedController,
    LedEffect,
    LED_COLOR_PRESETS,
    LED_EFFECT_NAMES,
    get_led_controller,
)
from firmware_updater import (
    FirmwareUpdater,
    FirmwareUpdateStatus,
    get_firmware_updater,
    set_firmware_updater_serial,
    get_version_checker,
    set_version_checker_serial,
)

# ============================================================================
# Type Definitions
# ============================================================================
class DiskData(TypedDict):
    model: str
    used: int
    size: int
    rps: int | None
    wps: int | None


class WeatherForecast(TypedDict, total=False):
    date: str
    text_day: str
    text_night: str
    temp_max: int
    temp_min: int
    wind_dir_day: str
    wind_scale_day: str
    humidity: int
    uv_index: int


class WeatherData(TypedDict, total=False):
    weather_city: str
    weather_temp: float
    weather_feels_like: float
    weather_desc: str
    weather_quality: str
    weather_comfort_index: str
    weather_humidity: int
    weather_pressure: float
    weather_visibility: float
    weather_precipitation: float
    weather_wind_display: str
    weather_cloud_cover: int
    weather_dew_point: float
    weather_source: str
    weather_obs_time: str
    weather_forecast: list[WeatherForecast]


class ColorDict(TypedDict):
    TEXT_PRIMARY: str
    TEXT_SECONDARY: str
    TEXT_TERTIARY: str
    TEXT_INVERSE: str
    BG_PRIMARY: str
    BG_SECONDARY: str
    BG_CARD: str
    BG_SHELL: str
    BG_OVERLAY: str
    BORDER: str
    DIVIDER: str
    ACCENT: str
    GOOD: str
    WARN: str
    BAD: str
    CARD_BG_ALPHA: str
    BAR_BG_ALPHA: str
    SIDEBAR_BG: str
    SIDEBAR_HOVER: str
    SIDEBAR_ACTIVE: str


# ============================================================================
# Argument Parsing
# ============================================================================
def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='SuperKey Hardware Monitor')
    parser.add_argument(
        '--minimized', '-m', action='store_true',
        help='启动时最小化到系统托盘（静默启动）'
    )
    args, _ = parser.parse_known_args()
    return args


STARTUP_ARGS: argparse.Namespace = parse_args()
START_MINIMIZED: bool = STARTUP_ARGS.minimized


# ============================================================================
# 平台检测
# ============================================================================
SYSTEM: str = platform.system().lower()
IS_WINDOWS: bool = SYSTEM == 'windows'
IS_MACOS: bool = SYSTEM == 'darwin'
IS_LINUX: bool = SYSTEM == 'linux'

# 条件导入，仅Windows（用于主题检测）
if IS_WINDOWS:
    import winreg

# ============================================================================
# Version Configuration
# ============================================================================
APP_VERSION: str = "1.7.0"
FIRMWARE_COMPAT: str = "1.2"
APP_NAME: str = "SuperKeyHUB"
# ============================================================================


def detect_system_theme() -> str:
    """跨平台检测系统主题"""
    if IS_WINDOWS:
        try:
            reg_path = (
                r"Software\Microsoft\Windows\CurrentVersion"
                r"\Themes\Personalize"
            )
            registry_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                reg_path)
            value, _ = winreg.QueryValueEx(registry_key, "AppsUseLightTheme")
            winreg.CloseKey(registry_key)
            return "light" if value else "dark"
        except Exception:
            return "dark"
    elif IS_MACOS:
        try:
            import subprocess
            result = subprocess.run(
                ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                capture_output=True, text=True
            )
            return "dark" if "Dark" in result.stdout else "light"
        except Exception:
            return "light"
    elif IS_LINUX:
        try:
            gtk_theme = os.environ.get('GTK_THEME', '').lower()
            if 'dark' in gtk_theme:
                return "dark"
            import subprocess
            gsettings_cmd = [
                'gsettings', 'get',
                'org.gnome.desktop.interface', 'gtk-theme'
            ]
            result = subprocess.run(
                gsettings_cmd,
                capture_output=True, text=True
            )
            if 'dark' in result.stdout.lower():
                return "dark"
        except Exception:
            pass
        return "dark"
    return "dark"


class ThemeColors:
    def __init__(self) -> None:
        self.current_theme: str = detect_system_theme()
        self.colors: ColorDict = self._get_colors()

    def _get_colors(self) -> ColorDict:
        if self.current_theme == "light":
            return {
                "TEXT_PRIMARY": "#0F172A",
                "TEXT_SECONDARY": "#475569",
                "TEXT_TERTIARY": "#64748B",
                "TEXT_INVERSE": "#FFFFFF",
                "BG_PRIMARY": "#FFFFFF",
                "BG_SECONDARY": "#F9FAFB",
                "BG_CARD": "#FFFFFF",
                "BG_SHELL": "#F3F4F6",
                "BG_OVERLAY": "#E5E7EB",
                "BORDER": "#E5E7EB",
                "DIVIDER": "#E5E7EB",
                "ACCENT": "#9BE0E0",
                "GOOD": "#059669",
                "WARN": "#D97706",
                "BAD": "#DC2626",
                "CARD_BG_ALPHA": "#EEFFFFFF",
                "BAR_BG_ALPHA": "#CDFFFFFF",
                "SIDEBAR_BG": "#F8FAFC",
                "SIDEBAR_HOVER": "#E2E8F0",
                "SIDEBAR_ACTIVE": "#E0E7FF",
            }
        else:
            return {
                "TEXT_PRIMARY": "#F9FAFB",
                "TEXT_SECONDARY": "#D1D5DB",
                "TEXT_TERTIARY": "#9CA3AF",
                "TEXT_INVERSE": "#1F2937",
                "BG_PRIMARY": "#1C2841",
                "BG_SECONDARY": "#313438",
                "BG_CARD": "#1F2937",
                "BG_SHELL": "#34363A",
                "BG_OVERLAY": "#374151",
                "BORDER": "#374151",
                "DIVIDER": "#374151",
                "ACCENT": "#3B82F6",
                "GOOD": "#10B981",
                "WARN": "#F59E0B",
                "BAD": "#EF4444",
                "CARD_BG_ALPHA": "#1A1F2937",
                "BAR_BG_ALPHA": "#331F2937",
                "SIDEBAR_BG": "#1E293B",
                "SIDEBAR_HOVER": "#334155",
                "SIDEBAR_ACTIVE": "#1E40AF",
            }

    def refresh_theme(self) -> bool:
        new_theme: str = detect_system_theme()
        if new_theme != self.current_theme:
            self.current_theme = new_theme
            self.colors = self._get_colors()
            return True
        return False

    def get(self, key: str) -> str:
        return self.colors.get(key, "#000000")


def color_by_temp(t: float | None, theme: ThemeColors) -> str:
    if t is None:
        return theme.get("TEXT_TERTIARY")
    elif t <= 60:
        return theme.get("GOOD")
    elif t <= 80:
        return theme.get("WARN")
    else:
        return theme.get("BAD")


def color_by_load(p: float | None, theme: ThemeColors) -> str:
    if p is None:
        return theme.get("TEXT_TERTIARY")
    elif p < 50:
        return theme.get("GOOD")
    elif p < 85:
        return theme.get("WARN")
    else:
        return theme.get("BAD")


def get_resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径，支持 PyInstaller 打包环境"""
    base_path: str
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_icon_path() -> str | None:
    """根据平台返回合适的图标路径"""
    candidates: list[str]
    if IS_WINDOWS:
        candidates = ["assets/app.ico", "app.ico"]
    elif IS_MACOS:
        candidates = [
            "assets/app.icns",
            "app.icns",
            "assets/app.png",
            "app.png"
        ]
    else:
        candidates = ["assets/app.png", "app.png"]

    for path in candidates:
        resource_path: str = get_resource_path(path)
        if os.path.exists(resource_path):
            return resource_path

    for path in candidates:
        if os.path.exists(path):
            return path

    return None


# 导航项组件
class NavigationItem:
    def __init__(
            self,
            icon: str,
            title: str,
            view_name: str,
            theme: ThemeColors,
            on_click_handler: Callable[[str], None] | None,
            icon_size: int = 24,
            is_separator: bool = False
    ) -> None:
        self.icon: str = icon
        self.title: str = title
        self.view_name: str = view_name
        self.theme: ThemeColors = theme
        self.on_click_handler: Callable[[str], None] | None = (
            on_click_handler
        )
        self.icon_size: int = icon_size
        self.is_separator: bool = is_separator
        self.is_active: bool = False

        self.icon_btn: ft.IconButton
        self.container: ft.Container
        self.divider: ft.Divider

        if not is_separator:
            self.icon_btn = ft.IconButton(
                icon=icon,
                icon_color=theme.get("TEXT_SECONDARY"),
                icon_size=icon_size,
                tooltip=title,
                on_click=lambda e: (
                    self.on_click_handler(view_name)
                    if self.on_click_handler else None
                )
            )

            # 创建 container，只包含图标按钮
            self.container = ft.Container(
                content=self.icon_btn,
                padding=ft.padding.symmetric(horizontal=4, vertical=4),
                border_radius=8,
                ink=True,
                on_click=lambda e: (
                    self.on_click_handler(view_name)
                    if self.on_click_handler else None
                )
            )
        else:
            self.divider = ft.Divider(
                opacity=0.2,
                thickness=1,
                color=theme.get("DIVIDER")
            )

    def set_expanded(self, expanded: bool) -> None:
        pass  # 不再需要展开/收起文字

    def set_active(self, active: bool) -> None:
        """设置激活状态"""
        if not self.is_separator:
            self.is_active = active
            if active:
                self.icon_btn.icon_color = self.theme.get("ACCENT")
                self.container.bgcolor = self.theme.get("SIDEBAR_ACTIVE")
            else:
                self.icon_btn.icon_color = self.theme.get("TEXT_SECONDARY")
                self.container.bgcolor = None

    def update_theme_colors(self, theme: ThemeColors) -> None:
        self.theme = theme
        if not self.is_separator:
            if self.is_active:
                self.icon_btn.icon_color = theme.get("ACCENT")
                self.container.bgcolor = theme.get("SIDEBAR_ACTIVE")
            else:
                self.icon_btn.icon_color = theme.get("TEXT_SECONDARY")
                self.container.bgcolor = None
        else:
            self.divider.color = theme.get("DIVIDER")


# 主应用
async def main(page: ft.Page) -> None:
    # 设置窗口图标（跨平台）
    icon_path: str | None = get_icon_path()
    if icon_path:
        page.window_icon = icon_path

    theme: ThemeColors = ThemeColors()

    # ==================== 跨平台字体设置 ====================
    if IS_WINDOWS:
        page.fonts = {
            "default": "Microsoft YaHei",
        }
        page.theme = ft.Theme(font_family="Microsoft YaHei")
    elif IS_MACOS:
        page.fonts = {
            "default": "PingFang SC",
        }
        page.theme = ft.Theme(font_family="PingFang SC")
    else:  # Linux
        page.fonts = {
            "default": "Noto Sans CJK SC",
        }
        page.theme = ft.Theme(font_family="Noto Sans CJK SC")

    # 跨平台窗口配置
    if IS_WINDOWS:
        page.window.title_bar_hidden = True
        page.window.frameless = False
        page.window.bgcolor = "#00000000"
        page.bgcolor = "#00000000"
    elif IS_MACOS:
        page.window.title_bar_hidden = False
        page.window.title_bar_buttons_hidden = False
        page.window.frameless = False
        page.bgcolor = ft.colors.TRANSPARENT
    else:
        page.window.title_bar_hidden = False
        page.window.frameless = False
        page.bgcolor = ft.colors.TRANSPARENT

    # 固定窗口大小
    page.window.resizable = False      # 禁止调整大小
    page.window.maximizable = False    # 禁止最大化
    page.window.minimizable = True     # 保留最小化

    page.window.width = 1024           # 固定宽度
    page.window.height = 640           # 固定高度

    page.window.shadow = True
    page.padding = 0
    page.spacing = 0
    page.title = f"Build v{APP_VERSION} - {APP_NAME}"

    page.adaptive = True
    page.scroll = None

    # ==================== 启动画面 ====================
    splash_logo: ft.Image = ft.Image(
        src="logo_484x74.png",
        width=300,
        fit=ft.ImageFit.CONTAIN,
    )
    splash_progress: ft.ProgressRing = ft.ProgressRing(
        width=24,
        height=24,
        stroke_width=2,
        color=theme.get("ACCENT"),
    )
    splash_status: ft.Text = ft.Text(
        "正在初始化...",
        size=13,
        color=theme.get("TEXT_SECONDARY"),
    )
    splash_screen: ft.Container = ft.Container(
        content=ft.Column(
            [
                splash_logo,
                ft.Container(height=30),
                ft.Row(
                    [splash_progress, splash_status],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        expand=True,
        bgcolor=theme.get("BG_PRIMARY"),
        alignment=ft.alignment.center,
    )

    # 显示启动画面
    page.add(splash_screen)
    page.update()

    # ==================== 后台初始化 ====================
    hw_monitor: HardwareMonitor = HardwareMonitor(lazy_init=True)
    hw_init_done: dict[str, bool] = {"ready": False}

    def init_hw_monitor_background() -> None:
        """后台初始化硬件监控器"""
        hw_monitor._do_init()
        hw_init_done["ready"] = True

    # 启动后台初始化线程
    import threading
    hw_init_thread = threading.Thread(
        target=init_hw_monitor_background, daemon=True)
    hw_init_thread.start()

    config_mgr = get_config_manager()
    weather_cfg: dict[str, Any] = config_mgr.get_weather_config()
    weather_api: WeatherAPI = WeatherAPI(
        api_key=weather_cfg.get('api_key', ''),
        default_city=weather_cfg.get('default_city', '北京'),
        api_host=weather_cfg.get('api_host', ''),
        use_jwt=weather_cfg.get('use_jwt', False)
    )
    serial_assistant: SerialAssistant = SerialAssistant()
    led_controller: LedController = get_led_controller()
    led_controller.set_serial_assistant(serial_assistant)
    finsh_sender: FinshDataSender = FinshDataSender(
        serial_assistant=serial_assistant,
        weather_api=weather_api,
        hardware_monitor=hw_monitor
    )

    # ==================== 系统托盘初始化 ====================
    system_tray: SystemTray | None = None
    app_state: dict[str, bool] = {"force_quit": False}

    def show_window() -> None:
        """显示窗口"""
        page.window.visible = True
        page.window.focused = True
        try:
            page.update()
        except BaseException:
            pass

    def cleanup_and_exit() -> None:
        """清理资源"""
        try:
            if finsh_sender.enabled:
                finsh_sender.stop()
            if serial_assistant.is_connected:
                serial_assistant.disconnect()
        except BaseException:
            pass
        if system_tray:
            system_tray.stop()

    def quit_app() -> None:
        """完全退出应用"""
        app_state["force_quit"] = True
        cleanup_and_exit()
        page.window.destroy()

    def on_window_event(e: ft.ControlEvent) -> None:
        """处理窗口事件"""
        if e.data == "close":
            if app_state["force_quit"]:
                return

            tray_available: bool = is_tray_available()
            should_minimize: bool = config_mgr.should_minimize_to_tray()
            if system_tray and tray_available and should_minimize:
                page.window.visible = False
                page.update()
                if IS_MACOS:
                    system_tray.show_notification(
                        APP_NAME, "App minimized to system tray")
                else:
                    system_tray.show_notification(
                        APP_NAME, "程序已最小化到系统托盘")
            else:
                quit_app()

    page.window.prevent_close = True
    page.window.on_event = on_window_event

    if is_tray_available():
        tray_icon_path: str | None = get_icon_path()

        system_tray = SystemTray(
            app_name=f"{APP_NAME} v{APP_VERSION}",
            icon_path=tray_icon_path,
            on_show=show_window,
            on_quit=quit_app
        )
        system_tray.start()

    if START_MINIMIZED and system_tray and is_tray_available():
        page.window.visible = False
        page.update()

    sidebar_expanded: dict[str, bool] = {"value": False}

    def do_minimize(e: ft.ControlEvent) -> None:
        page.window.minimized = True
        page.update()

    def do_max_restore(e: ft.ControlEvent) -> None:
        page.window.maximized = not page.window.maximized
        page.update()

    def do_close(e: ft.ControlEvent) -> None:
        """关闭按钮 - 触发窗口关闭事件"""
        tray_available: bool = is_tray_available()
        should_minimize: bool = config_mgr.should_minimize_to_tray()
        if system_tray and tray_available and should_minimize:
            page.window.visible = False
            page.update()
            if IS_MACOS:
                system_tray.show_notification(
                    APP_NAME, "App minimized to system tray")
            else:
                system_tray.show_notification(
                    APP_NAME, "程序已最小化到系统托盘")
        else:
            quit_app()

    title_buttons: ft.Row = ft.Row(
        [
            ft.IconButton(
                icon="remove",
                icon_color=theme.get("TEXT_SECONDARY"),
                tooltip="最小化",
                on_click=do_minimize),
            ft.IconButton(
                icon="crop_square",
                icon_color=theme.get("TEXT_SECONDARY"),
                tooltip="最大化/还原",
                on_click=do_max_restore),
            ft.IconButton(
                icon="close",
                icon_color=theme.get("TEXT_SECONDARY"),
                tooltip="关闭",
                on_click=do_close),
        ],
        spacing=0,
        visible=IS_WINDOWS,
    )

    logo_img: ft.Image = ft.Image(
        src="logo_484x74.png",
        height=28,
        width=180,
        fit=ft.ImageFit.CONTAIN)

    title_row: ft.Container = ft.Container(
        content=ft.Row([
            ft.Container(width=12),
            ft.Row([
                logo_img,
                ft.Text(
                    f"{APP_NAME} v{APP_VERSION}",
                    color=theme.get("TEXT_SECONDARY"),
                    size=14),
            ], spacing=10),
            ft.Container(expand=True),
            title_buttons
        ],
            alignment="spaceBetween",
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0),
        height=44,
        padding=0,
        margin=0,
        bgcolor="transparent"
    )

    title_bar: ft.Control
    if IS_WINDOWS:
        title_bar = ft.WindowDragArea(
            title_row,
            maximizable=True,
        )
    else:
        title_bar = title_row

    content_host: ft.Container = ft.Container(
        expand=True, bgcolor="transparent")
    current_view: dict[str, str] = {"name": "performance"}

    CARD_H_ROW1: int = 160
    CARD_H_ROW2: int = 140

    # 使用占位符，待初始化完成后更新
    cpu_name: str = "正在检测..."
    cpu_title: ft.Text = ft.Text(
        cpu_name,
        size=16,
        weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_PRIMARY"))
    cpu_bar: ft.ProgressBar = ft.ProgressBar(
        value=0,
        height=8,
        color=theme.get("ACCENT"),
        bgcolor=theme.get("BAR_BG_ALPHA"))
    cpu_usage: ft.Text = ft.Text(
        "Load: —", size=13, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_SECONDARY"))
    cpu_temp: ft.Text = ft.Text(
        "温度: —", size=12, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    cpu_clock: ft.Text = ft.Text(
        "频率: —", size=12, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    cpu_power: ft.Text = ft.Text(
        "功耗: —", size=12, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    cpu_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(
                    name="devices_other",
                    color=theme.get("TEXT_SECONDARY")),
                ft.Text(
                    "CPU",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            cpu_title, cpu_bar, cpu_usage,
            ft.Row([cpu_temp, cpu_clock, cpu_power], spacing=16)
        ], spacing=8, expand=True),
        height=CARD_H_ROW1,
        padding=12,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    # 使用占位符，待初始化完成后更新
    gpu_names: list[str] = ["正在检测..."]
    gpu_dd: ft.Dropdown = ft.Dropdown(
        options=[
            ft.dropdown.Option(
                str(i),
                text=name) for i,
            name in enumerate(gpu_names)],
        value="0",
        width=300,
        dense=True,
        border_width=0,
        text_style=ft.TextStyle(weight=ft.FontWeight.BOLD))
    gpu_bar: ft.ProgressBar = ft.ProgressBar(
        value=0,
        height=8,
        color=theme.get("ACCENT"),
        bgcolor=theme.get("BAR_BG_ALPHA"))
    gpu_usage: ft.Text = ft.Text(
        "Load: —", size=13, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_SECONDARY"))
    gpu_temp: ft.Text = ft.Text(
        "温度: —", size=12, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    gpu_clock: ft.Text = ft.Text(
        "频率: —", size=12, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    gpu_mem: ft.Text = ft.Text(
        "显存: —", size=12, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    gpu_power: ft.Text = ft.Text(
        "功耗: —", size=12, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    gpu_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(
                    name="developer_board",
                    color=theme.get("TEXT_SECONDARY")),
                ft.Text(
                    "GPU",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY")),
                ft.Container(expand=True),
                gpu_dd
            ], spacing=8),
            gpu_bar, gpu_usage,
            ft.Row([gpu_temp, gpu_clock, gpu_power], spacing=16),
            gpu_mem
        ], spacing=8, expand=True),
        height=CARD_H_ROW1,
        padding=12,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    mem_bar: ft.ProgressBar = ft.ProgressBar(
        value=0,
        height=8,
        color=theme.get("ACCENT"),
        bgcolor=theme.get("BAR_BG_ALPHA"))
    mem_pct: ft.Text = ft.Text(
        "占用: —", size=13, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_SECONDARY"))
    mem_freq: ft.Text = ft.Text(
        "频率: —", size=12, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    mem_used: ft.Text = ft.Text(
        "已用/总计: —", size=12, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    mem_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="memory", color=theme.get("TEXT_SECONDARY")),
                ft.Text(
                    "内存",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            mem_bar, mem_pct, mem_freq, mem_used
        ], spacing=8, expand=True),
        height=CARD_H_ROW2,
        padding=12,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    disk_list: ft.Column = ft.Column(
        spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    storage_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="storage", color=theme.get("TEXT_SECONDARY")),
                ft.Text(
                    "存储",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            disk_list
        ], spacing=8, expand=True),
        height=CARD_H_ROW2,
        padding=12,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    net_up_icon: ft.Icon = ft.Icon(
        name="arrow_upward", size=16, color=theme.get("TEXT_SECONDARY"))
    net_up: ft.Text = ft.Text(
        "—", size=13, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_SECONDARY"))
    net_dn_icon: ft.Icon = ft.Icon(
        name="arrow_downward", size=16, color=theme.get("TEXT_SECONDARY"))
    net_dn: ft.Text = ft.Text(
        "—", size=13, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_SECONDARY"))
    net_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(
                    name="network_check",
                    color=theme.get("TEXT_SECONDARY")),
                ft.Text(
                    "网络",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            ft.Row([
                ft.Row([net_up_icon, net_up], spacing=4),
                ft.Row([net_dn_icon, net_dn], spacing=4)
            ], spacing=16)
        ], spacing=8, expand=True),
        height=CARD_H_ROW2,
        padding=12,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    weather_api_key_field: ft.TextField = ft.TextField(
        label="API密钥",
        value="",
        password=True,
        width=300,
        helper_text="在dev.qweather.com申请",
        on_change=lambda e: update_weather_config()
    )

    weather_api_host_field: ft.TextField = ft.TextField(
        label="API Host",
        value="",
        width=300,
        helper_text="你可以在控制台-设置中查看你的API Host",
        on_change=lambda e: update_weather_config()
    )

    weather_use_jwt_switch: ft.Switch = ft.Switch(
        label="使用JWT",
        value=False,
        scale=0.8,
        on_change=lambda e: update_weather_config()
    )

    weather_default_city_field: ft.TextField = ft.TextField(
        label="城市设置",
        value="",
        width=200,
        helper_text="例：北京 或 beijing",
        on_change=lambda e: update_weather_config()
    )

    weather_config_status: ft.Text = ft.Text(
        "配置状态: 未设置",
        size=12,
        color=theme.get("TEXT_TERTIARY")
    )

    def update_weather_config() -> None:
        api_key: str = weather_api_key_field.value.strip()
        api_host: str = weather_api_host_field.value.strip()
        default_city: str = weather_default_city_field.value.strip()

        config_complete: bool = bool(api_key and api_host and default_city)

        if config_complete:
            weather_config_status.value = "配置状态: 待保存"
            weather_config_status.color = theme.get("WARN")
            weather_save_btn.disabled = False
        else:
            weather_config_status.value = "配置状态: 不完整"
            weather_config_status.color = theme.get("BAD")
            weather_save_btn.disabled = True

        page.update()

    def save_weather_config() -> None:
        try:
            config_changed: bool = weather_api.update_config(
                api_key=weather_api_key_field.value.strip(),
                api_host=weather_api_host_field.value.strip(),
                use_jwt=weather_use_jwt_switch.value,
                default_city=weather_default_city_field.value.strip()
            )
            config_mgr.set_weather_config(
                api_key=weather_api_key_field.value.strip(),
                api_host=weather_api_host_field.value.strip(),
                use_jwt=weather_use_jwt_switch.value,
                default_city=weather_default_city_field.value.strip()
            )
            if config_changed:
                weather_config_status.value = "配置已保存"
                weather_config_status.color = theme.get("GOOD")

                if current_view["name"] == "api":
                    update_weather()
            else:
                weather_config_status.value = "配置无变化"
                weather_config_status.color = theme.get("TEXT_TERTIARY")

        except Exception as e:
            weather_config_status.value = f"保存失败: {str(e)}"
            weather_config_status.color = theme.get("BAD")

        page.update()

    weather_save_btn: ft.ElevatedButton = ft.ElevatedButton(
        "保存配置",
        icon="save",
        on_click=lambda e: save_weather_config(),
        disabled=True
    )

    weather_api_config_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="cloud", color=theme.get("TEXT_SECONDARY")),
                ft.Text(
                    "和风天气API",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),

            ft.Row([
                weather_api_key_field,
                weather_api_host_field,
                weather_use_jwt_switch,
            ], spacing=12),

            ft.Row([
                weather_default_city_field,
                ft.Container(width=1),
                weather_save_btn,
                ft.Container(expand=True),
            ], spacing=12),

            weather_config_status,
        ], spacing=16),
        padding=16,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    weather_current_city: ft.Text = ft.Text(
        "当前城市: --", size=16, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_SECONDARY"))
    weather_temp: ft.Text = ft.Text(
        "--°C",
        size=48,
        weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_PRIMARY"))
    weather_feels_like: ft.Text = ft.Text(
        "体感 --°C", size=16, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_SECONDARY"))
    weather_desc: ft.Text = ft.Text(
        "获取中...",
        size=20,
        weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_SECONDARY"))
    weather_quality: ft.Text = ft.Text(
        "空气质量: --",
        size=14,
        weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    weather_comfort: ft.Text = ft.Text(
        "舒适度: --",
        size=14,
        weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))

    weather_humidity: ft.Text = ft.Text(
        "湿度: --%",
        size=14,
        color=theme.get("TEXT_TERTIARY"))
    weather_pressure: ft.Text = ft.Text(
        "气压: --hPa",
        size=14,
        color=theme.get("TEXT_TERTIARY"))
    weather_visibility: ft.Text = ft.Text(
        "能见度: --km",
        size=14,
        color=theme.get("TEXT_TERTIARY"))
    weather_precipitation: ft.Text = ft.Text(
        "降水: --mm/h", size=14, color=theme.get("TEXT_TERTIARY"))
    weather_wind: ft.Text = ft.Text(
        "风力: --", size=14, color=theme.get("TEXT_TERTIARY"))
    weather_cloud: ft.Text = ft.Text(
        "云量: --%",
        size=14,
        color=theme.get("TEXT_TERTIARY"))
    weather_dew_point: ft.Text = ft.Text(
        "露点: --°C",
        size=14,
        color=theme.get("TEXT_TERTIARY"))
    weather_uv_index: ft.Text = ft.Text(
        "紫外线: --",
        size=14,
        color=theme.get("TEXT_TERTIARY"))

    weather_state: dict[str, float] = {"last_update": time.time()}

    def update_weather() -> None:
        try:
            data: WeatherData = weather_api.get_formatted_data(
                force_refresh=True)

            weather_current_city.value = f"当前城市: {data['weather_city']}"
            weather_temp.value = f"{data['weather_temp']:.1f}°C"
            weather_feels_like.value = (
                f"体感 {data['weather_feels_like']:.1f}°C"
            )
            weather_desc.value = data['weather_desc']

            weather_quality.value = f"空气质量: {data['weather_quality']}"
            weather_comfort.value = (
                f"舒适度: {data['weather_comfort_index']}"
            )

            quality_val: str = data['weather_quality']
            quality_color: str
            if quality_val in ["优秀", "良好"]:
                quality_color = theme.get("GOOD")
            elif quality_val == "一般":
                quality_color = theme.get("WARN")
            else:
                quality_color = theme.get("BAD")
            weather_quality.color = quality_color

            comfort_val: str = data['weather_comfort_index']
            comfort_color: str
            if "舒适" in comfort_val:
                comfort_color = theme.get("GOOD")
            elif comfort_val == "一般":
                comfort_color = theme.get("WARN")
            else:
                comfort_color = theme.get("BAD")
            weather_comfort.color = comfort_color

            weather_humidity.value = f"湿度: {data['weather_humidity']}%"
            weather_pressure.value = (
                f"气压: {data['weather_pressure']:.0f}hPa"
            )
            weather_visibility.value = (
                f"能见度: {data['weather_visibility']:.1f}km"
            )
            weather_precipitation.value = (
                f"降水: {data['weather_precipitation']:.1f}mm/h"
            )
            weather_wind.value = f"风力: {data['weather_wind_display']}"
            weather_cloud.value = f"云量: {data['weather_cloud_cover']}%"
            weather_dew_point.value = (
                f"露点: {data['weather_dew_point']:.1f}°C"
            )

            uv_value: str = "--"
            forecast = data['weather_forecast']
            if forecast and len(forecast) > 0:
                uv_value = str(forecast[0].get('uv_index', '--'))
            weather_uv_index.value = f"紫外线: {uv_value}"

            update_weather_forecast(data['weather_forecast'])

            weather_state["last_update"] = time.time()

        except Exception as e:
            weather_current_city.value = "当前城市: 获取失败"
            weather_temp.value = "--°C"
            weather_desc.value = f"错误: {str(e)}"

        page.update()

    weather_refresh_btn: ft.IconButton = ft.IconButton(
        icon="refresh",
        icon_color=theme.get("ACCENT"),
        tooltip="刷新天气",
        on_click=lambda e: update_weather()
    )

    weather_settings_btn: ft.IconButton = ft.IconButton(
        icon="settings",
        icon_color=theme.get("TEXT_SECONDARY"),
        tooltip="天气设置",
        on_click=lambda e: show_view("settings")
    )

    weather_main_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(
                    name="wb_sunny",
                    color=theme.get("TEXT_SECONDARY"),
                    size=22),
                ft.Text(
                    "实时天气",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY")),
                ft.Container(expand=True),
                weather_current_city,
                weather_settings_btn,
                weather_refresh_btn
            ], spacing=6),

            ft.Row([
                ft.Column([
                    weather_temp,
                    weather_feels_like,
                    weather_desc,
                    ft.Container(height=2),
                    ft.Row([weather_quality, weather_comfort], spacing=12),
                ], horizontal_alignment="start", spacing=0, expand=2),

                ft.Column([
                    weather_humidity,
                    weather_pressure,
                    weather_visibility,
                    weather_precipitation,
                ], spacing=4, expand=1),

                ft.Column([
                    weather_wind,
                    weather_cloud,
                    weather_dew_point,
                    weather_uv_index,
                    ft.Container(height=6),
                ], spacing=4, expand=1),

            ], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START),

        ], spacing=4),
        height=220,
        padding=12,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    forecast_container: ft.Column = ft.Column([], spacing=4)

    def update_weather_forecast(
        forecast_data: list[WeatherForecast] | None
    ) -> None:
        forecast_container.controls.clear()

        if not forecast_data:
            forecast_container.controls.append(
                ft.Text(
                    "暂无预报数据",
                    size=14,
                    color=theme.get("TEXT_TERTIARY"))
            )
            return

        for i, day_data in enumerate(forecast_data[:3]):
            date_str: str = day_data.get('date', '')
            date_display: str
            if date_str:
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    if i == 0:
                        date_display = "今天"
                    elif i == 1:
                        date_display = "明天"
                    else:
                        date_display = date_obj.strftime('%m月%d日')
                except BaseException:
                    date_display = date_str
            else:
                date_display = f"第{i + 1}天"

            forecast_row: ft.Container = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(
                            date_display,
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=theme.get("TEXT_PRIMARY")),
                        width=60
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text(
                                day_data.get('text_day', ''),
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=theme.get("TEXT_SECONDARY")),
                            ft.Text(
                                day_data.get('text_night', ''),
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=theme.get("TEXT_TERTIARY")),
                        ], spacing=2),
                        width=50
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"{day_data.get('temp_max', 0)}° / "
                            f"{day_data.get('temp_min', 0)}°",
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            color=theme.get("TEXT_PRIMARY")
                        ),
                        width=50
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"{day_data.get('wind_dir_day', '')} "
                            f"{day_data.get('wind_scale_day', '')}级",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=theme.get("TEXT_TERTIARY")
                        ),
                        width=50
                    ),
                    ft.Container(expand=True),
                    ft.Column([
                        ft.Text(
                            f"湿度{day_data.get('humidity', 0)}%",
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=theme.get("TEXT_TERTIARY")),
                        ft.Text(
                            f"UV{day_data.get('uv_index', 0)}",
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=theme.get("TEXT_TERTIARY")),
                    ], spacing=1),
                ], spacing=8),
                padding=ft.padding.all(4),
                border_radius=6,
                bgcolor=theme.get("BAR_BG_ALPHA") if i % 2 == 0 else None
            )

            forecast_container.controls.append(forecast_row)

    weather_forecast_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(
                    name="date_range",
                    color=theme.get("TEXT_SECONDARY"),
                    size=20),
                ft.Text(
                    "天气预报",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            ft.Container(height=8),
            ft.Container(content=forecast_container, expand=True),
        ], spacing=4, expand=True),
        height=220,
        padding=16,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    performance_view: ft.Container = ft.Container(
        content=ft.Column(
            [
                ft.ResponsiveRow([
                    ft.Column([cpu_card], col={"xs": 12, "md": 6}),
                    ft.Column([gpu_card], col={"xs": 12, "md": 6}),
                ], columns=12),
                ft.ResponsiveRow([
                    ft.Column([mem_card], col={"xs": 12, "md": 3}),
                    ft.Column([storage_card], col={"xs": 12, "md": 6}),
                    ft.Column([net_card], col={"xs": 12, "md": 3}),
                ], columns=12),
                ft.ResponsiveRow([
                    ft.Column(
                        [weather_main_card], col={"xs": 12, "md": 7}),
                    ft.Column(
                        [weather_forecast_card], col={"xs": 12, "md": 5}),
                ], columns=12),
            ],
            spacing=8, expand=True, scroll=ft.ScrollMode.ADAPTIVE
        ),
        padding=12,
        expand=True
    )

    port_dropdown: ft.Dropdown = ft.Dropdown(
        label="端口",
        width=250,
        options=[],
        dense=True,
        on_change=lambda e: on_port_selected(e.control.value)
    )

    def refresh_ports(e: ft.ControlEvent | None = None) -> None:
        ports: list[dict[str, str]] = serial_assistant.get_available_ports()
        port_dropdown.options = [
            ft.dropdown.Option(
                p['port'],
                text=f"{p['port']} - {p['description']}")
            for p in ports
        ]
        if not serial_assistant.is_connected and ports:
            port_dropdown.value = ports[0]['port']
        page.update()

    refresh_port_btn: ft.IconButton = ft.IconButton(
        icon="refresh",
        icon_color=theme.get("ACCENT"),
        tooltip="刷新",
        on_click=refresh_ports
    )

    port_status_text: ft.Text = ft.Text(
        "未连接",
        size=12,
        color=theme.get("TEXT_TERTIARY")
    )

    # 固件版本显示
    firmware_version_text: ft.Text = ft.Text(
        "",
        size=12,
        color=theme.get("TEXT_TERTIARY")
    )

    # 初始化版本检测器
    version_checker = get_version_checker()
    set_version_checker_serial(serial_assistant)

    def on_version_checked(version: str) -> None:
        """版本检测完成回调"""
        if version and version != "未知":
            firmware_version_text.value = f"固件: {version}"
            firmware_version_text.color = theme.get("TEXT_SECONDARY")
        else:
            firmware_version_text.value = "固件: 未知"
            firmware_version_text.color = theme.get("TEXT_TERTIARY")
        try:
            page.update()
        except BaseException:
            pass

    version_checker.on_version_checked = on_version_checked

    def trigger_version_check() -> None:
        """触发版本检测（延迟执行以确保连接稳定）"""
        import threading

        def delayed_check() -> None:
            import time
            time.sleep(3)  # 等待连接稳定
            version_checker.check_version_async()

        threading.Thread(target=delayed_check, daemon=True).start()

    def on_auto_reconnect(
        success: bool,
        port: str,
        is_reconnect: bool
    ) -> None:
        """处理自动重连事件"""
        if success:
            port_dropdown.value = port
            port_dropdown.disabled = True

            if is_reconnect:
                port_status_text.value = "已重连"
            else:
                port_status_text.value = "已连接"
            port_status_text.color = theme.get("GOOD")

            if not finsh_sender.enabled:
                finsh_sender.start()

            config_mgr.set_last_port(port)

            # 触发固件版本检测
            trigger_version_check()
        else:
            port_dropdown.disabled = False
            port_status_text.value = "连接断开"
            port_status_text.color = theme.get("WARN")
            firmware_version_text.value = ""
            finsh_sender.stop()

        try:
            page.update()
        except BaseException:
            pass

    def on_connection_changed(connected: bool) -> None:
        """处理连接状态变化"""
        if connected:
            # 连接成功（包括烧录后重连）
            port_dropdown.disabled = True
            port_status_text.value = "已连接"
            port_status_text.color = theme.get("GOOD")

            if not finsh_sender.enabled:
                finsh_sender.start()

            # 保存端口配置
            port = serial_assistant.config.get('port', '')
            if port:
                config_mgr.set_last_port(port)

            # 触发固件版本检测
            trigger_version_check()
        else:
            # 连接断开
            port_dropdown.disabled = False
            firmware_version_text.value = ""
            if not serial_assistant._manual_disconnect:
                port_status_text.value = "连接断开，正在重连..."
                port_status_text.color = theme.get("WARN")
            else:
                port_status_text.value = "已断开"
                port_status_text.color = theme.get("TEXT_TERTIARY")
            finsh_sender.stop()

        try:
            page.update()
        except BaseException:
            pass

    serial_assistant.on_auto_reconnect = on_auto_reconnect
    serial_assistant.on_connection_changed = on_connection_changed

    def on_port_selected(port: str) -> None:
        if not port:
            return

        if serial_assistant.is_connected:
            finsh_sender.stop()
            serial_assistant.disconnect()

        serial_assistant.configure(
            port=port,
            baudrate=1000000,
            bytesize=8,
            stopbits=1,
            parity='N'
        )

        if serial_assistant.connect():
            port_dropdown.disabled = True
            port_status_text.value = "已连接"
            port_status_text.color = theme.get("GOOD")

            finsh_sender.start()
            config_mgr.set_last_port(port)
            # 手动连接成功，触发版本检测
            trigger_version_check()
        else:
            port_status_text.value = "连接失败"
            port_status_text.color = theme.get("BAD")
            firmware_version_text.value = ""

        page.update()

    def disconnect_port(e: ft.ControlEvent | None = None) -> None:
        if serial_assistant.is_connected:
            finsh_sender.stop()
            serial_assistant.disconnect()
            port_dropdown.disabled = False
            port_status_text.value = "已断开"
            port_status_text.color = theme.get("TEXT_TERTIARY")
            firmware_version_text.value = ""
            page.update()

    disconnect_btn: ft.IconButton = ft.IconButton(
        icon="link_off",
        icon_color=theme.get("TEXT_SECONDARY"),
        tooltip="断开连接",
        on_click=disconnect_port
    )

    serial_config_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="usb", color=theme.get("TEXT_SECONDARY")),
                ft.Text(
                    "设备连接",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            ft.Row(
                [port_dropdown, refresh_port_btn, disconnect_btn],
                spacing=4),
            ft.Row([
                port_status_text,
                ft.Container(width=16),  # 间距
                firmware_version_text,
            ], spacing=0),
        ], spacing=12),
        padding=16,
        height=140,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    refresh_ports()

    serial_assistant.enable_auto_reconnect(enabled=True, interval=2.0)

    if config_mgr.should_auto_connect():
        last_port: str | None = config_mgr.get_last_port()
        if last_port:
            serial_assistant.set_last_connected_port(last_port)

            ports = serial_assistant.get_available_ports()
            if any(p['port'] == last_port for p in ports):
                serial_assistant.configure(
                    port=last_port,
                    baudrate=1000000,
                    bytesize=8,
                    stopbits=1,
                    parity='N'
                )

                if serial_assistant.connect():
                    port_dropdown.value = last_port
                    port_dropdown.disabled = True
                    port_status_text.value = "已连接"
                    port_status_text.color = theme.get("GOOD")
                    finsh_sender.start()
                    # 启动时连接成功，触发版本检测
                    trigger_version_check()

    def on_minimize_to_tray_changed(e: ft.ControlEvent) -> None:
        config_mgr.set_minimize_to_tray(e.control.value)

    def on_auto_start_changed(e: ft.ControlEvent) -> None:
        enabled: bool = e.control.value
        success: bool = AutoStartManager.set_enabled(enabled)
        if success:
            config_mgr.set_auto_start(enabled)
        else:
            e.control.value = AutoStartManager.is_enabled()
            page.update()

    minimize_to_tray_switch: ft.Switch = ft.Switch(
        label="最小化到系统托盘",
        value=config_mgr.should_minimize_to_tray(),
        scale=0.8,
        label_style=ft.TextStyle(
            size=16,
            color=theme.get("TEXT_SECONDARY"),
        ),
        on_change=on_minimize_to_tray_changed,
        disabled=not is_tray_available()
    )

    auto_start_switch: ft.Switch = ft.Switch(
        label="开机自启",
        value=AutoStartManager.is_enabled(),
        scale=0.8,
        label_style=ft.TextStyle(
            size=16,
            color=theme.get("TEXT_SECONDARY"),
        ),
        on_change=on_auto_start_changed
    )

    app_settings_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(
                    name="settings_applications",
                    color=theme.get("TEXT_SECONDARY")),
                ft.Text(
                    "应用设置",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            minimize_to_tray_switch,
            auto_start_switch,
        ], spacing=8),
        padding=16,
        height=140,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    # ==================== 固件更新卡片 ====================
    firmware_updater: FirmwareUpdater = get_firmware_updater()
    firmware_updater.set_serial_assistant(serial_assistant)

    firmware_status_text: ft.Text = ft.Text(
        "等待选择固件文件",
        size=12,
        color=theme.get("TEXT_TERTIARY")
    )

    firmware_progress_bar: ft.ProgressBar = ft.ProgressBar(
        width=400,
        value=0,
        color=theme.get("ACCENT"),
        bgcolor=theme.get("BAR_BG_ALPHA"),
        visible=False
    )

    firmware_file_info: ft.Text = ft.Text(
        "",
        size=11,
        color=theme.get("TEXT_TERTIARY"),
        visible=False
    )

    firmware_update_btn: ft.ElevatedButton = ft.ElevatedButton(
        "开始更新",
        icon="system_update",
        disabled=True,
        visible=False
    )

    def update_firmware_ui() -> None:
        """更新固件更新界面状态"""
        status_text, color_type = firmware_updater.get_status_display()
        firmware_status_text.value = status_text

        color_map = {
            "good": theme.get("GOOD"),
            "warn": theme.get("WARN"),
            "bad": theme.get("BAD"),
            "neutral": theme.get("TEXT_TERTIARY"),
        }
        firmware_status_text.color = color_map.get(
            color_type, theme.get("TEXT_TERTIARY")
        )

        # 更新进度条
        if firmware_updater.is_busy:
            firmware_progress_bar.visible = True
            firmware_progress_bar.value = firmware_updater.progress / 100.0
        else:
            firmware_progress_bar.visible = False

        # 更新按钮状态
        if firmware_updater.status == FirmwareUpdateStatus.VALID:
            firmware_update_btn.disabled = False
            firmware_update_btn.visible = True
        elif firmware_updater.is_busy:
            firmware_update_btn.disabled = True
            firmware_update_btn.visible = True
        else:
            firmware_update_btn.visible = False

        try:
            page.update()
        except Exception:
            pass

    def on_firmware_status_changed(
        status: FirmwareUpdateStatus,
        message: str
    ) -> None:
        """固件状态变化回调"""
        update_firmware_ui()

    def on_firmware_progress_changed(progress: int) -> None:
        """固件进度变化回调"""
        firmware_progress_bar.value = progress / 100.0
        try:
            page.update()
        except Exception:
            pass

    firmware_updater.on_status_changed = on_firmware_status_changed
    firmware_updater.on_progress_changed = on_firmware_progress_changed

    def on_firmware_file_picked(e: ft.FilePickerResultEvent) -> None:
        """固件文件选择回调"""
        if not e.files or len(e.files) == 0:
            return

        file_path = e.files[0].path
        if not file_path:
            return

        # 验证固件文件
        valid, message, found_files = firmware_updater.validate_firmware_zip(
            file_path
        )

        if valid and found_files:
            firmware_file_info.value = f"已验证更新包"
            firmware_file_info.visible = True
        else:
            firmware_file_info.visible = False

        update_firmware_ui()

    firmware_file_picker: ft.FilePicker = ft.FilePicker(
        on_result=on_firmware_file_picked
    )
    page.overlay.append(firmware_file_picker)

    def on_select_firmware_click(e: ft.ControlEvent) -> None:
        """选择固件文件按钮点击"""
        firmware_file_picker.pick_files(
            dialog_title="选择固件更新包",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["zip"],
            allow_multiple=False
        )

    def on_start_update_click(e: ft.ControlEvent) -> None:
        """开始更新按钮点击"""
        if not serial_assistant.is_connected:
            firmware_status_text.value = "✗ 请先连接设备"
            firmware_status_text.color = theme.get("BAD")
            page.update()
            return

        firmware_updater.start_update()

    firmware_update_btn.on_click = on_start_update_click

    select_firmware_btn: ft.ElevatedButton = ft.ElevatedButton(
        "选择固件包 (.zip)",
        icon="folder_open",
        on_click=on_select_firmware_click
    )

    firmware_update_card: ft.Card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="system_update", color=theme.get("TEXT_SECONDARY")),
                ft.Text(
                    "固件更新",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            ft.Container(height=4),
            ft.Row([
                select_firmware_btn,
                firmware_update_btn,
            ], spacing=8),
            firmware_file_info,
            firmware_progress_bar,
            firmware_status_text,
        ], spacing=8),
        padding=16,
        bgcolor=theme.get("CARD_BG_ALPHA"),
        border_radius=10
    ))

    settings_view: ft.Container = ft.Container(
        content=ft.Column([
            ft.Text(
                "设置",
                size=24,
                weight=ft.FontWeight.BOLD,
                color=theme.get("TEXT_PRIMARY")),
            ft.Row([
                ft.Container(content=serial_config_card, expand=True),
                ft.Container(content=app_settings_card, expand=True),
            ], spacing=12, alignment=ft.MainAxisAlignment.START,
               vertical_alignment=ft.CrossAxisAlignment.START),
            firmware_update_card,
            weather_api_config_card,
        ], spacing=12, scroll=ft.ScrollMode.ADAPTIVE, expand=True),
        padding=20,
        expand=True
    )

    platform_name: str = "Windows" if IS_WINDOWS else (
        "macOS" if IS_MACOS else "Linux")

    about_view: ft.Container = ft.Container(
        content=ft.Column([
            ft.Text(
                "关于",
                size=24,
                weight=ft.FontWeight.BOLD,
                color=theme.get("TEXT_PRIMARY")),
            ft.Text(
                f"SuperKey_{platform_name}支持工具",
                size=16,
                color=theme.get("TEXT_SECONDARY")),
            ft.Text(
                f"Build v{APP_VERSION} - 适配固件{FIRMWARE_COMPAT}版本",
                size=14,
                color=theme.get("TEXT_TERTIARY")),
            ft.Container(height=20),
            ft.Text(
                "制作团队",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=theme.get("TEXT_SECONDARY")),
            ft.Text(
                "• 解博文 xiebowen1@outlook.com",
                size=12,
                color=theme.get("TEXT_TERTIARY")),
            ft.Text(
                "• 蔡松 19914553473@163.com",
                size=12,
                color=theme.get("TEXT_TERTIARY")),
            ft.Text(
                "• 郭雨十 2361768748@qq.com",
                size=12,
                color=theme.get("TEXT_TERTIARY")),
            ft.Text(
                "• 思澈科技（南京）提供技术支持",
                size=12,
                color=theme.get("TEXT_TERTIARY")),
            ft.Container(height=20),
            ft.Text(
                "更新日志 2025年12月9日",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=theme.get("TEXT_SECONDARY")),
            ft.Text(
                "• 修复：天气信息自动更新，APP自动获取权限",
                size=12,
                color=theme.get("TEXT_TERTIARY")),
            ft.Text(
                "• 新增：开机自启，自动检测与连接，配置保存，"
                "后台运行，自定义按键配置",
                size=12,
                color=theme.get("TEXT_TERTIARY")),
            ft.Text(
                "• 删除：复杂的串口配置页面和数据下发间隔配置",
                size=12,
                color=theme.get("TEXT_TERTIARY")),
            ft.Text(
                "• 本次更新与旧版本固件部分兼容",
                size=12,
                color=theme.get("TEXT_TERTIARY")),
            ft.Container(height=20),
            ft.Text(
                "开源协议",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=theme.get("TEXT_SECONDARY")),
            ft.Text(
                "• Apache-2.0",
                size=12,
                color=theme.get("TEXT_TERTIARY")),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.START),
        padding=20,
        expand=True
    )

    # ==================== 自定义按键视图 ====================
    custom_key_manager: Any = None
    custom_key_status: ft.Text = ft.Text(
        "", size=12, weight=ft.FontWeight.BOLD,
        color=theme.get("TEXT_TERTIARY"))
    def create_led_view() -> ft.Container:
        """创建LED灯光控制视图"""
        
        led_status_text: ft.Text = ft.Text(
            "未连接设备", size=12, color=theme.get("TEXT_TERTIARY")
        )
        
        def update_led_status() -> None:
            if serial_assistant.is_connected:
                led_status_text.value = "✓ 设备已连接"
                led_status_text.color = theme.get("GOOD")
            else:
                led_status_text.value = "✗ 设备未连接"
                led_status_text.color = theme.get("BAD")
            try:
                page.update()
            except Exception:
                pass
        
        # ===== 亮度控制 =====
        brightness_value_text: ft.Text = ft.Text(
            "128", size=14, weight=ft.FontWeight.BOLD,
            color=theme.get("TEXT_PRIMARY"), width=40,
            text_align=ft.TextAlign.CENTER
        )
        
        def on_brightness_change(e: ft.ControlEvent) -> None:
            brightness = int(e.control.value)
            brightness_value_text.value = str(brightness)
            led_controller.set_brightness(brightness)
            update_led_status()
            page.update()
        
        brightness_slider: ft.Slider = ft.Slider(
            min=0, max=255, value=128, divisions=255,
            label="{value}", expand=True,
            on_change_end=on_brightness_change,
            active_color=theme.get("ACCENT"),
        )
        
        brightness_card: ft.Card = ft.Card(ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(name="brightness_6", color=theme.get("TEXT_SECONDARY")),
                    ft.Text("亮度控制", size=16, weight=ft.FontWeight.BOLD,
                           color=theme.get("TEXT_PRIMARY")),
                    ft.Container(expand=True),
                    brightness_value_text,
                ], spacing=8),
                ft.Container(height=8),
                brightness_slider,
            ], spacing=4),
            padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
        ))
        
        # ===== 颜色选择 =====
        current_color_display: ft.Container = ft.Container(
            width=40, height=40, bgcolor="#FF0000", border_radius=8,
            border=ft.border.all(2, theme.get("BORDER"))
        )
        
        current_color_hex: ft.Text = ft.Text(
            "#FF0000", size=14, weight=ft.FontWeight.BOLD,
            color=theme.get("TEXT_PRIMARY"), selectable=True
        )
        
        def on_preset_color_click(color_hex: str, preset_name: str) -> None:
            current_color_display.bgcolor = f"#{color_hex}"
            current_color_hex.value = f"#{color_hex}"
            led_controller.set_preset_color(preset_name)
            update_led_status()
            page.update()
        
        def create_color_button(preset) -> ft.Container:
            return ft.Container(
                width=36, height=36, bgcolor=f"#{preset.color}",
                border_radius=6, border=ft.border.all(1, theme.get("BORDER")),
                tooltip=preset.display_name, ink=True,
                on_click=lambda e, c=preset.color, n=preset.name: on_preset_color_click(c, n)
            )
        
        color_buttons = [create_color_button(preset) for preset in LED_COLOR_PRESETS]
        
        custom_color_field: ft.TextField = ft.TextField(
            label="自定义颜色", hint_text="RRGGBB", value="FF0000",
            width=120, dense=True, max_length=6,
        )
        
        def on_custom_color_apply(e: ft.ControlEvent) -> None:
            color = custom_color_field.value.strip().upper()
            if len(color) == 6:
                try:
                    int(color, 16)
                    current_color_display.bgcolor = f"#{color}"
                    current_color_hex.value = f"#{color}"
                    led_controller.set_color(color)
                    update_led_status()
                    page.update()
                except ValueError:
                    pass
        
        custom_color_btn: ft.ElevatedButton = ft.ElevatedButton(
            "应用", on_click=on_custom_color_apply, height=36,
        )
        
        color_card: ft.Card = ft.Card(ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(name="palette", color=theme.get("TEXT_SECONDARY")),
                    ft.Text("颜色选择", size=16, weight=ft.FontWeight.BOLD,
                           color=theme.get("TEXT_PRIMARY")),
                    ft.Container(expand=True),
                    current_color_display,
                    current_color_hex,
                ], spacing=8),
                ft.Container(height=8),
                ft.Text("预设颜色", size=12, color=theme.get("TEXT_TERTIARY")),
                ft.Row(color_buttons, spacing=8, wrap=True),
                ft.Container(height=8),
                ft.Text("自定义颜色", size=12, color=theme.get("TEXT_TERTIARY")),
                ft.Row([
                    ft.Text("#", size=14, color=theme.get("TEXT_SECONDARY")),
                    custom_color_field,
                    custom_color_btn,
                ], spacing=8),
            ], spacing=4),
            padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
        ))
        
        # ===== 效果选择 =====
        current_effect_text: ft.Text = ft.Text(
            "静态", size=14, weight=ft.FontWeight.BOLD,
            color=theme.get("TEXT_PRIMARY")
        )
        
        effect_period_field: ft.TextField = ft.TextField(
            label="周期(ms)", value="2000", width=100, dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        
        def on_effect_click(effect: LedEffect) -> None:
            current_effect_text.value = LED_EFFECT_NAMES.get(effect, "未知")
            try:
                period = int(effect_period_field.value)
            except ValueError:
                period = 2000
            
            if effect == LedEffect.RAINBOW:
                led_controller.set_effect_with_params(
                    effect, period_ms=period,
                    brightness=int(brightness_slider.value)
                )
            elif effect in [LedEffect.BREATHING, LedEffect.FLOWING, LedEffect.BLINK]:
                color = current_color_hex.value.replace("#", "")
                led_controller.set_effect_with_params(
                    effect, color=color, period_ms=period,
                    brightness=int(brightness_slider.value)
                )
            else:
                led_controller.set_effect(effect)
            
            update_led_status()
            page.update()
        
        def create_effect_button(effect: LedEffect, icon_name: str) -> ft.ElevatedButton:
            return ft.ElevatedButton(
                text=LED_EFFECT_NAMES.get(effect, ""),
                icon=icon_name,
                on_click=lambda e, eff=effect: on_effect_click(eff),
                height=40,
            )
        
        effect_buttons = [
            create_effect_button(LedEffect.STATIC, "circle"),
            create_effect_button(LedEffect.BREATHING, "air"),
            create_effect_button(LedEffect.FLOWING, "waves"),
            create_effect_button(LedEffect.BLINK, "flash_on"),
            create_effect_button(LedEffect.RAINBOW, "gradient"),
        ]
        
        stop_btn: ft.ElevatedButton = ft.ElevatedButton(
            text="停止", icon="stop",
            on_click=lambda e: (led_controller.stop(), update_led_status(), page.update()),
            bgcolor=theme.get("BAD"), color=theme.get("TEXT_INVERSE"), height=40,
        )
        
        effect_card: ft.Card = ft.Card(ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(name="auto_awesome", color=theme.get("TEXT_SECONDARY")),
                    ft.Text("效果控制", size=16, weight=ft.FontWeight.BOLD,
                           color=theme.get("TEXT_PRIMARY")),
                    ft.Container(expand=True),
                    ft.Text("当前:", size=12, color=theme.get("TEXT_TERTIARY")),
                    current_effect_text,
                ], spacing=8),
                ft.Container(height=8),
                ft.Row([
                    ft.Text("效果周期:", size=12, color=theme.get("TEXT_TERTIARY")),
                    effect_period_field,
                    ft.Text("ms", size=12, color=theme.get("TEXT_TERTIARY")),
                ], spacing=8),
                ft.Container(height=8),
                ft.Row(effect_buttons + [stop_btn], spacing=8, wrap=True),
            ], spacing=4),
            padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
        ))
        
        # ===== 快捷操作 =====
        def quick_demo() -> None:
            import threading
            import time as time_module
            
            def demo_sequence():
                effects = [
                    (LedEffect.STATIC, "FF0000", 1000),
                    (LedEffect.BREATHING, "00FF00", 1500),
                    (LedEffect.FLOWING, "0000FF", 1000),
                    (LedEffect.BLINK, "FFFF00", 500),
                    (LedEffect.RAINBOW, None, 2000),
                ]
                for effect, color, period in effects:
                    if color:
                        led_controller.set_effect_with_params(
                            effect, color=color, period_ms=period
                        )
                    else:
                        led_controller.set_effect_with_params(effect, period_ms=period)
                    time_module.sleep(3)
                led_controller.stop()
            
            threading.Thread(target=demo_sequence, daemon=True).start()
        
        quick_card: ft.Card = ft.Card(ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(name="bolt", color=theme.get("TEXT_SECONDARY")),
                    ft.Text("快捷操作", size=16, weight=ft.FontWeight.BOLD,
                           color=theme.get("TEXT_PRIMARY")),
                ], spacing=8),
                ft.Container(height=8),
                ft.Row([
                    ft.ElevatedButton(
                        "演示模式", icon="play_arrow",
                        on_click=lambda e: quick_demo(), height=36,
                    ),
                    ft.ElevatedButton(
                        "全部关闭", icon="power_settings_new",
                        on_click=lambda e: (led_controller.turn_off(), update_led_status(), page.update()),
                        height=36,
                    ),
                ], spacing=8),
            ], spacing=4),
            padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
        ))
        
        update_led_status()
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("灯光效果", size=24, weight=ft.FontWeight.BOLD,
                           color=theme.get("TEXT_PRIMARY")),
                    ft.Container(expand=True),
                    led_status_text,
                ], spacing=8),
                ft.Container(height=12),
                brightness_card,
                ft.Container(height=8),
                color_card,
                ft.Container(height=8),
                effect_card,
                ft.Container(height=8),
                quick_card,
            ], spacing=0, scroll=ft.ScrollMode.AUTO),
            padding=20, expand=True,
        )
    
    led_view: ft.Container | None = None
    def create_custom_key_view() -> ft.Container:
        nonlocal custom_key_manager

        def send_command(cmd: str) -> bool:
            if serial_assistant and serial_assistant.is_connected:
                try:
                    serial_assistant.send_data(cmd + "\r\n")
                    return True
                except BaseException:
                    return False
            return False

        custom_key_manager = get_custom_key_manager(send_command)

        modifier_options: list[tuple[str, int]] = get_modifier_options()

        modifier_dropdown_options: list[ft.dropdown.Option] = [
            ft.dropdown.Option(
                text=name,
                key=str(val)) for name,
            val in modifier_options]
        preset_options: list[ft.dropdown.Option] = [
            ft.dropdown.Option(name) for name in PRESET_SHORTCUTS.keys()
        ]

        combo_controls: dict[tuple[int, int], dict[str, Any]] = {}
        key_summary_texts: dict[int, ft.Text] = {}

        # 键盘捕获状态
        key_capture_state: dict[str, Any] = {
            "active": False,
            "key_idx": -1,
            "combo_idx": -1,
            "button": None,
        }

        def update_status(msg: str, is_error: bool = False) -> None:
            custom_key_status.value = msg
            custom_key_status.color = theme.get(
                "BAD") if is_error else theme.get("GOOD")
            page.update()

        def refresh_key_summary(
            key_idx: int, skip_update: bool = False
        ) -> None:
            """刷新按键摘要显示"""
            if key_idx in key_summary_texts:
                parts: list[str] = []
                for ci in range(4):
                    text: str = custom_key_manager.get_combo_display_text(
                        key_idx, ci)
                    if text != "无":
                        parts.append(f"[{ci + 1}]{text}")
                summary: str = " → ".join(parts) if parts else "未配置"
                key_summary_texts[key_idx].value = summary
                if not skip_update:
                    page.update()

        def on_modifier_change(
            key_idx: int,
            combo_idx: int
        ) -> Callable[[ft.ControlEvent], None]:
            def handler(e: ft.ControlEvent) -> None:
                mod_value: int = (
                    int(e.control.value) if e.control.value else 0
                )
                _, current_keycode = custom_key_manager.get_combo(
                    key_idx, combo_idx)
                custom_key_manager.set_combo(
                    key_idx, combo_idx, mod_value, current_keycode)
                refresh_key_summary(key_idx)
            return handler

        def on_keycode_change(
            key_idx: int,
            combo_idx: int
        ) -> Callable[[ft.ControlEvent], None]:
            def handler(e: ft.ControlEvent) -> None:
                keycode: int = int(e.control.value) if e.control.value else 0
                current_mod, _ = custom_key_manager.get_combo(
                    key_idx, combo_idx)
                custom_key_manager.set_combo(
                    key_idx, combo_idx, current_mod, keycode)
                refresh_key_summary(key_idx)
            return handler

        def start_key_capture(
            key_idx: int,
            combo_idx: int,
            button: ft.ElevatedButton
        ) -> Callable[[ft.ControlEvent], None]:
            """开始捕获键盘输入"""
            def handler(e: ft.ControlEvent) -> None:
                # 如果已经在捕获，先取消之前的
                if key_capture_state["active"] and key_capture_state["button"]:
                    old_btn = key_capture_state["button"]
                    old_key_idx = key_capture_state["key_idx"]
                    old_combo_idx = key_capture_state["combo_idx"]
                    _, old_keycode = custom_key_manager.get_combo(
                        old_key_idx, old_combo_idx)
                    old_btn.text = get_key_display_name(old_keycode)
                    old_btn.bgcolor = theme.get("BG_OVERLAY")

                # 设置新的捕获状态
                key_capture_state["active"] = True
                key_capture_state["key_idx"] = key_idx
                key_capture_state["combo_idx"] = combo_idx
                key_capture_state["button"] = button

                # 更新按钮样式
                button.text = "按下按键..."
                button.bgcolor = theme.get("ACCENT")
                page.update()

            return handler

        def on_keyboard_event(e: ft.KeyboardEvent) -> None:
            """处理键盘事件"""
            if not key_capture_state["active"]:
                return

            key_idx = key_capture_state["key_idx"]
            combo_idx = key_capture_state["combo_idx"]
            button = key_capture_state["button"]

            # 转换 Flet 键名到 HID keycode
            hid_keycode = flet_key_to_hid(e.key)

            if hid_keycode is not None:
                # 获取当前修饰键
                current_mod, _ = custom_key_manager.get_combo(
                    key_idx, combo_idx)

                # 设置新的按键
                custom_key_manager.set_combo(
                    key_idx, combo_idx, current_mod, hid_keycode)

                # 更新按钮显示
                button.text = get_key_display_name(hid_keycode)
                button.bgcolor = theme.get("BG_OVERLAY")

                # 更新 combo_controls 中的记录
                if (key_idx, combo_idx) in combo_controls:
                    combo_controls[
                        (key_idx, combo_idx)
                    ]["keycode"] = hid_keycode

                refresh_key_summary(key_idx)
                update_status(f"已设置按键: {get_key_display_name(hid_keycode)}")
            else:
                # 不支持的按键 - 显示提示但不阻塞
                update_status(f"不支持的按键: {e.key}", is_error=True)
                # 恢复按钮状态
                _, current_keycode = custom_key_manager.get_combo(
                    key_idx, combo_idx)
                button.text = get_key_display_name(current_keycode)
                button.bgcolor = theme.get("BG_OVERLAY")

            # 结束捕获状态
            key_capture_state["active"] = False
            key_capture_state["key_idx"] = -1
            key_capture_state["combo_idx"] = -1
            key_capture_state["button"] = None
            page.update()

        # 注册全局键盘事件
        page.on_keyboard_event = on_keyboard_event

        def on_preset_change(
            key_idx: int
        ) -> Callable[[ft.ControlEvent], None]:
            def handler(e: ft.ControlEvent) -> None:
                preset_name: str = e.control.value
                if preset_name:
                    custom_key_manager.set_key_from_preset(
                        key_idx, preset_name)
                    for ci in range(4):
                        mod, keycode = custom_key_manager.get_combo(
                            key_idx, ci)
                        if (key_idx, ci) in combo_controls:
                            combo_controls[(key_idx, ci)
                                           ]["mod"].value = str(mod)
                            # 更新按键按钮显示
                            key_btn = combo_controls[(key_idx, ci)]["key_btn"]
                            key_btn.text = get_key_display_name(keycode)
                            combo_controls[(key_idx, ci)]["keycode"] = keycode
                    refresh_key_summary(key_idx)
                    update_status(f"已应用预设: {preset_name}")
            return handler

        def on_apply_click(
            key_idx: int
        ) -> Callable[[ft.ControlEvent], None]:
            def handler(e: ft.ControlEvent) -> None:
                if custom_key_manager.sync_key_to_device(key_idx):
                    update_status(f"按键{key_idx + 1} 已同步到设备")
                else:
                    update_status("同步失败，请检查串口连接", True)
            return handler

        def on_clear_click(
            key_idx: int
        ) -> Callable[[ft.ControlEvent], None]:
            def handler(e: ft.ControlEvent) -> None:
                custom_key_manager.clear_key(key_idx)
                for ci in range(4):
                    if (key_idx, ci) in combo_controls:
                        combo_controls[(key_idx, ci)]["mod"].value = "0"
                        combo_controls[(key_idx, ci)]["key_btn"].text = "无"
                        combo_controls[(key_idx, ci)]["keycode"] = 0
                refresh_key_summary(key_idx)
                update_status(f"已清除 按键{key_idx + 1}")
            return handler

        def on_sync_all_click(e: ft.ControlEvent) -> None:
            if custom_key_manager.sync_all_to_device():
                update_status("所有配置已同步到设备")
            else:
                update_status("同步失败，请检查串口连接", True)

        def create_combo_row(key_idx: int, combo_idx: int) -> ft.Row:
            current_mod: int
            current_keycode: int
            current_mod, current_keycode = custom_key_manager.get_combo(
                key_idx, combo_idx)

            mod_dropdown: ft.Dropdown = ft.Dropdown(
                label="修饰键",
                options=modifier_dropdown_options,
                value=str(current_mod),
                on_change=on_modifier_change(key_idx, combo_idx),
                width=120,
                dense=True,
                text_size=12,
                text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            )

            # 使用按钮代替下拉框，点击后捕获键盘输入
            key_button: ft.ElevatedButton = ft.ElevatedButton(
                text=get_key_display_name(current_keycode),
                width=100,
                height=40,
                bgcolor=theme.get("BG_OVERLAY"),
                color=theme.get("TEXT_PRIMARY"),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=4),
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                ),
            )
            # 设置点击事件（需要在创建后设置，因为要传递按钮自身）
            key_button.on_click = start_key_capture(
                key_idx, combo_idx, key_button)

            combo_controls[(key_idx, combo_idx)] = {
                "mod": mod_dropdown,
                "key_btn": key_button,
                "keycode": current_keycode,
            }

            return ft.Row([
                ft.Text(
                    f"{combo_idx + 1}.",
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_TERTIARY"),
                    width=20),
                mod_dropdown,
                ft.Text(
                    "+", size=12, weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_TERTIARY")),
                key_button,
            ], spacing=4, alignment=ft.MainAxisAlignment.START)

        def create_key_card(key_idx: int) -> ft.Container:
            preset_dropdown: ft.Dropdown = ft.Dropdown(
                label="快捷预设",
                options=preset_options,
                on_change=on_preset_change(key_idx),
                width=180,
                dense=True,
                text_size=12,
                text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            )

            combo_rows: list[ft.Row] = [
                create_combo_row(key_idx, ci) for ci in range(4)
            ]

            summary_text: ft.Text = ft.Text(
                custom_key_manager.get_key_display_text(key_idx),
                size=11,
                weight=ft.FontWeight.BOLD,
                color=theme.get("GOOD"),
                italic=True,
            )
            key_summary_texts[key_idx] = summary_text
            refresh_key_summary(key_idx, skip_update=True)

            apply_btn: ft.ElevatedButton = ft.ElevatedButton(
                "同步到设备",
                icon="sync",
                on_click=on_apply_click(key_idx),
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(
                        horizontal=8,
                        vertical=4)),
            )
            clear_btn: ft.TextButton = ft.TextButton(
                "清除",
                on_click=on_clear_click(key_idx),
            )

            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(
                            "keyboard",
                            size=16,
                            color=theme.get("TEXT_SECONDARY")),
                        ft.Text(
                            f"按键 {key_idx + 1}",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=theme.get("TEXT_PRIMARY")),
                    ], spacing=6),
                    ft.Divider(height=1, color=theme.get("BORDER")),
                    preset_dropdown,
                    ft.Text(
                        "自定义映射 (按顺序执行):",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=theme.get("TEXT_TERTIARY")),
                    *combo_rows,
                    ft.Container(
                        content=summary_text,
                        padding=ft.padding.only(top=4),
                    ),
                    ft.Row([apply_btn, clear_btn], spacing=8),
                ], spacing=6),
                padding=12,
                bgcolor=theme.get("BAR_BG_ALPHA"),
                border_radius=8,
                width=280,
            )

        key_cards: ft.Row = ft.Row(
            [create_key_card(ki) for ki in range(3)],
            spacing=16,
            wrap=True,
            alignment=ft.MainAxisAlignment.START,
        )

        sync_all_btn: ft.ElevatedButton = ft.ElevatedButton(
            "同步所有到设备",
            icon="sync",
            on_click=on_sync_all_click,
        )

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(
                        name="keyboard",
                        color=theme.get("TEXT_SECONDARY")),
                    ft.Text(
                        "自定义按键配置",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=theme.get("TEXT_PRIMARY")),
                    ft.Container(expand=True),
                    sync_all_btn,
                ], spacing=8),
                ft.Text(
                    "配置设备自定义按键",
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=theme.get("TEXT_TERTIARY")),
                ft.Container(height=12),
                key_cards,
                ft.Container(height=8),
                custom_key_status,
            ], spacing=8, scroll=ft.ScrollMode.AUTO),
            padding=20,
            expand=True,
        )

    custom_key_view: ft.Container | None = None

    def show_view(name: str) -> None:
        nonlocal custom_key_view
        current_view["name"] = name
        try:
            if name == "performance":
                content_host.content = performance_view
            elif name == "settings":
                content_host.content = settings_view
            elif name == "about":
                content_host.content = about_view
            elif name == "custom_key":
                if custom_key_view is None:
                    custom_key_view = create_custom_key_view()
                content_host.content = custom_key_view
            elif name == "led":
                nonlocal led_view
                if led_view is None:
                    led_view = create_led_view()
                content_host.content = led_view
        except Exception as e:
            print(f"视图切换错误: {e}")
            import traceback
            traceback.print_exc()

        for nav_item in nav_items:
            if not nav_item.is_separator:
                nav_item.set_active(nav_item.view_name == name)

        page.update()

    nav_items: list[NavigationItem] = [
        NavigationItem("speed", "信息", "performance", theme, show_view, 24),
        NavigationItem("keyboard", "按键", "custom_key", theme, show_view, 20),
        NavigationItem("lightbulb", "灯光", "led", theme, show_view, 20),
        NavigationItem("", "", "", theme, None, is_separator=True),
        NavigationItem("settings", "设置", "settings", theme, show_view, 20),
        NavigationItem("info_outline", "关于", "about", theme, show_view, 20),
    ]

    nav_items[0].set_active(True)

    def toggle_sidebar() -> None:
        sidebar_expanded["value"] = not sidebar_expanded["value"]

        if sidebar_expanded["value"]:
            nav_holder.width = 150
        else:
            nav_holder.width = 56

        for nav_item in nav_items:
            if not nav_item.is_separator:
                nav_item.set_expanded(sidebar_expanded["value"])

        page.update()

    nav_controls: list[ft.Control] = []
    nav_controls.append(ft.Container(height=8))

    for i, nav_item in enumerate(nav_items[:3]):
        nav_controls.append(ft.Container(
            content=nav_item.container,
            padding=ft.padding.symmetric(horizontal=8, vertical=2)
        ))

    nav_controls.append(ft.Container(expand=True))

    nav_controls.append(ft.Container(
        content=nav_items[3].divider,
        padding=ft.padding.symmetric(horizontal=12, vertical=8)
    ))

    for nav_item in nav_items[4:]:
        nav_controls.append(ft.Container(
            content=nav_item.container,
            padding=ft.padding.symmetric(horizontal=8, vertical=2)
        ))

    nav_controls.append(ft.Container(height=8))

    nav_holder: ft.Container = ft.Container(
        content=ft.Column(
            controls=nav_controls,
            spacing=0,
            expand=True,
        ),
        width=72,
        padding=0,
        margin=0,
        border=ft.border.only(right=ft.BorderSide(1, theme.get("DIVIDER")))
    )

    main_row: ft.Row = ft.Row(
        [
            nav_holder,
            ft.Container(content_host, expand=True, padding=0, margin=0)
        ],
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        spacing=0
    )

    content_column: ft.Column = ft.Column(
        [title_bar, main_row], spacing=0, expand=True)

    shell_bg: str
    if theme.current_theme == "light":
        shell_bg = "#F0F0F0"
    else:
        shell_bg = "#1A1A1A"

    shell: ft.Container = ft.Container(
        content=content_column,
        bgcolor=shell_bg,
        expand=True,
        padding=0,
        margin=0,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS
    )

    # 等待硬件初始化完成（最长等待5秒）
    splash_status.value = "正在检测硬件..."
    page.update()

    # 预先创建自定义按键视图（避免首次点击卡顿）
    splash_status.value = "正在加载按键配置..."
    page.update()
    custom_key_view = create_custom_key_view()

    splash_status.value = "正在检测硬件..."
    page.update()

    wait_start: float = time.time()
    while not hw_init_done["ready"] and (time.time() - wait_start) < 5.0:
        await asyncio.sleep(0.1)

    splash_status.value = "启动中..."
    page.update()
    await asyncio.sleep(0.1)  # 短暂显示"启动中"

    # 清除启动画面，显示主界面
    page.clean()
    page.add(shell)

    show_view("performance")

    def initialize_weather_config() -> None:
        config: dict[str, Any] = weather_api.get_config()

        weather_api_key_field.value = config.get('api_key', '')
        weather_api_host_field.value = config.get('api_host', '')
        weather_use_jwt_switch.value = config.get('use_jwt', False)
        weather_default_city_field.value = config.get('default_city', '城市名')

        update_weather_config()

    initialize_weather_config()

    if weather_api.get_config().get('api_configured', False):
        try:
            update_weather()
        except BaseException:
            pass

    def build_disks(items: list[DiskData]) -> None:
        disk_list.controls.clear()
        for d in items:
            used: int = d["used"]
            size: int = d["size"]
            pct: float = (used / size) if size else 0
            bar: ft.ProgressBar = ft.ProgressBar(
                value=pct,
                height=6,
                color=theme.get("ACCENT"),
                bgcolor=theme.get("BAR_BG_ALPHA"))
            t_model: ft.Text = ft.Text(
                d["model"],
                size=14,
                weight=ft.FontWeight.BOLD,
                color=theme.get("TEXT_PRIMARY"))
            t_usage: ft.Text = ft.Text(
                f"{bytes2human(used)} / {bytes2human(size)}  "
                f"({pct * 100:.0f}%)",
                size=12, color=theme.get("TEXT_SECONDARY"))
            t_speed: ft.Text = ft.Text(
                "读: —   写: —",
                size=12,
                color=theme.get("TEXT_TERTIARY"))
            row: ft.Container = ft.Container(
                content=ft.Column(
                    [
                        t_model,
                        bar,
                        t_usage,
                        t_speed],
                    spacing=4),
                padding=8,
                border_radius=8,
                bgcolor=theme.get("BAR_BG_ALPHA"))
            row._speed = t_speed
            disk_list.controls.append(row)
        page.update()

    # 初始时不加载磁盘数据，等待后台初始化完成后由updater填充
    # build_disks(hw_monitor.get_disk_data())

    def update_all_theme_colors() -> None:

        for btn in title_buttons.controls:
            btn.icon_color = theme.get("TEXT_SECONDARY")

        nav_holder.border = ft.border.only(
            right=ft.BorderSide(1, theme.get("DIVIDER")))

        for nav_item in nav_items:
            nav_item.update_theme_colors(theme)

        cpu_title.color = theme.get("TEXT_PRIMARY")
        cpu_bar.color = theme.get("ACCENT")
        cpu_bar.bgcolor = theme.get("BAR_BG_ALPHA")
        cpu_usage.color = theme.get("TEXT_SECONDARY")
        cpu_temp.color = theme.get("TEXT_TERTIARY")
        cpu_clock.color = theme.get("TEXT_TERTIARY")
        cpu_power.color = theme.get("TEXT_TERTIARY")
        cpu_card.content.bgcolor = theme.get("CARD_BG_ALPHA")

        gpu_bar.color = theme.get("ACCENT")
        gpu_bar.bgcolor = theme.get("BAR_BG_ALPHA")
        gpu_usage.color = theme.get("TEXT_SECONDARY")
        gpu_temp.color = theme.get("TEXT_TERTIARY")
        gpu_clock.color = theme.get("TEXT_TERTIARY")
        gpu_mem.color = theme.get("TEXT_TERTIARY")
        gpu_power.color = theme.get("TEXT_TERTIARY")
        gpu_card.content.bgcolor = theme.get("CARD_BG_ALPHA")

        mem_bar.color = theme.get("ACCENT")
        mem_bar.bgcolor = theme.get("BAR_BG_ALPHA")
        mem_pct.color = theme.get("TEXT_SECONDARY")
        mem_freq.color = theme.get("TEXT_TERTIARY")
        mem_used.color = theme.get("TEXT_TERTIARY")
        mem_card.content.bgcolor = theme.get("CARD_BG_ALPHA")

        storage_card.content.bgcolor = theme.get("CARD_BG_ALPHA")

        for disk_container in disk_list.controls:
            if hasattr(disk_container, 'content'):
                if hasattr(disk_container.content, 'controls'):
                    disk_container.bgcolor = theme.get("BAR_BG_ALPHA")
                    for ctrl in disk_container.content.controls:
                        if hasattr(ctrl, 'color'):
                            if (hasattr(ctrl, 'weight') and
                                    ctrl.weight == ft.FontWeight.BOLD):
                                ctrl.color = theme.get("TEXT_PRIMARY")
                            elif isinstance(ctrl, ft.ProgressBar):
                                ctrl.color = theme.get("ACCENT")
                                ctrl.bgcolor = theme.get("BAR_BG_ALPHA")
                            else:
                                ctrl.color = theme.get("TEXT_SECONDARY")

        net_up_icon.color = theme.get("TEXT_SECONDARY")
        net_up.color = theme.get("TEXT_SECONDARY")
        net_dn_icon.color = theme.get("TEXT_SECONDARY")
        net_dn.color = theme.get("TEXT_SECONDARY")
        net_card.content.bgcolor = theme.get("CARD_BG_ALPHA")

        weather_current_city.color = theme.get("TEXT_SECONDARY")
        weather_temp.color = theme.get("TEXT_PRIMARY")
        weather_feels_like.color = theme.get("TEXT_SECONDARY")
        weather_desc.color = theme.get("TEXT_SECONDARY")
        weather_refresh_btn.icon_color = theme.get("ACCENT")
        weather_settings_btn.icon_color = theme.get("TEXT_SECONDARY")
        weather_main_card.content.bgcolor = theme.get("CARD_BG_ALPHA")

        for ctrl in [
            weather_humidity, weather_pressure, weather_visibility,
            weather_precipitation, weather_wind, weather_cloud,
            weather_dew_point, weather_uv_index
        ]:
            ctrl.color = theme.get("TEXT_TERTIARY")

        weather_forecast_card.content.bgcolor = theme.get("CARD_BG_ALPHA")

        serial_config_card.content.bgcolor = theme.get("CARD_BG_ALPHA")

        firmware_update_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        firmware_progress_bar.color = theme.get("ACCENT")
        firmware_progress_bar.bgcolor = theme.get("BAR_BG_ALPHA")

        weather_api_config_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        weather_config_status.color = theme.get("TEXT_TERTIARY")

        if hasattr(settings_view, 'content'):
            if hasattr(settings_view.content, 'controls'):
                for ctrl in settings_view.content.controls:
                    if hasattr(ctrl, 'color'):
                        if hasattr(ctrl, 'size') and ctrl.size == 24:
                            ctrl.color = theme.get("TEXT_PRIMARY")
                        else:
                            ctrl.color = theme.get("TEXT_TERTIARY")

        if hasattr(about_view, 'content'):
            if hasattr(about_view.content, 'controls'):
                for ctrl in about_view.content.controls:
                    if hasattr(ctrl, 'color'):
                        if hasattr(ctrl, 'size'):
                            if ctrl.size == 24:
                                ctrl.color = theme.get("TEXT_PRIMARY")
                            elif ctrl.size == 16:
                                ctrl.color = theme.get("TEXT_SECONDARY")
                            else:
                                ctrl.color = theme.get("TEXT_TERTIARY")

        if theme.current_theme == "light":
            shell.bgcolor = "#F0F0F0"
        else:
            shell.bgcolor = "#1A1A1A"

    async def updater() -> None:
        hw_ui_updated: bool = False  # 标记是否已更新硬件UI

        while True:
            t0: float = time.time()

            # 硬件监控初始化完成后，更新UI（仅执行一次）
            if hw_init_done["ready"] and not hw_ui_updated:
                # 更新CPU名称
                cpu_title.value = hw_monitor.get_cpu_name()
                # 更新GPU下拉列表
                new_gpu_names: list[str] = hw_monitor.gpu_names
                gpu_dd.options = [
                    ft.dropdown.Option(str(i), text=name)
                    for i, name in enumerate(new_gpu_names)
                ]
                gpu_dd.value = "0"
                # 构建磁盘列表
                if current_view["name"] == "performance":
                    build_disks(hw_monitor.get_disk_data())
                hw_ui_updated = True
                try:
                    await page.update_async()
                except Exception:
                    page.update()

            if theme.refresh_theme():
                update_all_theme_colors()

                is_performance = current_view["name"] == "performance"
                if is_performance and hw_init_done["ready"]:
                    dlist: list[DiskData] = hw_monitor.get_disk_data()
                    build_disks(dlist)

                try:
                    await page.update_async()
                except Exception:
                    page.update()

            if current_view["name"] == "performance" and hw_init_done["ready"]:
                c: dict[str, Any] = hw_monitor.get_cpu_data()
                cpu_bar.value = (c.get("usage", 0) or 0) / 100.0
                cpu_usage.value = f"Load: {pct_str(c.get('usage'))}"
                cpu_usage.color = color_by_load(c.get("usage"), theme)
                cpu_temp.value = f"温度: {temp_str(c.get('temp'))}"
                cpu_temp.color = color_by_temp(c.get("temp"), theme)
                cpu_clock.value = f"频率: {mhz_str(c.get('clock_mhz'))}"
                cpu_power.value = f"功耗: {watt_str(c.get('power'))}"

                sel: int = int(gpu_dd.value or 0)
                g: dict[str, Any] = hw_monitor.get_gpu_data(sel)
                util: float | None = g.get("util")
                gpu_bar.value = (util or 0) / 100.0
                gpu_usage.value = f"Load: {pct_str(util)}"
                gpu_usage.color = color_by_load(util, theme)
                gpu_temp.value = f"温度: {temp_str(g.get('temp'))}"
                gpu_temp.color = color_by_temp(g.get("temp"), theme)
                gpu_clock.value = f"频率: {mhz_str(g.get('clock_mhz'))}"
                mem_total: int | None = g.get("mem_total_b")
                mem_used_val: int | None = g.get("mem_used_b")
                if mem_total is not None and mem_used_val is not None:
                    gpu_mem.value = (
                        f"显存: {bytes2human(mem_used_val)} / "
                        f"{bytes2human(mem_total)}"
                    )
                else:
                    gpu_mem.value = "显存: —"
                gpu_power.value = f"功耗: {watt_str(g.get('power'))}"

                m: dict[str, Any] = hw_monitor.get_memory_data()
                mem_bar.value = (m["percent"] or 0) / 100.0
                mem_pct.value = f"占用: {pct_str(m['percent'])}"
                mem_used.value = (
                    f"已用/总计: {bytes2human(m['used_b'])} / "
                    f"{bytes2human(m['total_b'])}"
                )
                mem_freq.value = f"频率: {mhz_str(m['freq_mhz'])}"

                dlist = hw_monitor.get_disk_data()
                if len(dlist) != len(disk_list.controls):
                    build_disks(dlist)
                for i, d in enumerate(dlist):
                    if i < len(disk_list.controls):
                        rb: int | None = d["rps"]
                        wb: int | None = d["wps"]
                        rb_str: str = (
                            bytes2human(rb) + '/s' if rb is not None else '—'
                        )
                        wb_str: str = (
                            bytes2human(wb) + '/s' if wb is not None else '—'
                        )
                        disk_list.controls[i]._speed.value = (
                            f"读: {rb_str}    写: {wb_str}"
                        )

                n: dict[str, Any] = hw_monitor.get_network_data()
                if n["up"] is not None:
                    net_up.value = f"{bytes2human(n['up'])}/s"
                else:
                    net_up.value = "—"
                if n["down"] is not None:
                    net_dn.value = f"{bytes2human(n['down'])}/s"
                else:
                    net_dn.value = "—"

            try:
                await page.update_async()
            except Exception:
                page.update()

            await asyncio.sleep(max(0, 1.0 - (time.time() - t0)))

    page.run_task(updater)


def get_assets_dir() -> str:
    """获取 assets 目录的正确路径（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的环境
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境
        base_path = Path(__file__).parent
    return str(base_path / "assets")


ft.app(
    target=main,
    view=ft.AppView.FLET_APP_HIDDEN,
    assets_dir=get_assets_dir(),  # 使用动态路径
    use_color_emoji=True,
)
