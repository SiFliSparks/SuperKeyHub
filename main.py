#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, time, asyncio, math
import argparse
import flet as ft
import platform

# ==============================================================================
# 命令行参数解析
# ==============================================================================
def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='SuperKey Hardware Monitor')
    parser.add_argument('--minimized', '-m', action='store_true',
                        help='启动时最小化到系统托盘（静默启动）')
    # 忽略 flet 可能传递的其他参数
    args, _ = parser.parse_known_args()
    return args

# 全局启动参数
STARTUP_ARGS = parse_args()
START_MINIMIZED = STARTUP_ARGS.minimized

from hw_monitor import HardwareMonitor, bytes2human, pct_str, mhz_str, temp_str, watt_str
from weather_api import QWeatherAPI as WeatherAPI
from serial_assistant import SerialAssistant
from finsh_data_sender import FinshDataSender
from config_manager import get_config_manager
from system_tray import SystemTray, AutoStartManager, is_tray_available
from custom_key_manager import (
    get_custom_key_manager, PRESET_SHORTCUTS, 
    get_all_key_options, get_modifier_options,
    KEY_NAME_MAP, Modifier
)

# ==============================================================================
# 平台检测
# ==============================================================================
SYSTEM = platform.system().lower()
IS_WINDOWS = SYSTEM == 'windows'
IS_MACOS = SYSTEM == 'darwin'
IS_LINUX = SYSTEM == 'linux'

# 条件导入 - 仅Windows需要
if IS_WINDOWS:
    import ctypes
    import winreg

# ==============================================================================
# Version Configuration
# ==============================================================================
APP_VERSION = "1.6.1"
FIRMWARE_COMPAT = "1.1.2"
APP_NAME = "SuperKey"
# ==============================================================================

def detect_system_theme() -> str:
    """跨平台检测系统主题"""
    if IS_WINDOWS:
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                         r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
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
        # Linux: 尝试检测GTK主题或使用环境变量
        try:
            gtk_theme = os.environ.get('GTK_THEME', '').lower()
            if 'dark' in gtk_theme:
                return "dark"
            # 尝试gsettings
            import subprocess
            result = subprocess.run(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'],
                capture_output=True, text=True
            )
            if 'dark' in result.stdout.lower():
                return "dark"
        except Exception:
            pass
        return "dark"  # Linux默认暗色
    return "dark"

class ThemeColors:
    def __init__(self):
        self.current_theme = detect_system_theme()
        self.colors = self._get_colors()
    
    def _get_colors(self):
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
                "ACCENT": "#2563EB",
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
                "BG_PRIMARY": "#111827",
                "BG_SECONDARY": "#1F2937",
                "BG_CARD": "#1F2937",
                "BG_SHELL": "#0F172A",
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
    
    def refresh_theme(self):
        new_theme = detect_system_theme()
        if new_theme != self.current_theme:
            self.current_theme = new_theme
            self.colors = self._get_colors()
            return True
        return False
    
    def get(self, key: str) -> str:
        return self.colors.get(key, "#000000")

def color_by_temp(t, theme: ThemeColors): 
    if t is None:
        return theme.get("TEXT_TERTIARY")
    elif t <= 60:
        return theme.get("GOOD")
    elif t <= 80:
        return theme.get("WARN")
    else:
        return theme.get("BAD")

def color_by_load(p, theme: ThemeColors):
    if p is None:
        return theme.get("TEXT_TERTIARY")
    elif p < 50:
        return theme.get("GOOD")
    elif p < 85:
        return theme.get("WARN")
    else:
        return theme.get("BAD")

# ==============================================================================
# Windows 特定的窗口效果函数
# ==============================================================================
def _find_hwnd_by_title(title: str, retry=20, delay=0.2):
    """Windows: 通过标题查找窗口句柄"""
    if not IS_WINDOWS:
        return 0
    user32 = ctypes.windll.user32
    for _ in range(retry):
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
        time.sleep(delay)
    return 0

def enable_mica(hwnd: int, kind: int = 2) -> bool:
    """Windows: 启用Mica效果"""
    if not IS_WINDOWS:
        return False
    try:
        dwmapi = ctypes.windll.dwmapi
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        val = ctypes.c_int(kind)
        r = dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), ctypes.c_uint(DWMWA_SYSTEMBACKDROP_TYPE),
                                         ctypes.byref(val), ctypes.sizeof(val))
        return r == 0
    except Exception:
        return False

def enable_acrylic(hwnd: int, is_light_theme: bool = False) -> bool:
    """Windows: 启用Acrylic效果"""
    if not IS_WINDOWS:
        return False
    try:
        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int),
                        ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_uint),
                        ("AnimationId", ctypes.c_int)]
        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int),
                        ("Data", ctypes.c_void_p),
                        ("SizeOfData", ctypes.c_size_t)]
        user32 = ctypes.windll.user32
        SetWindowCompositionAttribute = user32.SetWindowCompositionAttribute
        WCA_ACCENT_POLICY = 19
        ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
        
        if is_light_theme:
            gradient_color = 0x80F0F0F0
        else:
            gradient_color = 0x80101010
            
        policy = ACCENTPOLICY(ACCENT_ENABLE_ACRYLICBLURBEHIND, 0, ctypes.c_uint(gradient_color), 0)
        data = WINDOWCOMPOSITIONATTRIBDATA(WCA_ACCENT_POLICY, ctypes.byref(policy), ctypes.sizeof(policy))
        return SetWindowCompositionAttribute(ctypes.c_void_p(hwnd), ctypes.byref(data)) == 1
    except Exception:
        return False

def apply_backdrop_for_page(page: ft.Page, theme: ThemeColors, prefer_mica=True):
    """Windows: 应用窗口背景效果（仅Windows有效）"""
    if not IS_WINDOWS:
        return
    hwnd = _find_hwnd_by_title(page.title, retry=20, delay=0.2)
    if not hwnd:
        return
    ok = False
    if prefer_mica:
        ok = enable_mica(hwnd, 2) or enable_mica(hwnd, 3)
    if not ok:
        enable_acrylic(hwnd, theme.current_theme == "light")

# ==============================================================================
# 获取平台特定的图标路径
# ==============================================================================
def get_resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径，支持 PyInstaller 打包环境"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，资源在 _MEIPASS 目录中
        base_path = sys._MEIPASS
    else:
        # 开发环境，使用脚本所在目录
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_icon_path():
    """根据平台返回合适的图标路径"""
    if IS_WINDOWS:
        candidates = ["assets/app.ico", "app.ico"]
    elif IS_MACOS:
        candidates = ["assets/app.icns", "app.icns", "assets/app.png", "app.png"]
    else:
        candidates = ["assets/app.png", "app.png"]
    
    # 首先尝试打包环境路径
    for path in candidates:
        resource_path = get_resource_path(path)
        if os.path.exists(resource_path):
            return resource_path
    
    # 回退到相对路径（开发环境兼容）
    for path in candidates:
        if os.path.exists(path):
            return path
    
    return None

