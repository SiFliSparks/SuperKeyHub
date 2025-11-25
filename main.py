#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, time, asyncio, ctypes, math, winreg
import flet as ft
import sys
import os

from hw_monitor import HardwareMonitor, bytes2human, pct_str, mhz_str, temp_str, watt_str
from weather_api import QWeatherAPI as WeatherAPI
from stock_api import StockAPI
from serial_assistant import SerialAssistant, DataFormat
from finsh_data_sender import FinshDataSender

def detect_windows_theme() -> str:
    if os.name != "nt":
        return "dark"
    
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                     r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(registry_key, "AppsUseLightTheme")
        winreg.CloseKey(registry_key)
        return "light" if value else "dark"
    except Exception:
        return "dark"

class ThemeColors:
    def __init__(self):
        self.current_theme = detect_windows_theme()
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
        new_theme = detect_windows_theme()
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

def _find_hwnd_by_title(title: str, retry=20, delay=0.2):
    if os.name != "nt": return 0
    user32 = ctypes.windll.user32
    for _ in range(retry):
        hwnd = user32.FindWindowW(None, title)
        if hwnd: return hwnd
        time.sleep(delay)
    return 0

def enable_mica(hwnd: int, kind: int = 2) -> bool:
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
    if os.name != "nt": return
    hwnd = _find_hwnd_by_title(page.title, retry=20, delay=0.2)
    if not hwnd: return
    ok = False
    if prefer_mica:
        ok = enable_mica(hwnd, 2) or enable_mica(hwnd, 3)
    if not ok:
        enable_acrylic(hwnd, theme.current_theme == "light")

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