# ==============================================================================
# 导航项组件
# ==============================================================================
class NavigationItem:
    def __init__(self, icon: str, title: str, view_name: str, theme: ThemeColors, 
                 on_click_handler, icon_size: int = 24, is_separator: bool = False):
        self.icon = icon
        self.title = title
        self.view_name = view_name
        self.theme = theme
        self.on_click_handler = on_click_handler
        self.icon_size = icon_size
        self.is_separator = is_separator
        self.is_active = False
        
        if not is_separator:
            self.icon_btn = ft.IconButton(
                icon=icon,
                icon_color=theme.get("TEXT_SECONDARY"),
                icon_size=icon_size,
                tooltip=title,
                on_click=lambda e: self.on_click_handler(view_name)
            )
            
            self.text_label = ft.Text(
                title,
                size=14,
                color=theme.get("TEXT_SECONDARY"),
                visible=False
            )
            
            self.container = ft.Container(
                content=ft.Row([
                    self.icon_btn,
                    self.text_label
                ], spacing=12, tight=True),
                padding=ft.padding.symmetric(horizontal=4, vertical=4),
                border_radius=8,
                ink=True,
                on_click=lambda e: self.on_click_handler(view_name)
            )
        else:
            self.divider = ft.Divider(
                opacity=0.2, 
                thickness=1, 
                color=theme.get("DIVIDER")
            )
    
    def set_expanded(self, expanded: bool):
        if not self.is_separator:
            self.text_label.visible = expanded
            if expanded:
                self.icon_btn.style = ft.ButtonStyle(padding=ft.padding.all(8))
            else:
                self.icon_btn.style = ft.ButtonStyle(padding=ft.padding.all(12))
    
    def set_active(self, active: bool):
        if not self.is_separator:
            self.is_active = active
            if active:
                self.icon_btn.icon_color = self.theme.get("ACCENT")
                self.text_label.color = self.theme.get("ACCENT")
                self.container.bgcolor = self.theme.get("SIDEBAR_ACTIVE")
            else:
                self.icon_btn.icon_color = self.theme.get("TEXT_SECONDARY")
                self.text_label.color = self.theme.get("TEXT_SECONDARY")
                self.container.bgcolor = None
    
    def update_theme_colors(self, theme: ThemeColors):
        self.theme = theme
        if not self.is_separator:
            if self.is_active:
                self.icon_btn.icon_color = theme.get("ACCENT")
                self.text_label.color = theme.get("ACCENT")
                self.container.bgcolor = theme.get("SIDEBAR_ACTIVE")
            else:
                self.icon_btn.icon_color = theme.get("TEXT_SECONDARY")
                self.text_label.color = theme.get("TEXT_SECONDARY")
                self.container.bgcolor = None
        else:
            self.divider.color = theme.get("DIVIDER")

# ==============================================================================
# 主应用
# ==============================================================================
async def main(page: ft.Page):
    # 设置窗口图标（跨平台）
    icon_path = get_icon_path()
    if icon_path:
        page.window_icon = icon_path
    
    theme = ThemeColors()
    
    # 初始窗口设置
    page.window_width = 100
    page.window_height = 100
    page.update()
    
    time.sleep(0.1)   

    # 跨平台窗口配置
    if IS_WINDOWS:
        # Windows: 使用自定义标题栏
        page.window.title_bar_hidden = True
        page.window.frameless = False
        page.window.bgcolor = "#00000000"
        page.bgcolor = "#00000000"
    elif IS_MACOS:
        # macOS: 使用原生标题栏但自定义样式
        page.window.title_bar_hidden = False
        page.window.title_bar_buttons_hidden = False
        page.window.frameless = False
        page.bgcolor = ft.colors.TRANSPARENT
    else:
        # Linux: 使用系统默认样式
        page.window.title_bar_hidden = False
        page.window.frameless = False
        page.bgcolor = ft.colors.TRANSPARENT
    
    page.window.resizable = True
    page.window.maximizable = True
    page.window.minimizable = True
    
    page.window.width = 1400
    page.window.height = 900
    page.window.min_width = 800
    page.window.min_height = 600
    
    page.window.shadow = True
    page.padding = 0
    page.spacing = 0
    page.title = f"Build v{APP_VERSION} - {APP_NAME}"
    
    page.adaptive = True
    page.scroll = None

    hw_monitor = HardwareMonitor()
    config_mgr = get_config_manager()
    weather_cfg = config_mgr.get_weather_config()
    weather_api = WeatherAPI(
        api_key=weather_cfg.get('api_key', ''),
        default_city=weather_cfg.get('default_city', '北京'),
        api_host=weather_cfg.get('api_host', ''),
        use_jwt=weather_cfg.get('use_jwt', False)
    )
    serial_assistant = SerialAssistant()
    
    finsh_sender = FinshDataSender(
        serial_assistant=serial_assistant,
        weather_api=weather_api, 
        hardware_monitor=hw_monitor
    )

    # ==================== 系统托盘初始化 ====================
    system_tray = None
    app_state = {"force_quit": False}  # 标记是否强制退出
    
    def show_window():
        """显示窗口"""
        page.window.visible = True
        page.window.focused = True
        try:
            page.update()
        except:
            pass
    
    def cleanup_and_exit():
        """清理资源"""
        try:
            if finsh_sender.enabled:
                finsh_sender.stop()
            if serial_assistant.is_connected:
                serial_assistant.disconnect()
        except:
            pass
        if system_tray:
            system_tray.stop()
    
    def quit_app():
        """完全退出应用"""
        app_state["force_quit"] = True
        cleanup_and_exit()
        # 使用 Flet 正常关闭窗口，让它有机会清理临时目录
        page.window.destroy()
    
    def on_window_event(e):
        """处理窗口事件"""
        if e.data == "close":
            # 如果是强制退出，不做任何处理（让窗口正常关闭）
            if app_state["force_quit"]:
                return
            
            # 如果托盘可用且设置了最小化到托盘
            if system_tray and is_tray_available() and config_mgr.should_minimize_to_tray():
                page.window.visible = False
                page.update()
                if IS_MACOS:
                    system_tray.show_notification(APP_NAME, "App minimized to system tray")
                else:
                    system_tray.show_notification(APP_NAME, "程序已最小化到系统托盘")
            else:
                # 没有托盘或不最小化，直接退出
                quit_app()
    
    # 设置窗口事件处理（处理系统关闭按钮、Alt+F4等）
    page.window.prevent_close = True
    page.window.on_event = on_window_event
    
    # 初始化系统托盘
    if is_tray_available():
        tray_icon_path = get_icon_path()
        
        system_tray = SystemTray(
            app_name=f"{APP_NAME} v{APP_VERSION}",
            icon_path=tray_icon_path,
            on_show=show_window,
            on_quit=quit_app
        )
        system_tray.start()
    
    # ==================== 静默启动支持 ====================
    # 如果使用 --minimized 参数启动，则隐藏窗口到托盘
    if START_MINIMIZED and system_tray and is_tray_available():
        page.window.visible = False
        page.update()

    sidebar_expanded = {"value": False}

    def do_minimize(e):
        page.window.minimized = True
        page.update()

    def do_max_restore(e):
        page.window.maximized = not page.window.maximized
        page.update()

    def do_close(e):
        """关闭按钮 - 触发窗口关闭事件"""
        # 模拟窗口关闭，让 on_window_event 统一处理
        if system_tray and is_tray_available() and config_mgr.should_minimize_to_tray():
            page.window.visible = False
            page.update()
            if IS_MACOS:
                system_tray.show_notification(APP_NAME, "App minimized to system tray")
            else:
                system_tray.show_notification(APP_NAME, "程序已最小化到系统托盘")
        else:
            quit_app()

    # 标题栏按钮（仅Windows显示自定义按钮）
    title_buttons = ft.Row(
        [
            ft.IconButton(icon="remove", icon_color=theme.get("TEXT_SECONDARY"), 
                         tooltip="最小化", on_click=do_minimize),
            ft.IconButton(icon="crop_square", icon_color=theme.get("TEXT_SECONDARY"), 
                         tooltip="最大化/还原", on_click=do_max_restore),
            ft.IconButton(icon="close", icon_color=theme.get("TEXT_SECONDARY"), 
                         tooltip="关闭", on_click=do_close),
        ],
        spacing=0,
        visible=IS_WINDOWS,  # 仅Windows显示
    )
    
    logo_img = ft.Image(src="logo_484x74.png", height=28, width=180, fit=ft.ImageFit.CONTAIN)
    
    hamburger_btn = ft.IconButton(
        icon="menu",
        icon_color=theme.get("TEXT_SECONDARY"),
        tooltip="切换侧边栏",
        on_click=lambda e: toggle_sidebar()
    )
    
    # LHM状态指示器（仅Windows显示）
    lhm_state = ft.Text(
        "",
        size=10,
        color=theme.get("TEXT_TERTIARY"),
        visible=IS_WINDOWS
    )
    
    # 标题行布局
    title_row = ft.Container(
        content=ft.Row([
            hamburger_btn, 
            ft.Row([
                logo_img, 
                ft.Text(f"{APP_NAME} v{APP_VERSION}", color=theme.get("TEXT_SECONDARY"), size=14),
                lhm_state
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
    
    # Windows使用拖拽区域，其他平台直接使用容器
    if IS_WINDOWS:
        title_bar = ft.WindowDragArea(
            title_row,
            maximizable=True,
        )
    else:
        title_bar = title_row

    content_host = ft.Container(expand=True, bgcolor="transparent")
    current_view = {"name": "performance"}

    CARD_H_ROW1 = 260
    CARD_H_ROW2 = 260

    cpu_name = hw_monitor.get_cpu_name()
    cpu_title = ft.Text(cpu_name, size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
    cpu_bar = ft.ProgressBar(value=0, height=8, color=theme.get("ACCENT"), bgcolor=theme.get("BAR_BG_ALPHA"))
    cpu_usage = ft.Text("Load: —", size=13, color=theme.get("TEXT_SECONDARY"))
    cpu_temp = ft.Text("温度: —", size=12, color=theme.get("TEXT_TERTIARY"))
    cpu_clock = ft.Text("频率: —", size=12, color=theme.get("TEXT_TERTIARY"))
    cpu_power = ft.Text("功耗: —", size=12, color=theme.get("TEXT_TERTIARY"))
    cpu_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([ft.Icon(name="devices_other", color=theme.get("TEXT_SECONDARY")),
                    ft.Text("CPU", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))], spacing=8),
            cpu_title, cpu_bar, cpu_usage,
            ft.Row([cpu_temp, cpu_clock, cpu_power], spacing=16)
        ], spacing=8, expand=True),
        height=CARD_H_ROW1, padding=12, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    gpu_names = hw_monitor.gpu_names
    gpu_dd = ft.Dropdown(options=[ft.dropdown.Option(str(i), text=name) for i, name in enumerate(gpu_names)],
                        value="0", width=360, dense=True)
    gpu_bar = ft.ProgressBar(value=0, height=8, color=theme.get("ACCENT"), bgcolor=theme.get("BAR_BG_ALPHA"))
    gpu_usage = ft.Text("Load: —", size=13, color=theme.get("TEXT_SECONDARY"))
    gpu_temp = ft.Text("温度: —", size=12, color=theme.get("TEXT_TERTIARY"))
    gpu_clock = ft.Text("频率: —", size=12, color=theme.get("TEXT_TERTIARY"))
    gpu_mem = ft.Text("显存: —", size=12, color=theme.get("TEXT_TERTIARY"))
    gpu_power = ft.Text("功耗: —", size=12, color=theme.get("TEXT_TERTIARY"))
    gpu_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([ft.Icon(name="device_hub", color=theme.get("TEXT_SECONDARY")),
                    ft.Text("GPU", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
                    ft.Container(expand=True), gpu_dd], spacing=8),
            gpu_bar, gpu_usage,
            ft.Row([gpu_temp, gpu_clock, gpu_power], spacing=16),
            gpu_mem
        ], spacing=8, expand=True),
        height=CARD_H_ROW1, padding=12, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    mem_bar = ft.ProgressBar(value=0, height=8, color=theme.get("ACCENT"), bgcolor=theme.get("BAR_BG_ALPHA"))
    mem_pct = ft.Text("占用: —", size=13, color=theme.get("TEXT_SECONDARY"))
    mem_freq = ft.Text("频率: —", size=12, color=theme.get("TEXT_TERTIARY"))
    mem_used = ft.Text("已用/总计: —", size=12, color=theme.get("TEXT_TERTIARY"))
    mem_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([ft.Icon(name="memory", color=theme.get("TEXT_SECONDARY")),
                    ft.Text("内存", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))], spacing=8),
            mem_bar, mem_pct, mem_freq, mem_used
        ], spacing=8, expand=True),
        height=CARD_H_ROW2, padding=12, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    disk_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    storage_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([ft.Icon(name="storage", color=theme.get("TEXT_SECONDARY")),
                    ft.Text("存储", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))], spacing=8),
            disk_list
        ], spacing=8, expand=True),
        height=CARD_H_ROW2, padding=12, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    net_up = ft.Text("↑ —", size=13, color=theme.get("TEXT_SECONDARY"))
    net_dn = ft.Text("↓ —", size=13, color=theme.get("TEXT_SECONDARY"))
    net_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([ft.Icon(name="network_check", color=theme.get("TEXT_SECONDARY")),
                    ft.Text("网络", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))], spacing=8),
            ft.Row([net_up, net_dn], spacing=16)
        ], spacing=8, expand=True),
        height=CARD_H_ROW2, padding=12, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    # performance_view 将在天气组件定义后创建
    
    weather_api_key_field = ft.TextField(
        label="和风天气API密钥",
        value="",
        password=True,
        width=300,
        helper_text="在dev.qweather.com申请",
        on_change=lambda e: update_weather_config()
    )
    
    weather_api_host_field = ft.TextField(
        label="API Host",
        value="",
        width=300,
        helper_text="你可以在控制台-设置中查看你的API Host",
        on_change=lambda e: update_weather_config()
    )
    
    weather_use_jwt_switch = ft.Switch(
        label="使用JWT身份认证（测试）",
        value=False,
        on_change=lambda e: update_weather_config()
    )
    
    weather_default_city_field = ft.TextField(
        label="默认城市",
        value="杭州",
        width=200,
        helper_text="支持中文城市名",
        on_change=lambda e: update_weather_config()
    )
    
    weather_config_status = ft.Text(
        "配置状态: 未设置",
        size=12,
        color=theme.get("TEXT_TERTIARY")
    )
    
    def update_weather_config():
        api_key = weather_api_key_field.value.strip()
        api_host = weather_api_host_field.value.strip()
        default_city = weather_default_city_field.value.strip()
        use_jwt = weather_use_jwt_switch.value
        
        config_complete = bool(api_key and api_host and default_city)
        
        if config_complete:
            weather_config_status.value = "配置状态: 待保存"
            weather_config_status.color = theme.get("WARN")
            weather_save_btn.disabled = False
        else:
            weather_config_status.value = "配置状态: 不完整"
            weather_config_status.color = theme.get("BAD")
            weather_save_btn.disabled = True
        
        page.update()
    
    
    def save_weather_config():
        try:
            config_changed = weather_api.update_config(
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
    
    weather_save_btn = ft.ElevatedButton(
        "保存配置",
        icon="save",
        on_click=lambda e: save_weather_config(),
        disabled=True
    )
    
    weather_api_config_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="cloud", color=theme.get("TEXT_SECONDARY")),
                ft.Text("和风天气API配置", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            
            ft.Text("API认证", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
            ft.Row([
                weather_api_key_field,
                weather_api_host_field,
                weather_use_jwt_switch,
            ], spacing=12),
            
            ft.Text("城市设置", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
            ft.Row([
                weather_default_city_field,
                ft.Container(width=1),
                weather_save_btn,
                ft.Container(expand=True),
            ], spacing=12),
            
            weather_config_status,
        ], spacing=16),
        padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))
    
    weather_current_city = ft.Text("当前城市: --", size=16, color=theme.get("TEXT_SECONDARY"))
    weather_temp = ft.Text("--°C", size=48, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
    weather_feels_like = ft.Text("体感 --°C", size=16, color=theme.get("TEXT_SECONDARY"))
    weather_desc = ft.Text("获取中...", size=20, weight=ft.FontWeight.W_500, color=theme.get("TEXT_SECONDARY"))
    weather_quality = ft.Text("空气质量: --", size=14, color=theme.get("TEXT_TERTIARY"))
    weather_comfort = ft.Text("舒适度: --", size=14, color=theme.get("TEXT_TERTIARY"))
    
    weather_humidity = ft.Text("湿度: --%", size=14, color=theme.get("TEXT_TERTIARY"))
    weather_pressure = ft.Text("气压: --hPa", size=14, color=theme.get("TEXT_TERTIARY"))
    weather_visibility = ft.Text("能见度: --km", size=14, color=theme.get("TEXT_TERTIARY"))
    weather_precipitation = ft.Text("降水: --mm/h", size=14, color=theme.get("TEXT_TERTIARY"))
    weather_wind = ft.Text("风力: --", size=14, color=theme.get("TEXT_TERTIARY"))
    weather_cloud = ft.Text("云量: --%", size=14, color=theme.get("TEXT_TERTIARY"))
    weather_dew_point = ft.Text("露点: --°C", size=14, color=theme.get("TEXT_TERTIARY"))
    weather_uv_index = ft.Text("紫外线: --", size=14, color=theme.get("TEXT_TERTIARY"))
    
    weather_update_info = ft.Column([
        ft.Text("数据源: --", size=11, color=theme.get("TEXT_TERTIARY")),
        ft.Text("更新: --", size=11, color=theme.get("TEXT_TERTIARY")),
        ft.Text("观测: --", size=11, color=theme.get("TEXT_TERTIARY")),
    ], spacing=0)
    
    # 天气自动更新状态
    weather_state = {"last_update": time.time()}
    
    def update_weather():
        try:
            data = weather_api.get_formatted_data(force_refresh=True)
            
            weather_current_city.value = f"当前城市: {data['weather_city']}"
            weather_temp.value = f"{data['weather_temp']:.1f}°C"
            weather_feels_like.value = f"体感 {data['weather_feels_like']:.1f}°C"
            weather_desc.value = data['weather_desc']
            
            weather_quality.value = f"空气质量: {data['weather_quality']}"
            weather_comfort.value = f"舒适度: {data['weather_comfort_index']}"
            
            quality_color = theme.get("GOOD") if data['weather_quality'] in ["优秀", "良好"] else \
                           theme.get("WARN") if data['weather_quality'] == "一般" else theme.get("BAD")
            weather_quality.color = quality_color
            
            comfort_color = theme.get("GOOD") if "舒适" in data['weather_comfort_index'] else \
                           theme.get("WARN") if data['weather_comfort_index'] == "一般" else theme.get("BAD")
            weather_comfort.color = comfort_color
            
            weather_humidity.value = f"湿度: {data['weather_humidity']}%"
            weather_pressure.value = f"气压: {data['weather_pressure']:.0f}hPa"
            weather_visibility.value = f"能见度: {data['weather_visibility']:.1f}km"
            weather_precipitation.value = f"降水: {data['weather_precipitation']:.1f}mm/h"
            weather_wind.value = f"风力: {data['weather_wind_display']}"
            weather_cloud.value = f"云量: {data['weather_cloud_cover']}%"
            weather_dew_point.value = f"露点: {data['weather_dew_point']:.1f}°C"
            
            uv_value = "--"
            if data['weather_forecast'] and len(data['weather_forecast']) > 0:
                uv_value = str(data['weather_forecast'][0].get('uv_index', '--'))
            weather_uv_index.value = f"紫外线: {uv_value}"
            
            weather_update_info.controls[0].value = f"数据源: {data['weather_source']}"
            weather_update_info.controls[1].value = f"更新: {data['weather_update_time'][-8:] if data['weather_update_time'] else '--'}"
            weather_update_info.controls[2].value = f"观测: {data['weather_obs_time'][-8:] if data['weather_obs_time'] else '--'}"
            
            update_weather_forecast(data['weather_forecast'])
            
            # 更新天气刷新时间（手动刷新也会重置计时器）
            weather_state["last_update"] = time.time()
            
        except Exception as e:
            weather_current_city.value = f"当前城市: 获取失败"
            weather_temp.value = "--°C"
            weather_desc.value = f"错误: {str(e)}"
        
        page.update()
    
    weather_refresh_btn = ft.IconButton(
        icon="refresh",
        icon_color=theme.get("ACCENT"),
        tooltip="刷新天气",
        on_click=lambda e: update_weather()
    )
    
    weather_settings_btn = ft.IconButton(
        icon="settings",
        icon_color=theme.get("TEXT_SECONDARY"),
        tooltip="天气设置",
        on_click=lambda e: show_view("settings")
    )
    
    weather_main_card = ft.Card(ft.Container(
        content=ft.Column([
            # 标题行
            ft.Row([
                ft.Icon(name="wb_sunny", color=theme.get("TEXT_SECONDARY"), size=22),
                ft.Text("实时天气", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
                ft.Container(expand=True),
                weather_current_city,
                weather_settings_btn,
                weather_refresh_btn
            ], spacing=6),
            
            # 主内容区：三列平行布局
            ft.Row([
                # 左列：温度和天气描述
                ft.Column([
                    weather_temp,
                    weather_feels_like,
                    weather_desc,
                    ft.Container(height=2),
                    ft.Row([weather_quality, weather_comfort], spacing=12),
                ], horizontal_alignment="start", spacing=0, expand=2),
                
                # 中列：详细信息（左半部分）
                ft.Column([
                    weather_humidity,
                    weather_pressure,
                    weather_visibility,
                    weather_precipitation,
                ], spacing=4, expand=1),
                
                # 右列：详细信息（右半部分）+ 更新信息
                ft.Column([
                    weather_wind,
                    weather_cloud,
                    weather_dew_point,
                    weather_uv_index,
                    ft.Container(height=6),
                    weather_update_info,
                ], spacing=4, expand=1),
                
            ], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START),
            
        ], spacing=4),
        height=240, padding=12, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    forecast_container = ft.Column([], spacing=8)
    
    def update_weather_forecast(forecast_data):
        forecast_container.controls.clear()
        
        if not forecast_data:
            forecast_container.controls.append(
                ft.Text("暂无预报数据", size=14, color=theme.get("TEXT_TERTIARY"))
            )
            return
        
        for i, day_data in enumerate(forecast_data[:3]):
            date_str = day_data.get('date', '')
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
                except:
                    date_display = date_str
            else:
                date_display = f"第{i+1}天"
            
            forecast_row = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(date_display, size=14, weight=ft.FontWeight.W_500, 
                                      color=theme.get("TEXT_PRIMARY")),
                        width=60
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text(day_data.get('text_day', ''), size=12, color=theme.get("TEXT_SECONDARY")),
                            ft.Text(day_data.get('text_night', ''), size=11, color=theme.get("TEXT_TERTIARY")),
                        ], spacing=2),
                        width=80
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"{day_data.get('temp_max', 0)}° / {day_data.get('temp_min', 0)}°",
                            size=13, color=theme.get("TEXT_PRIMARY")
                        ),
                        width=80
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"{day_data.get('wind_dir_day', '')} {day_data.get('wind_scale_day', '')}级",
                            size=11, color=theme.get("TEXT_TERTIARY")
                        ),
                        width=70
                    ),
                    ft.Container(expand=True),
                    ft.Column([
                        ft.Text(f"湿度{day_data.get('humidity', 0)}%", size=10, color=theme.get("TEXT_TERTIARY")),
                        ft.Text(f"UV{day_data.get('uv_index', 0)}", size=10, color=theme.get("TEXT_TERTIARY")),
                    ], spacing=1),
                ], spacing=8),
                padding=ft.padding.all(8),
                border_radius=6,
                bgcolor=theme.get("BAR_BG_ALPHA") if i % 2 == 0 else None
            )
            
            forecast_container.controls.append(forecast_row)
    
    weather_forecast_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="date_range", color=theme.get("TEXT_SECONDARY"), size=20),
                ft.Text("天气预报", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            ft.Container(height=8),
            ft.Container(content=forecast_container, expand=True),
        ], spacing=8, expand=True),
        height=240, padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    # 性能监控视图（包含天气信息）
    performance_view = ft.Container(
        content=ft.Column(
            [
                ft.ResponsiveRow([
                    ft.Column([cpu_card], col={"xs":12, "md":6}),
                    ft.Column([gpu_card], col={"xs":12, "md":6}),
                ], columns=12),
                ft.ResponsiveRow([
                    ft.Column([mem_card], col={"xs":12, "md":3}),
                    ft.Column([storage_card], col={"xs":12, "md":6}),
                    ft.Column([net_card], col={"xs":12, "md":3}),
                ], columns=12),
                ft.ResponsiveRow([
                    ft.Column([weather_main_card], col={"xs":12, "md":8}),
                    ft.Column([weather_forecast_card], col={"xs":12, "md":4}),
                ], columns=12),
            ],
            spacing=8, expand=True, scroll=ft.ScrollMode.ADAPTIVE
        ),
        padding=12,
        expand=True
    )
    
    port_dropdown = ft.Dropdown(
        label="端口",
        width=250,
        options=[],
        dense=True,
        on_change=lambda e: on_port_selected(e.control.value)
    )
    
    def refresh_ports(e=None):
        ports = serial_assistant.get_available_ports()
        port_dropdown.options = [
            ft.dropdown.Option(p['port'], text=f"{p['port']} - {p['description']}")
            for p in ports
        ]
        if not serial_assistant.is_connected and ports:
            port_dropdown.value = ports[0]['port']
        page.update()
    
    refresh_port_btn = ft.IconButton(
        icon="refresh",
        icon_color=theme.get("ACCENT"),
        tooltip="刷新端口",
        on_click=refresh_ports
    )
    
    port_status_text = ft.Text(
        "未连接",
        size=12,
        color=theme.get("TEXT_TERTIARY")
    )
    # ==================== 自动重连回调 ====================
    def on_auto_reconnect(success: bool, port: str, is_reconnect: bool):
        """处理自动重连事件
        
        Args:
            success: 是否连接成功
            port: 端口名称
            is_reconnect: True表示重连，False表示启动时自动连接
        """
        if success:
            port_dropdown.value = port
            port_dropdown.disabled = True
            
            if is_reconnect:
                port_status_text.value = "已重连"
            else:
                port_status_text.value = "已连接"
            port_status_text.color = theme.get("GOOD")
            
            # 重新启动数据下发
            if not finsh_sender.enabled:
                finsh_sender.start()
            
            config_mgr.set_last_port(port)
        else:
            port_dropdown.disabled = False
            port_status_text.value = "连接断开"
            port_status_text.color = theme.get("WARN")
            finsh_sender.stop()
        
        try:
            page.update()
        except:
            pass
    
    def on_connection_changed(connected: bool):
        """处理连接状态变化"""
        if not connected:
            port_dropdown.disabled = False
            if not serial_assistant._manual_disconnect:
                port_status_text.value = "连接断开，正在重连..."
                port_status_text.color = theme.get("WARN")
            else:
                port_status_text.value = "已断开"
                port_status_text.color = theme.get("TEXT_TERTIARY")
            finsh_sender.stop()
        
        try:
            page.update()
        except:
            pass
    
    # 注册回调
    serial_assistant.on_auto_reconnect = on_auto_reconnect
    serial_assistant.on_connection_changed = on_connection_changed
    def on_port_selected(port: str):
        if not port:
            return
            
        # 如果已连接，先断开
        if serial_assistant.is_connected:
            finsh_sender.stop()
            serial_assistant.disconnect()
        
        # 配置固定参数：波特率1000000, 数据位8, 停止位1, 校验位N
        serial_assistant.configure(
            port=port,
            baudrate=1000000,
            bytesize=8,
            stopbits=1,
            parity='N'
        )
        
        # 自动连接
        if serial_assistant.connect():
            port_dropdown.disabled = True
            port_status_text.value = "已连接"
            port_status_text.color = theme.get("GOOD")
            
            # 自动启动数据下发
            finsh_sender.start()
            config_mgr.set_last_port(port)
        else:
            port_status_text.value = "连接失败"
            port_status_text.color = theme.get("BAD")
        
        page.update()
    
    def disconnect_port(e=None):
        if serial_assistant.is_connected:
            finsh_sender.stop()
            serial_assistant.disconnect()
            port_dropdown.disabled = False
            port_status_text.value = "已断开"
            port_status_text.color = theme.get("TEXT_TERTIARY")
            page.update()
    
    disconnect_btn = ft.IconButton(
        icon="link_off",
        icon_color=theme.get("TEXT_SECONDARY"),
        tooltip="断开连接",
        on_click=disconnect_port
    )
    
    serial_config_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="usb", color=theme.get("TEXT_SECONDARY")),
                ft.Text("串口连接", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            ft.Row([port_dropdown, refresh_port_btn, disconnect_btn], spacing=4),
            port_status_text,
        ], spacing=12),
        padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))
    
    refresh_ports()
    
    # 启动自动重连功能
    serial_assistant.enable_auto_reconnect(enabled=True, interval=2.0)
    
    # 自动连接上次使用的串口（静默方式）
    if config_mgr.should_auto_connect():
        last_port = config_mgr.get_last_port()
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

    # ==================== 应用设置卡片 ====================
    def on_minimize_to_tray_changed(e):
        config_mgr.set_minimize_to_tray(e.control.value)
    
    def on_auto_start_changed(e):
        enabled = e.control.value
        success = AutoStartManager.set_enabled(enabled)
        if success:
            config_mgr.set_auto_start(enabled)
        else:
            # 如果失败，恢复开关状态
            e.control.value = AutoStartManager.is_enabled()
            page.update()
    
    minimize_to_tray_switch = ft.Switch(
        label="关闭窗口时最小化到系统托盘",
        value=config_mgr.should_minimize_to_tray(),
        on_change=on_minimize_to_tray_changed,
        disabled=not is_tray_available()
    )
    
    auto_start_switch = ft.Switch(
        label="开机自动启动",
        value=AutoStartManager.is_enabled(),
        on_change=on_auto_start_changed
    )
    
    # 根据平台显示不同的提示信息
    if is_tray_available():
        tray_hint_text = "提示: 最小化到托盘后，可在系统托盘图标右键菜单中显示窗口或退出"
        tray_hint_color = theme.get("TEXT_TERTIARY")
    else:
        if IS_LINUX:
            tray_hint_text = "提示: 系统托盘功能需要安装 pystray 和 Pillow 库，且需要显示服务器支持"
        else:
            tray_hint_text = "提示: 系统托盘功能需要安装 pystray 和 Pillow 库"
        tray_hint_color = theme.get("WARN")
    
    app_settings_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="settings_applications", color=theme.get("TEXT_SECONDARY")),
                ft.Text("应用设置", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            ft.Container(height=8),
            minimize_to_tray_switch,
            auto_start_switch,
            ft.Container(height=8),
            ft.Text(tray_hint_text, size=11, color=tray_hint_color),
        ], spacing=8),
        padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    settings_view = ft.Container(
        content=ft.Column([
            ft.Text("设置", size=24, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
            ft.Container(height=20),
            serial_config_card,
            ft.Container(height=20),
            weather_api_config_card,
            ft.Container(height=20),
            app_settings_card,
            ft.Container(height=20),
        ], spacing=16, scroll=ft.ScrollMode.ADAPTIVE, expand=True),
        padding=20,
        expand=True
    )

    # 关于页面：根据平台显示不同的工具名称
    platform_name = "Windows" if IS_WINDOWS else ("macOS" if IS_MACOS else "Linux")
    
    about_view = ft.Container(
        content=ft.Column([
            ft.Text("关于", size=24, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
            ft.Text(f"SuperKey_{platform_name}支持工具", size=16, color=theme.get("TEXT_SECONDARY")),
            ft.Text(f"Build v{APP_VERSION} - 适配固件{FIRMWARE_COMPAT}版本", size=14, color=theme.get("TEXT_TERTIARY")),
            ft.Container(height=20),
            ft.Text("制作团队", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
            ft.Text("• 解博文 xiebowen1@outlook.com", size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Text("• 蔡松 19914553473@163.com", size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Text("• 郭雨十 2361768748@qq.com", size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Text("• 思澈科技（南京）提供技术支持", size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Container(height=20),
            ft.Text("更新日志 2025年12月9日", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
            ft.Text("• 修复：天气信息自动更新，APP自动获取权限"size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Text("• 新增：开机自启，自动检测与连接，配置保存，后台运行，自定义按键配置",size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Text("• 删除：复杂的串口配置页面和数据下发间隔配置", size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Text("• 本次更新与旧版本固件部分兼容", size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Container(height=20),
            ft.Text("开源协议", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
            ft.Text("• Apache-2.0", size=12, color=theme.get("TEXT_TERTIARY")),
        ], spacing=8),
        padding=20,
        expand=True
    )

    # ==================== 自定义按键视图 ====================
    custom_key_manager = None
    custom_key_status = ft.Text("", size=12, color=theme.get("TEXT_TERTIARY"))
    
    def create_custom_key_view():
        """创建自定义按键配置视图 - 支持自由编辑4个组合键"""
        nonlocal custom_key_manager
        
        # 初始化管理器
        def send_command(cmd: str) -> bool:
            if serial_assistant and serial_assistant.is_connected:
                try:
                    serial_assistant.send_data(cmd + "\r\n")
                    return True
                except:
                    return False
            return False
        
        custom_key_manager = get_custom_key_manager(send_command)
        
        # 获取选项列表
        key_options = get_all_key_options()
        modifier_options = get_modifier_options()
        
        # 创建下拉选项
        key_dropdown_options = [ft.dropdown.Option(text=name, key=str(code)) for name, code in key_options]
        modifier_dropdown_options = [ft.dropdown.Option(text=name, key=str(val)) for name, val in modifier_options]
        preset_options = [ft.dropdown.Option(name) for name in PRESET_SHORTCUTS.keys()]
        
        # 存储UI控件引用
        combo_controls = {}  # {(key_idx, combo_idx): {"mod": dropdown, "key": dropdown}}
        key_summary_texts = {}  # {key_idx: Text}
        
        def update_status(msg: str, is_error: bool = False):
            custom_key_status.value = msg
            custom_key_status.color = theme.get("BAD") if is_error else theme.get("GOOD")
            page.update()
        
        def refresh_key_summary(key_idx: int):
            """刷新按键摘要显示"""
            if key_idx in key_summary_texts:
                parts = []
                for ci in range(4):
                    text = custom_key_manager.get_combo_display_text(key_idx, ci)
                    if text != "无":
                        parts.append(f"[{ci+1}]{text}")
                key_summary_texts[key_idx].value = " → ".join(parts) if parts else "未配置"
                page.update()
        
        def on_modifier_change(key_idx: int, combo_idx: int):
            def handler(e):
                mod_value = int(e.control.value) if e.control.value else 0
                _, current_keycode = custom_key_manager.get_combo(key_idx, combo_idx)
                custom_key_manager.set_combo(key_idx, combo_idx, mod_value, current_keycode)
                refresh_key_summary(key_idx)
            return handler
        
        def on_keycode_change(key_idx: int, combo_idx: int):
            def handler(e):
                keycode = int(e.control.value) if e.control.value else 0
                current_mod, _ = custom_key_manager.get_combo(key_idx, combo_idx)
                custom_key_manager.set_combo(key_idx, combo_idx, current_mod, keycode)
                refresh_key_summary(key_idx)
            return handler
        
        def on_preset_change(key_idx: int):
            def handler(e):
                preset_name = e.control.value
                if preset_name:
                    custom_key_manager.set_key_from_preset(key_idx, preset_name)
                    # 更新UI控件显示
                    for ci in range(4):
                        mod, keycode = custom_key_manager.get_combo(key_idx, ci)
                        if (key_idx, ci) in combo_controls:
                            combo_controls[(key_idx, ci)]["mod"].value = str(mod)
                            combo_controls[(key_idx, ci)]["key"].value = str(keycode)
                    refresh_key_summary(key_idx)
                    update_status(f"已应用预设: {preset_name}")
            return handler
        
        def on_apply_click(key_idx: int):
            def handler(e):
                if custom_key_manager.sync_key_to_device(key_idx):
                    update_status(f"按键{key_idx+1} 已同步到设备")
                else:
                    update_status("同步失败，请检查串口连接", True)
            return handler
        
        def on_clear_click(key_idx: int):
            def handler(e):
                custom_key_manager.clear_key(key_idx)
                # 清空UI控件
                for ci in range(4):
                    if (key_idx, ci) in combo_controls:
                        combo_controls[(key_idx, ci)]["mod"].value = "0"
                        combo_controls[(key_idx, ci)]["key"].value = "0"
                refresh_key_summary(key_idx)
                update_status(f"已清除 按键{key_idx+1}")
            return handler
        
        def on_sync_all_click(e):
            if custom_key_manager.sync_all_to_device():
                update_status("所有配置已同步到设备")
            else:
                update_status("同步失败，请检查串口连接", True)
        
        # 创建单个组合键编辑行
        def create_combo_row(key_idx: int, combo_idx: int):
            current_mod, current_keycode = custom_key_manager.get_combo(key_idx, combo_idx)
            
            mod_dropdown = ft.Dropdown(
                label=f"修饰键",
                options=modifier_dropdown_options,
                value=str(current_mod),
                on_change=on_modifier_change(key_idx, combo_idx),
                width=120,
                dense=True,
                text_size=12,
            )
            
            key_dropdown = ft.Dropdown(
                label=f"按键",
                options=key_dropdown_options,
                value=str(current_keycode),
                on_change=on_keycode_change(key_idx, combo_idx),
                width=100,
                dense=True,
                text_size=12,
            )
            
            combo_controls[(key_idx, combo_idx)] = {"mod": mod_dropdown, "key": key_dropdown}
            
            return ft.Row([
                ft.Text(f"{combo_idx+1}.", size=12, color=theme.get("TEXT_TERTIARY"), width=20),
                mod_dropdown,
                ft.Text("+", size=12, color=theme.get("TEXT_TERTIARY")),
                key_dropdown,
            ], spacing=4, alignment=ft.MainAxisAlignment.START)
        
        # 创建单个按键配置卡片
        def create_key_card(key_idx: int):
            # 预设快捷选择
            preset_dropdown = ft.Dropdown(
                label="快捷预设",
                options=preset_options,
                on_change=on_preset_change(key_idx),
                width=180,
                dense=True,
                text_size=12,
            )
            
            # 4个组合键编辑行
            combo_rows = [create_combo_row(key_idx, ci) for ci in range(4)]
            
            # 当前配置摘要
            summary_text = ft.Text(
                custom_key_manager.get_key_display_text(key_idx),
                size=11,
                color=theme.get("GOOD"),
                italic=True,
            )
            key_summary_texts[key_idx] = summary_text
            refresh_key_summary(key_idx)
            
            # 操作按钮
            apply_btn = ft.ElevatedButton(
                "同步到设备",
                icon="sync",
                on_click=on_apply_click(key_idx),
                style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=8, vertical=4)),
            )
            clear_btn = ft.TextButton(
                "清除",
                on_click=on_clear_click(key_idx),
            )
            
            return ft.Container(
                content=ft.Column([
                    # 标题栏
                    ft.Row([
                        ft.Icon("keyboard", size=16, color=theme.get("TEXT_SECONDARY")),
                        ft.Text(f"按键 {key_idx + 1}", size=14, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
                    ], spacing=6),
                    ft.Divider(height=1, color=theme.get("BORDER")),
                    # 预设选择
                    preset_dropdown,
                    # 4个组合键
                    ft.Text("自定义映射 (按顺序执行):", size=11, color=theme.get("TEXT_TERTIARY")),
                    *combo_rows,
                    # 摘要
                    ft.Container(
                        content=summary_text,
                        padding=ft.padding.only(top=4),
                    ),
                    # 操作按钮
                    ft.Row([apply_btn, clear_btn], spacing=8),
                ], spacing=6),
                padding=12,
                bgcolor=theme.get("BAR_BG_ALPHA"),
                border_radius=8,
                width=280,
            )
        
        # 创建3个按键卡片
        key_cards = ft.Row(
            [create_key_card(ki) for ki in range(3)],
            spacing=16,
            wrap=True,
            alignment=ft.MainAxisAlignment.START,
        )
        
        sync_all_btn = ft.ElevatedButton(
            "同步所有到设备",
            icon="sync",
            on_click=on_sync_all_click,
        )
        
        # 使用说明
        help_text = ft.Container(
            content=ft.Column([
                ft.Text("使用说明:", size=12, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
                ft.Text("• 每个按键支持4个组合键，按顺序依次执行", size=11, color=theme.get("TEXT_TERTIARY")),
                ft.Text("• 可选择预设快捷键快速配置，或自定义每个映射", size=11, color=theme.get("TEXT_TERTIARY")),
                ft.Text("• 修改后需点击「同步到设备」才能生效", size=11, color=theme.get("TEXT_TERTIARY")),
            ], spacing=2),
            padding=ft.padding.only(top=8),
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(name="keyboard", color=theme.get("TEXT_SECONDARY")),
                    ft.Text("自定义按键配置", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
                    ft.Container(expand=True),
                    sync_all_btn,
                ], spacing=8),
                ft.Text("配置设备第5页的3个自定义按键，每个按键支持4个连续组合键", size=12, color=theme.get("TEXT_TERTIARY")),
                ft.Container(height=12),
                key_cards,
                help_text,
                ft.Container(height=8),
                custom_key_status,
            ], spacing=8, scroll=ft.ScrollMode.AUTO),
            padding=20,
            expand=True,
        )
    
    custom_key_view = None  # 延迟创建

    def show_view(name: str):
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
        except Exception as e:
            print(f"视图切换错误: {e}")
            import traceback
            traceback.print_exc()
        
        for nav_item in nav_items:
            if not nav_item.is_separator:
                nav_item.set_active(nav_item.view_name == name)
        
        page.update()

    nav_items = [
        NavigationItem("speed", "监控", "performance", theme, show_view, 24),
        NavigationItem("keyboard", "按键", "custom_key", theme, show_view, 20),
        NavigationItem("", "", "", theme, None, is_separator=True),
        NavigationItem("settings", "设置", "settings", theme, show_view, 20),
        NavigationItem("info_outline", "关于", "about", theme, show_view, 20),
    ]
    
    nav_items[0].set_active(True)
    
    def toggle_sidebar():
        sidebar_expanded["value"] = not sidebar_expanded["value"]
        
        if sidebar_expanded["value"]:
            nav_holder.width = 150
        else:
            nav_holder.width = 72
        
        for nav_item in nav_items:
            if not nav_item.is_separator:
                nav_item.set_expanded(sidebar_expanded["value"])
        
        page.update()

    nav_controls = []
    nav_controls.append(ft.Container(height=8))
    
    # 添加监控和按键导航项（分隔符之前的项）
    for i, nav_item in enumerate(nav_items[:2]):
        nav_controls.append(ft.Container(
            content=nav_item.container,
            padding=ft.padding.symmetric(horizontal=8, vertical=2)
        ))
    
    nav_controls.append(ft.Container(expand=True))
    
    # 添加分隔符 (现在是 nav_items[2])
    nav_controls.append(ft.Container(
        content=nav_items[2].divider,
        padding=ft.padding.symmetric(horizontal=12, vertical=8)
    ))
    
    # 添加设置和关于 (nav_items[3:])
    for nav_item in nav_items[3:]:
        nav_controls.append(ft.Container(
            content=nav_item.container,
            padding=ft.padding.symmetric(horizontal=8, vertical=2)
        ))
    
    nav_controls.append(ft.Container(height=8))

    nav_holder = ft.Container(
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

    main_row = ft.Row(
        [nav_holder, ft.Container(content_host, expand=True, padding=0, margin=0)],
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        spacing=0
    )

    content_column = ft.Column([title_bar, main_row], spacing=0, expand=True)

    # 跨平台背景颜色设置
    if IS_WINDOWS:
        # Windows: 使用半透明背景配合Mica/Acrylic效果
        if theme.current_theme == "light":
            shell_bg = "#EEF0F0F0"
        else:
            shell_bg = "#EE0E0E10"
    else:
        # macOS/Linux: 使用纯色背景
        if theme.current_theme == "light":
            shell_bg = "#F0F0F0"
        else:
            shell_bg = "#1A1A1A"
    
    shell = ft.Container(
        content=content_column,
        bgcolor=shell_bg,
        expand=True,
        padding=0,
        margin=0,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS
    )
    
    page.add(shell)

    show_view("performance")

    def initialize_weather_config():
        config = weather_api.get_config()
        
        weather_api_key_field.value = config.get('api_key', '')
        weather_api_host_field.value = config.get('api_host', '')
        weather_use_jwt_switch.value = config.get('use_jwt', False)
        weather_default_city_field.value = config.get('default_city', '城市名')
        
        update_weather_config()
    
    initialize_weather_config()
    
    # 如果天气API已配置，自动刷新天气数据
    if weather_api.get_config().get('api_configured', False):
        try:
            update_weather()
        except:
            pass

    def build_disks(items):
        disk_list.controls.clear()
        for d in items:
            used, size = d["used"], d["size"]
            pct = (used/size) if size else 0
            bar = ft.ProgressBar(value=pct, height=6, color=theme.get("ACCENT"), bgcolor=theme.get("BAR_BG_ALPHA"))
            t_model = ft.Text(d["model"], size=14, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
            t_usage = ft.Text(f"{bytes2human(used)} / {bytes2human(size)}  ({pct*100:.0f}%)",
                              size=12, color=theme.get("TEXT_SECONDARY"))
            t_speed = ft.Text("读: —   写: —", size=12, color=theme.get("TEXT_TERTIARY"))
            row = ft.Container(content=ft.Column([t_model, bar, t_usage, t_speed], spacing=4),
                               padding=8, border_radius=8, bgcolor=theme.get("BAR_BG_ALPHA"))
            row._speed = t_speed
            disk_list.controls.append(row)
        page.update()

    build_disks(hw_monitor.get_disk_data())

    async def apply_backdrop_only():
        """仅应用背景效果，不调整窗口尺寸（仅Windows有效）"""
        if IS_WINDOWS:
            await asyncio.sleep(0.8)
            apply_backdrop_for_page(page, theme, prefer_mica=True)

    page.run_task(apply_backdrop_only)

    def update_all_theme_colors():
        
        lhm_state.color = theme.get("TEXT_TERTIARY")
        hamburger_btn.icon_color = theme.get("TEXT_SECONDARY")
        for btn in title_buttons.controls:
            btn.icon_color = theme.get("TEXT_SECONDARY")
        
        nav_holder.border = ft.border.only(right=ft.BorderSide(1, theme.get("DIVIDER")))
        
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
            if hasattr(disk_container, 'content') and hasattr(disk_container.content, 'controls'):
                disk_container.bgcolor = theme.get("BAR_BG_ALPHA")
                for ctrl in disk_container.content.controls:
                    if hasattr(ctrl, 'color'):
                        if hasattr(ctrl, 'weight') and ctrl.weight == ft.FontWeight.BOLD:
                            ctrl.color = theme.get("TEXT_PRIMARY")
                        elif isinstance(ctrl, ft.ProgressBar):
                            ctrl.color = theme.get("ACCENT")
                            ctrl.bgcolor = theme.get("BAR_BG_ALPHA")
                        else:
                            ctrl.color = theme.get("TEXT_SECONDARY")
        
        net_up.color = theme.get("TEXT_SECONDARY")
        net_dn.color = theme.get("TEXT_SECONDARY")
        net_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        
        weather_current_city.color = theme.get("TEXT_SECONDARY")
        weather_temp.color = theme.get("TEXT_PRIMARY")
        weather_feels_like.color = theme.get("TEXT_SECONDARY")
        weather_desc.color = theme.get("TEXT_SECONDARY")
        weather_refresh_btn.icon_color = theme.get("ACCENT")
        weather_settings_btn.icon_color = theme.get("TEXT_SECONDARY")
        weather_main_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        
        for ctrl in [weather_humidity, weather_pressure, weather_visibility, 
                     weather_precipitation, weather_wind, weather_cloud, 
                     weather_dew_point, weather_uv_index]:
            ctrl.color = theme.get("TEXT_TERTIARY")
        
        for ctrl in weather_update_info.controls:
            ctrl.color = theme.get("TEXT_TERTIARY")
        
        weather_forecast_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        
        serial_config_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        
        weather_api_config_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        weather_config_status.color = theme.get("TEXT_TERTIARY")
        
        if hasattr(settings_view, 'content') and hasattr(settings_view.content, 'controls'):
            for ctrl in settings_view.content.controls:
                if hasattr(ctrl, 'color'):
                    if hasattr(ctrl, 'size') and ctrl.size == 24:
                        ctrl.color = theme.get("TEXT_PRIMARY")
                    else:
                        ctrl.color = theme.get("TEXT_TERTIARY")
        
        if hasattr(about_view, 'content') and hasattr(about_view.content, 'controls'):
            for ctrl in about_view.content.controls:
                if hasattr(ctrl, 'color'):
                    if hasattr(ctrl, 'size'):
                        if ctrl.size == 24:
                            ctrl.color = theme.get("TEXT_PRIMARY")
                        elif ctrl.size == 16:
                            ctrl.color = theme.get("TEXT_SECONDARY")
                        else:
                            ctrl.color = theme.get("TEXT_TERTIARY")
        
        # 跨平台背景颜色更新
        if IS_WINDOWS:
            if theme.current_theme == "light":
                shell.bgcolor = "#EEF0F0F0"
            else:
                shell.bgcolor = "#EE0E0E10"
        else:
            if theme.current_theme == "light":
                shell.bgcolor = "#F0F0F0"
            else:
                shell.bgcolor = "#1A1A1A"

    async def updater():
        weather_update_interval = 30 * 60  # 天气更新间隔：30分钟
        
        while True:
            t0 = time.time()
            
            if theme.refresh_theme():
                update_all_theme_colors()
                
                if current_view["name"] == "performance":
                    dlist = hw_monitor.get_disk_data()
                    build_disks(dlist)
                
                try:
                    await page.update_async()
                except Exception:
                    page.update()
                
                await asyncio.sleep(0.2)
                if IS_WINDOWS:
                    apply_backdrop_for_page(page, theme, prefer_mica=True)
            
            # ==================== 天气自动更新 ====================
            if t0 - weather_state["last_update"] > weather_update_interval:
                if weather_api.get_config().get('api_configured', False):
                    try:
                        update_weather()
                        # update_weather 内部已经更新了 weather_state["last_update"]
                    except Exception:
                        pass  # 静默失败，下次再试
            
            if current_view["name"] == "performance":
                c = hw_monitor.get_cpu_data()
                cpu_bar.value = (c.get("usage", 0) or 0) / 100.0
                cpu_usage.value = f"Load: {pct_str(c.get('usage'))}"
                cpu_usage.color = color_by_load(c.get("usage"), theme)
                cpu_temp.value = f"温度: {temp_str(c.get('temp'))}"
                cpu_temp.color = color_by_temp(c.get("temp"), theme)
                cpu_clock.value = f"频率: {mhz_str(c.get('clock_mhz'))}"
                cpu_power.value = f"功耗: {watt_str(c.get('power'))}"

                sel = int(gpu_dd.value or 0)
                g = hw_monitor.get_gpu_data(sel)
                util = g.get("util")
                gpu_bar.value = (util or 0) / 100.0
                gpu_usage.value = f"Load: {pct_str(util)}"
                gpu_usage.color = color_by_load(util, theme)
                gpu_temp.value = f"温度: {temp_str(g.get('temp'))}"
                gpu_temp.color = color_by_temp(g.get("temp"), theme)
                gpu_clock.value = f"频率: {mhz_str(g.get('clock_mhz'))}"
                if g.get("mem_total_b") is not None and g.get("mem_used_b") is not None:
                    gpu_mem.value = f"显存: {bytes2human(g['mem_used_b'])} / {bytes2human(g['mem_total_b'])}"
                else:
                    gpu_mem.value = "显存: —"
                gpu_power.value = f"功耗: {watt_str(g.get('power'))}"

                m = hw_monitor.get_memory_data()
                mem_bar.value = (m["percent"] or 0) / 100.0
                mem_pct.value = f"占用: {pct_str(m['percent'])}"
                mem_used.value = f"已用/总计: {bytes2human(m['used_b'])} / {bytes2human(m['total_b'])}"
                mem_freq.value = f"频率: {mhz_str(m['freq_mhz'])}"

                dlist = hw_monitor.get_disk_data()
                if len(dlist) != len(disk_list.controls):
                    build_disks(dlist)
                for i, d in enumerate(dlist):
                    if i < len(disk_list.controls):
                        rb, wb = d["rps"], d["wps"]
                        disk_list.controls[i]._speed.value = f"读: {bytes2human(rb) + '/s' if rb is not None else '—'}    写: {bytes2human(wb) + '/s' if wb is not None else '—'}"

                n = hw_monitor.get_network_data()
                net_up.value = f"↑ {bytes2human(n['up'])}/s" if n["up"] is not None else "↑ —"
                net_dn.value = f"↓ {bytes2human(n['down'])}/s" if n["down"] is not None else "↓ —"

            try:
                await page.update_async()
            except Exception:
                page.update()

            await asyncio.sleep(max(0, 1.0 - (time.time() - t0)))

    page.run_task(updater)

ft.app(
    target=main, 
    view=ft.AppView.FLET_APP, 
    assets_dir="assets",
    use_color_emoji=True,
)