async def main(page: ft.Page):
    page.window_icon = "assets/app.ico"
    theme = ThemeColors()
    page.window_width = 100
    page.window_height = 100
    page.update()
    
    import time
    time.sleep(0.1)   

    page.window.title_bar_hidden = True
    page.window.frameless = False
    page.window.resizable = True
    page.window.maximizable = True
    page.window.minimizable = True
    
    page.window.width = 1400
    page.window.height = 900
    page.window.min_width = 800
    page.window.min_height = 600
    
    page.window.bgcolor = "#00000000"
    page.window.shadow = True
    page.bgcolor = "#00000000"
    page.padding = 0
    page.spacing = 0
    page.title = "Build v1.1.0 - SuperKey"
    
    page.adaptive = True
    page.scroll = None

    hw_monitor = HardwareMonitor()
    weather_api = WeatherAPI()
    stock_api = StockAPI(default_symbol="1010")
    serial_assistant = SerialAssistant()
    
    finsh_sender = FinshDataSender(
        serial_assistant=serial_assistant,
        weather_api=weather_api, 
        stock_api=stock_api,
        hardware_monitor=hw_monitor
    )

    sidebar_expanded = {"value": False}

    def do_minimize(e):
        page.window.minimized = True
        page.update()

    def do_max_restore(e):
        page.window.maximized = not page.window.maximized
        page.update()

    def do_close(e):
        try:
            if finsh_sender.enabled:
                finsh_sender.stop()
            page.window.close()
        except Exception:
            os._exit(0)

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
    )
    
    logo_img = ft.Image(src="logo_484x74.png", height=28, width=180, fit=ft.ImageFit.CONTAIN)
    
    hamburger_btn = ft.IconButton(
        icon="menu",
        icon_color=theme.get("TEXT_SECONDARY"),
        tooltip="切换侧边栏",
        on_click=lambda e: toggle_sidebar()
    )
    
    title_row = ft.Container(
        content=ft.Row([
            hamburger_btn, 
            ft.Row([logo_img, ft.Text("SuperKey v1.1.0", color=theme.get("TEXT_SECONDARY"), size=14)], spacing=10),
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
    
    title_bar = ft.WindowDragArea(
        title_row,
        maximizable=True,
    )

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
            ],
            spacing=8, expand=True, scroll=ft.ScrollMode.ADAPTIVE
        ),
        padding=12,
        expand=True
    )
    
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
        ft.Text("数据源: --", size=12, color=theme.get("TEXT_TERTIARY")),
        ft.Text("更新: --", size=12, color=theme.get("TEXT_TERTIARY")),
        ft.Text("观测: --", size=12, color=theme.get("TEXT_TERTIARY")),
    ], spacing=2)
    
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
            ft.Row([
                ft.Icon(name="wb_sunny", color=theme.get("TEXT_SECONDARY"), size=24),
                ft.Text("实时天气", size=20, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
                ft.Container(expand=True),
                weather_current_city,
                weather_settings_btn,
                weather_refresh_btn
            ], spacing=8),
            
            ft.Container(height=8),
            
            ft.Row([
                ft.Column([
                    weather_temp,
                    weather_feels_like,
                    weather_desc,
                ], horizontal_alignment="start", spacing=4),
                
                ft.Container(width=40),
                
                ft.Column([
                    weather_quality,
                    weather_comfort,
                    ft.Container(height=20),
                    weather_update_info
                ], horizontal_alignment="start", spacing=4),
            ], alignment="start"),
            
            ft.Container(height=12),
            
            ft.Column([
                ft.Text("详细信息", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
                ft.Container(height=8),
                ft.Row([
                    ft.Column([
                        weather_humidity,
                        weather_pressure,
                        weather_visibility,
                        weather_precipitation,
                    ], spacing=8, expand=True),
                    
                    ft.Column([
                        weather_wind,
                        weather_cloud,
                        weather_dew_point,
                        weather_uv_index,
                    ], spacing=8, expand=True),
                ], spacing=20),
            ])
        ], spacing=8, expand=True),
        height=480, padding=20, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=12
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
        height=280, padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    stock_index_dropdown = ft.Dropdown(
        options=[
            ft.dropdown.Option("1010", text="上证指数"),
            ft.dropdown.Option("1011", text="深证成指"),
            ft.dropdown.Option("1012", text="沪深300"),
            ft.dropdown.Option("1013", text="创业板指"),
            ft.dropdown.Option("1015", text="恒生指数"),
            ft.dropdown.Option("1111", text="道琼斯"),
            ft.dropdown.Option("1112", text="标普500"),
            ft.dropdown.Option("1114", text="纳斯达克"),
        ],
        value="1010",
        width=150,
        dense=True,
        on_change=lambda e: update_stock(e.control.value)
    )
    
    stock_price = ft.Text("--", size=32, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
    stock_change = ft.Text("--", size=20, color=theme.get("TEXT_TERTIARY"))
    stock_change_pct = ft.Text("--", size=20, color=theme.get("TEXT_TERTIARY"))
    stock_details = ft.Column([
        ft.Text("成交量: --", size=14, color=theme.get("TEXT_TERTIARY")),
        ft.Text("成交额: --", size=14, color=theme.get("TEXT_TERTIARY")),
        ft.Text("数据源: --", size=12, color=theme.get("TEXT_TERTIARY")),
        ft.Text("更新时间: --", size=12, color=theme.get("TEXT_TERTIARY")),
    ], spacing=4)
    
    def update_stock(symbol=None):
        if symbol:
            stock_api.switch_to_index(symbol)
        data = stock_api.get_formatted_data(force_refresh=True)
        stock_price.value = f"{data['stock_price']:.2f}"
        
        change = data['stock_change']
        change_pct = data['stock_change_percent']
        if change >= 0:
            color = theme.get("BAD")
            sign = "+"
        else:
            color = theme.get("GOOD")
            sign = ""
        
        stock_change.value = f"{sign}{change:.2f}"
        stock_change.color = color
        stock_change_pct.value = f"({sign}{change_pct:.2f}%)"
        stock_change_pct.color = color
        
        volume = data['stock_volume']
        turnover = data['stock_turnover']
        if volume > 100000000:
            vol_str = f"{volume/100000000:.2f}亿"
        elif volume > 10000:
            vol_str = f"{volume/10000:.2f}万"
        else:
            vol_str = str(volume)
            
        if turnover > 100000000:
            turn_str = f"{turnover/100000000:.2f}亿"
        elif turnover > 10000:
            turn_str = f"{turnover/10000:.2f}万"
        else:
            turn_str = str(turnover)
        
        stock_details.controls[0].value = f"成交量: {vol_str}"
        stock_details.controls[1].value = f"成交额: {turn_str}"
        stock_details.controls[2].value = f"数据源: {data['stock_source']}"
        stock_details.controls[3].value = f"更新: {data['stock_update_time']}"
        page.update()
    
    stock_refresh_btn = ft.IconButton(
        icon="refresh",
        icon_color=theme.get("ACCENT"),
        tooltip="刷新股票",
        on_click=lambda e: update_stock()
    )
    
    stock_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="trending_up", color=theme.get("TEXT_SECONDARY")),
                ft.Text("股票指数", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
                ft.Container(expand=True),
                stock_index_dropdown,
                stock_refresh_btn
            ], spacing=8),
            ft.Row([stock_price, ft.Container(width=20), stock_change, stock_change_pct], alignment="end"),
            stock_details
        ], spacing=12, expand=True),
        height=320, padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    api_view = ft.Container(
        content=ft.Column(
            [
                ft.ResponsiveRow([
                    ft.Column([weather_main_card], col={"xs":12, "md":8}),
                    ft.Column([stock_card], col={"xs":12, "md":4}),
                ], columns=12),
                ft.ResponsiveRow([
                    ft.Column([weather_forecast_card], col={"xs":12, "md":12}),
                ], columns=12),
            ],
            spacing=12, expand=True, scroll=ft.ScrollMode.ADAPTIVE
        ),
        padding=12,
        expand=True
    )
    
    port_dropdown = ft.Dropdown(
        label="端口",
        width=150,
        options=[],
        dense=True
    )
    
    baudrate_dropdown = ft.Dropdown(
        label="波特率",
        width=140,
        value="1000000",
        options=[ft.dropdown.Option(str(b)) for b in serial_assistant.get_baudrate_list()] + [ft.dropdown.Option("custom", text="自定义…")],
        dense=True
    )

    baudrate_custom = ft.TextField(
        label="自定义",
        width=120,
        value="1000000",
        visible=False,
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.CENTER,
    )

    def on_baudrate_change(v):
        baudrate_custom.visible = (v == "custom")
        page.update()

    baudrate_dropdown.on_change = lambda e: on_baudrate_change(e.control.value)

    databits_dropdown = ft.Dropdown(
        label="数据位",
        width=80,
        value="8",
        options=[ft.dropdown.Option(str(b)) for b in [5, 6, 7, 8]],
        dense=True
    )
    
    stopbits_dropdown = ft.Dropdown(
        label="停止位",
        width=80,
        value="1",
        options=[ft.dropdown.Option(str(b)) for b in ["1", "1.5", "2"]],
        dense=True
    )
    
    parity_dropdown = ft.Dropdown(
        label="校验位",
        width=80,
        value="N",
        options=[
            ft.dropdown.Option("N", text="无"),
            ft.dropdown.Option("E", text="偶"),
            ft.dropdown.Option("O", text="奇"),
            ft.dropdown.Option("M", text="标记"),
            ft.dropdown.Option("S", text="空格")
        ],
        dense=True
    )
    
    def refresh_ports(e=None):
        ports = serial_assistant.get_available_ports()
        port_dropdown.options = [
            ft.dropdown.Option(p['port'], text=f"{p['port']} - {p['description']}")
            for p in ports
        ]
        if ports:
            port_dropdown.value = ports[0]['port']
        page.update()
    
    refresh_port_btn = ft.IconButton(
        icon="refresh",
        icon_color=theme.get("ACCENT"),
        tooltip="刷新端口",
        on_click=refresh_ports
    )
    
    connect_switch = ft.Switch(
        label="连接",
        value=False,
        active_color=theme.get("GOOD"),
        on_change=lambda e: toggle_connection(e.control.value)
    )
    
    rts_control_switch = ft.Switch(
        label="RTS",
        value=False,
        active_color=theme.get("ACCENT"),
        disabled=True,
        on_change=lambda e: control_rts_dtr(rts=e.control.value)
    )

    dtr_control_switch = ft.Switch(
        label="DTR", 
        value=False,
        active_color=theme.get("ACCENT"),
        disabled=True,
        on_change=lambda e: control_rts_dtr(dtr=e.control.value)
    )

    def control_rts_dtr(rts=None, dtr=None):
        if serial_assistant.is_connected:
            if rts is not None:
                serial_assistant.set_rts_dtr_control(rts=rts)
            if dtr is not None:
                serial_assistant.set_rts_dtr_control(dtr=dtr)
        else:
            if rts is not None:
                rts_control_switch.value = False
            if dtr is not None:
                dtr_control_switch.value = False
            page.update()

    finsh_enable_switch = ft.Switch(
        label="启用Finsh数据下发",
        value=False,
        active_color=theme.get("ACCENT"),
        on_change=lambda e: toggle_finsh_sender(e.control.value)
    )
    
    finsh_status_text = ft.Text(
        "数据下发: 已停止",
        size=12,
        color=theme.get("TEXT_TERTIARY")
    )

    
    finsh_stats_text = ft.Text(
        "已发送: 0 字段",
        size=12,
        color=theme.get("TEXT_TERTIARY")
    )
    
    def toggle_finsh_sender(enabled: bool):
        if enabled:
            if serial_assistant.is_connected:
                success = finsh_sender.start()
                if success:
                    finsh_enable_switch.value = True
                    finsh_status_text.value = "数据下发: 运行中"
                    finsh_status_text.color = theme.get("GOOD")
                else:
                    finsh_enable_switch.value = False
                    finsh_status_text.value = "数据下发: 启动失败"
                    finsh_status_text.color = theme.get("BAD")
            else:
                finsh_enable_switch.value = False
                finsh_status_text.value = "数据下发: 串口未连接"
                finsh_status_text.color = theme.get("WARN")
        else:
            finsh_sender.stop()
            finsh_enable_switch.value = False
            finsh_status_text.value = "数据下发: 已停止"
            finsh_status_text.color = theme.get("TEXT_TERTIARY")
        
        page.update()
    
    def toggle_connection(connect: bool):
        if connect:
            serial_assistant.configure(
                port=port_dropdown.value,
                baudrate=max(1, int(baudrate_custom.value) if baudrate_dropdown.value == "custom" else int(baudrate_dropdown.value)),
                bytesize=int(databits_dropdown.value),
                stopbits=float(stopbits_dropdown.value),
                parity=parity_dropdown.value
            )
            
            if serial_assistant.connect():
                connect_switch.value = True
                connect_switch.label = "已连接"
                
                port_dropdown.disabled = True
                baudrate_dropdown.disabled = True
                baudrate_custom.disabled = True
                databits_dropdown.disabled = True
                stopbits_dropdown.disabled = True
                parity_dropdown.disabled = True
                
                rts_control_switch.disabled = False
                dtr_control_switch.disabled = False
                
                finsh_enable_switch.disabled = False
                
            else:
                connect_switch.value = False
                connect_switch.label = "连接失败"
        else:
            if finsh_sender.enabled:
                toggle_finsh_sender(False)
            
            serial_assistant.disconnect()
            connect_switch.value = False
            connect_switch.label = "连接"
            
            port_dropdown.disabled = False
            baudrate_dropdown.disabled = False
            baudrate_custom.disabled = False
            databits_dropdown.disabled = False
            stopbits_dropdown.disabled = False
            parity_dropdown.disabled = False
            
            rts_control_switch.disabled = True
            dtr_control_switch.disabled = True
            
            finsh_enable_switch.disabled = True
            finsh_enable_switch.value = False
            finsh_status_text.value = "数据下发: 串口已断开"
            finsh_status_text.color = theme.get("TEXT_TERTIARY")
            
        page.update()
    
    serial_config_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="settings_input_component", color=theme.get("TEXT_SECONDARY")),
                ft.Text("串口配置", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            
            ft.Row([port_dropdown, refresh_port_btn], spacing=4),
            ft.Row([baudrate_dropdown, baudrate_custom, databits_dropdown], spacing=8),
            ft.Row([stopbits_dropdown, parity_dropdown], spacing=8),
            
            ft.Row([connect_switch, rts_control_switch, dtr_control_switch], spacing=12),
            
            ft.Divider(color=theme.get("DIVIDER")),
            
            ft.Row([
                ft.Icon(name="send", color=theme.get("TEXT_SECONDARY")),
                ft.Text("Finsh数据下发", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            finsh_enable_switch,
            finsh_status_text,
        ], spacing=12),
        width=350,
        padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))
    
    rx_display = ft.TextField(
        multiline=True,
        min_lines=20,
        max_lines=20,
        read_only=True,
        value="",
        text_style=ft.TextStyle(font_family="Consolas", size=12),
        border_color=theme.get("BORDER"),
        focused_border_color=theme.get("ACCENT"),
        expand=True
    )
    
    rx_format_radio = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="ascii", label="ASCII"),
            ft.Radio(value="hex", label="HEX")
        ]),
        value="ascii",
        on_change=lambda e: serial_assistant.set_rx_format(
            DataFormat.HEX if e.control.value == "hex" else DataFormat.ASCII
        )
    )
    
    rx_pause_checkbox = ft.Checkbox(
        label="暂停显示",
        value=False,
        on_change=lambda e: serial_assistant.pause_rx(e.control.value)
    )
    
    def clear_rx_display(e):
        rx_display.value = ""
        serial_assistant.clear_rx_buffer()
        page.update()
    
    rx_clear_btn = ft.ElevatedButton(
        "清空接收",
        icon="clear_all",
        on_click=clear_rx_display
    )
    
    rx_stats_text = ft.Text("接收: 0 字节", size=12, color=theme.get("TEXT_TERTIARY"))
    
    rx_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="call_received", color=theme.get("TEXT_SECONDARY")),
                ft.Text("接收区", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
                ft.Container(expand=True),
                rx_stats_text
            ], spacing=8),
            ft.Container(
                content=rx_display,
                expand=True
            ),
            ft.Row([
                rx_format_radio,
                ft.Container(expand=True),
                rx_pause_checkbox,
                rx_clear_btn
            ], spacing=8)
        ], spacing=12, expand=True),
        padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10,
        expand=True
    ))
    
    tx_input = ft.TextField(
        multiline=True,
        min_lines=4,
        max_lines=4,
        value="",
        text_style=ft.TextStyle(font_family="Consolas", size=12),
        border_color=theme.get("BORDER"),
        focused_border_color=theme.get("ACCENT")
    )
    
    tx_format_radio = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="ascii", label="ASCII"),
            ft.Radio(value="hex", label="HEX")
        ]),
        value="ascii",
        on_change=lambda e: serial_assistant.set_tx_format(
            DataFormat.HEX if e.control.value == "hex" else DataFormat.ASCII
        )
    )
    
    tx_newline_checkbox = ft.Checkbox(
        label="发送新行",
        value=False,
        on_change=lambda e: serial_assistant.set_tx_newline(e.control.value)
    )
    
    auto_send_checkbox = ft.Checkbox(
        label="自动发送",
        value=False,
        on_change=lambda e: toggle_auto_send(e.control.value)
    )
    
    auto_send_interval = ft.TextField(
        label="周期(ms)",
        value="1000",
        width=100,
        text_align=ft.TextAlign.CENTER
    )
    
    def toggle_auto_send(enabled: bool):
        if enabled:
            try:
                interval = int(auto_send_interval.value) / 1000.0
                if interval < 0.01:
                    interval = 0.01
                serial_assistant.start_auto_send(tx_input.value, interval)
            except:
                auto_send_checkbox.value = False
                page.update()
        else:
            serial_assistant.stop_auto_send()
    
    def send_data(e):
        if serial_assistant.is_connected:
            serial_assistant.send_data(tx_input.value)
    
    tx_send_btn = ft.ElevatedButton(
        "发送",
        icon="send",
        on_click=send_data
    )
    
    tx_stats_text = ft.Text("发送: 0 字节", size=12, color=theme.get("TEXT_TERTIARY"))
    
    tx_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="call_made", color=theme.get("TEXT_SECONDARY")),
                ft.Text("发送区", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
                ft.Container(expand=True),
                tx_stats_text
            ], spacing=8),
            tx_input,
            ft.Row([
                tx_format_radio,
                tx_newline_checkbox,
                ft.Container(expand=True),
            ], spacing=16),
            ft.Row([
                auto_send_checkbox,
                auto_send_interval,
                ft.Container(expand=True),
                tx_send_btn
            ], spacing=12)
        ], spacing=12),
        padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))

    serial_view = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Row([
                        ft.Container(content=serial_config_card, width=350),
                        ft.Container(width=12),
                        ft.Container(content=rx_card, expand=True)
                    ], spacing=0),
                    height=500,
                    expand=False
                ),
                ft.Container(height=8),
                ft.Container(content=tx_card, height=300)
            ],
            spacing=0, expand=True
        ),
        expand=True,
        padding=12
    )
    
    def on_serial_data_received(data: bytes):
        formatted = serial_assistant.get_received_data()
        if formatted:
            rx_display.value += formatted
            if len(rx_display.value) > 10000:
                rx_display.value = rx_display.value[-8000:]
            
            text_length = len(rx_display.value)
            rx_display.selection = ft.TextSelection(
                base_offset=text_length,
                extent_offset=text_length
            )
            
            stats = serial_assistant.get_statistics()
            rx_stats_text.value = f"接收: {stats['rx_bytes']} 字节"
            tx_stats_text.value = f"发送: {stats['tx_bytes']} 字节"
            
            finsh_stats = finsh_sender.get_status()
            finsh_stats_text.value = f"已发送: {finsh_stats['stats']['commands_sent']} 字段"
            
            page.update()
    
    serial_assistant.on_data_received = on_serial_data_received
    
    refresh_ports()

    time_data_switch = ft.Switch(
        label="时间数据下发",
        value=True,
        on_change=lambda e: finsh_sender.configure(send_time_data=e.control.value)
    )
    
    api_data_switch = ft.Switch(
        label="API数据下发",
        value=True,
        on_change=lambda e: finsh_sender.configure(send_api_data=e.control.value)
    )
    
    performance_data_switch = ft.Switch(
        label="性能数据下发",
        value=True,
        on_change=lambda e: finsh_sender.configure(send_performance_data=e.control.value)
    )
    
    time_interval_field = ft.TextField(
        label="时间数据间隔(秒)",
        value="1000.0",
        width=150,
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: finsh_sender.configure(time_interval=float(e.control.value) if e.control.value else 1.0)
    )
    
    api_interval_field = ft.TextField(
        label="API数据间隔(秒)",
        value="2.0", 
        width=150,
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: finsh_sender.configure(api_interval=float(e.control.value) if e.control.value else 30.0)
    )
    
    performance_interval_field = ft.TextField(
        label="性能数据间隔(秒)",
        value="1.0",
        width=150, 
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: finsh_sender.configure(performance_interval=float(e.control.value) if e.control.value else 5.0)
    )
    
    command_interval_field = ft.TextField(
        label="命令间隔(毫秒)",
        value="1000",
        width=150,
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: finsh_sender.configure(min_command_interval=int(e.control.value) if e.control.value else 5)
    )
    
    def reset_to_defaults(e):
        time_data_switch.value = True
        api_data_switch.value = True
        performance_data_switch.value = True
        time_interval_field.value = "1000.0"
        api_interval_field.value = "2.0"
        performance_interval_field.value = "1.0"
        command_interval_field.value = "1000"
        
        finsh_sender.configure(
            send_time_data=True,
            send_api_data=True,
            send_performance_data=True,
            time_interval=1000.0,
            api_interval=2.0,
            performance_interval=5.0,
            min_command_interval=1000
        )
        page.update()
    
    reset_defaults_btn = ft.ElevatedButton(
        "重置为默认",
        icon="restore",
        on_click=reset_to_defaults
    )
    
    finsh_config_card = ft.Card(ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(name="send", color=theme.get("TEXT_SECONDARY")),
                ft.Text("Finsh数据下发配置", size=18, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY"))
            ], spacing=8),
            
            ft.Text("数据类型控制", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
            ft.Row([
                time_data_switch,
                api_data_switch, 
                performance_data_switch
            ], spacing=16),
            
            ft.Row([
                ft.Column([
                    ft.Text("时间间隔配置", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
                    ft.Row([
                        time_interval_field,
                        api_interval_field,
                        performance_interval_field
                    ], spacing=12),
                ], spacing=8),
                ft.Container(width=20),
                ft.Column([
                    ft.Text("其他配置", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
                    ft.Row([
                        command_interval_field,
                        reset_defaults_btn
                    ], spacing=12)
                ], spacing=8),
            ], spacing=12)
        ], spacing=16),
        padding=16, bgcolor=theme.get("CARD_BG_ALPHA"), border_radius=10
    ))
    
    settings_view = ft.Container(
        content=ft.Column([
            ft.Text("设置", size=24, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
            ft.Container(height=20),
            weather_api_config_card,
            ft.Container(height=20),
            finsh_config_card,
            ft.Container(height=20),
        ], spacing=16, scroll=ft.ScrollMode.ADAPTIVE, expand=True),
        padding=20,
        expand=True
    )

    about_view = ft.Container(
        content=ft.Column([
            ft.Text("关于", size=24, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_PRIMARY")),
            ft.Text("SuperKey_Windows支持工具", size=16, color=theme.get("TEXT_SECONDARY")),
            ft.Text("Build v1.5.0 - 适配固件1.0版本", size=14, color=theme.get("TEXT_TERTIARY")),
            ft.Container(height=20),
            ft.Text("制作团队", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
            ft.Text("• 解博文 xiebowen1@outlook.com", size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Text("• 蔡松 19914553473@163.com", size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Text("• 郭雨十 2361768748@qq.com", size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Text("• 思澈科技（南京）提供技术支持", size=12, color=theme.get("TEXT_TERTIARY")),
            ft.Container(height=20),
            ft.Text("开源协议", size=16, weight=ft.FontWeight.BOLD, color=theme.get("TEXT_SECONDARY")),
            ft.Text("• Apache-2.0", size=12, color=theme.get("TEXT_TERTIARY")),
        ], spacing=8),
        padding=20,
        expand=True
    )

    def show_view(name: str):
        current_view["name"] = name
        if name == "performance":
            content_host.content = performance_view
        elif name == "api":
            content_host.content = api_view
            if not hasattr(api_view, '_initialized'):
                if weather_api.get_config().get('api_configured', False):
                    update_weather()
                update_stock()
                api_view._initialized = True
        elif name == "serial":
            content_host.content = serial_view
        elif name == "settings":
            content_host.content = settings_view
        elif name == "about":
            content_host.content = about_view
        
        for nav_item in nav_items:
            if not nav_item.is_separator:
                nav_item.set_active(nav_item.view_name == name)
        
        page.update()

    nav_items = [
        NavigationItem("speed", "性能监控", "performance", theme, show_view, 24),
        NavigationItem("api", "API 服务", "api", theme, show_view, 24), 
        NavigationItem("usb", "串口调试", "serial", theme, show_view, 24),
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

    if theme.current_theme == "light":
        shell_bg = "#EEF0F0F0"
    else:
        shell_bg = "#EE0E0E10"
    
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
        """仅应用背景效果，不调整窗口尺寸"""
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
        
        stock_price.color = theme.get("TEXT_PRIMARY")
        stock_refresh_btn.icon_color = theme.get("ACCENT")
        stock_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        
        for ctrl in stock_details.controls:
            ctrl.color = theme.get("TEXT_TERTIARY")
        
        serial_config_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        rx_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        tx_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        
        rx_display.border_color = theme.get("BORDER")
        rx_display.focused_border_color = theme.get("ACCENT")
        tx_input.border_color = theme.get("BORDER")
        tx_input.focused_border_color = theme.get("ACCENT")
        
        rx_stats_text.color = theme.get("TEXT_TERTIARY")
        tx_stats_text.color = theme.get("TEXT_TERTIARY")
        finsh_stats_text.color = theme.get("TEXT_TERTIARY")
        
        weather_api_config_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        weather_config_status.color = theme.get("TEXT_TERTIARY")
        
        finsh_config_card.content.bgcolor = theme.get("CARD_BG_ALPHA")
        
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
        
        if theme.current_theme == "light":
            shell.bgcolor = "#EEF0F0F0"
        else:
            shell.bgcolor = "#EE0E0E10"

    async def updater():
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
                apply_backdrop_for_page(page, theme, prefer_mica=True)
            
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
            
            if current_view["name"] == "serial":
                if serial_assistant.is_connected:
                    stats = serial_assistant.get_statistics()
                    rx_stats_text.value = f"接收: {stats['rx_bytes']} 字节"
                    tx_stats_text.value = f"发送: {stats['tx_bytes']} 字节"
                
                if finsh_sender.enabled:
                    finsh_status = finsh_sender.get_status()
                    finsh_stats_text.value = f"已发送: {finsh_status['stats']['commands_sent']} 字段"
                    
                    error_count = finsh_status['stats']['errors']
                    if error_count > 0:
                        finsh_status_text.value = f"数据下发: 运行中 (错误: {error_count})"
                        finsh_status_text.color = theme.get("WARN")
                    else:
                        finsh_status_text.value = "数据下发: 运行中"
                        finsh_status_text.color = theme.get("GOOD")

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