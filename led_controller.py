#!/usr/bin/env python3
"""
LED灯光效果控制器模块
通过串口发送命令控制RGB LED效果
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from serial_assistant import SerialAssistant


class LedEffect(Enum):
    """LED效果类型"""
    STATIC = "static"
    BREATHING = "breathing"
    FLOWING = "flowing"
    BLINK = "blink"
    RAINBOW = "rainbow"
    OFF = "off"


@dataclass
class LedColorPreset:
    """预设颜色"""
    name: str
    display_name: str
    color: str  # 十六进制颜色 RRGGBB


# 预设颜色列表
LED_COLOR_PRESETS: list[LedColorPreset] = [
    LedColorPreset("red", "红色", "FF0000"),
    LedColorPreset("orange", "橙色", "FF8000"),
    LedColorPreset("yellow", "黄色", "FFFF00"),
    LedColorPreset("green", "绿色", "00FF00"),
    LedColorPreset("cyan", "青色", "00FFFF"),
    LedColorPreset("blue", "蓝色", "0000FF"),
    LedColorPreset("purple", "紫色", "8000FF"),
    LedColorPreset("magenta", "品红", "FF00FF"),
    LedColorPreset("pink", "粉色", "FF80C0"),
    LedColorPreset("white", "白色", "FFFFFF"),
]

# 效果显示名称
LED_EFFECT_NAMES: dict[LedEffect, str] = {
    LedEffect.STATIC: "静态",
    LedEffect.BREATHING: "呼吸",
    LedEffect.FLOWING: "流水",
    LedEffect.BLINK: "闪烁",
    LedEffect.RAINBOW: "彩虹",
    LedEffect.OFF: "关闭",
}


class LedController:
    """LED控制器类"""

    def __init__(self, serial_assistant: SerialAssistant | None = None) -> None:
        """初始化LED控制器

        Args:
            serial_assistant: 串口助手实例
        """
        self.serial_assistant: SerialAssistant | None = serial_assistant

        # 当前状态
        self._brightness: int = 128
        self._color: str = "FF0000"  # 默认红色
        self._effect: LedEffect = LedEffect.STATIC
        self._effect_period: int = 2000  # 效果周期(毫秒)

    @property
    def brightness(self) -> int:
        """获取当前亮度"""
        return self._brightness

    @property
    def color(self) -> str:
        """获取当前颜色"""
        return self._color

    @property
    def effect(self) -> LedEffect:
        """获取当前效果"""
        return self._effect

    @property
    def effect_period(self) -> int:
        """获取效果周期"""
        return self._effect_period

    def set_serial_assistant(self, serial_assistant: SerialAssistant) -> None:
        """设置串口助手

        Args:
            serial_assistant: 串口助手实例
        """
        self.serial_assistant = serial_assistant

    def _send_command(self, key: str, value: Any) -> bool:
        """发送命令到设备

        Args:
            key: 命令键
            value: 命令值

        Returns:
            是否发送成功
        """
        if not self.serial_assistant or not self.serial_assistant.is_connected:
            return False

        command = f"sys_set {key} {value}\n"
        return self.serial_assistant.send_data(command)

    def set_brightness(self, brightness: int) -> bool:
        """设置亮度

        Args:
            brightness: 亮度值 (0-255)

        Returns:
            是否成功
        """
        brightness = max(0, min(255, brightness))
        self._brightness = brightness
        return self._send_command("led_brightness", brightness)

    def set_color(self, color: str) -> bool:
        """设置颜色

        Args:
            color: 十六进制颜色值 (RRGGBB)

        Returns:
            是否成功
        """
        # 移除可能的前缀
        if color.startswith("#"):
            color = color[1:]
        if color.startswith("0x") or color.startswith("0X"):
            color = color[2:]

        self._color = color.upper()
        return self._send_command("led_color", self._color)

    def set_color_rgb(self, r: int, g: int, b: int) -> bool:
        """设置RGB颜色

        Args:
            r: 红色分量 (0-255)
            g: 绿色分量 (0-255)
            b: 蓝色分量 (0-255)

        Returns:
            是否成功
        """
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        color = f"{r:02X}{g:02X}{b:02X}"
        return self.set_color(color)

    def set_preset_color(self, preset_name: str) -> bool:
        """设置预设颜色

        Args:
            preset_name: 预设颜色名称

        Returns:
            是否成功
        """
        return self._send_command("led_preset", preset_name)

    def set_effect(self, effect: LedEffect) -> bool:
        """设置效果

        Args:
            effect: 效果类型

        Returns:
            是否成功
        """
        self._effect = effect
        return self._send_command("led_effect", effect.value)

    def set_effect_with_params(
        self,
        effect: LedEffect,
        color: str | None = None,
        period_ms: int | None = None,
        brightness: int | None = None
    ) -> bool:
        """设置带参数的效果

        Args:
            effect: 效果类型
            color: 颜色 (RRGGBB)
            period_ms: 周期(毫秒)
            brightness: 亮度 (0-255)

        Returns:
            是否成功
        """
        self._effect = effect

        if color is None:
            color = self._color
        if period_ms is None:
            period_ms = self._effect_period
        if brightness is None:
            brightness = self._brightness

        self._effect_period = period_ms

        # 格式: effect_name,color,period_ms,brightness
        value = f"{effect.value},{color},{period_ms},{brightness}"
        return self._send_command("led_effect_ex", value)

    def set_single_led(self, index: int, color: str) -> bool:
        """设置单个LED颜色

        Args:
            index: LED索引
            color: 颜色 (RRGGBB)

        Returns:
            是否成功
        """
        if color.startswith("#"):
            color = color[1:]
        value = f"{index},{color}"
        return self._send_command("led_single", value)

    def stop(self) -> bool:
        """停止所有效果

        Returns:
            是否成功
        """
        self._effect = LedEffect.OFF
        return self._send_command("led_stop", "1")

    def turn_off(self) -> bool:
        """关闭所有LED

        Returns:
            是否成功
        """
        return self.set_effect(LedEffect.OFF)

    def get_status(self) -> dict[str, Any]:
        """获取当前状态

        Returns:
            状态字典
        """
        connected = False
        if self.serial_assistant:
            connected = self.serial_assistant.is_connected

        return {
            "connected": connected,
            "brightness": self._brightness,
            "color": self._color,
            "effect": self._effect.value,
            "effect_name": LED_EFFECT_NAMES.get(self._effect, "未知"),
            "effect_period": self._effect_period,
        }


# 全局实例
_led_controller: LedController | None = None


def get_led_controller() -> LedController:
    """获取全局LED控制器实例"""
    global _led_controller
    if _led_controller is None:
        _led_controller = LedController()
    return _led_controller


def set_led_controller_serial(serial_assistant: SerialAssistant) -> None:
    """设置LED控制器的串口助手"""
    controller = get_led_controller()
    controller.set_serial_assistant(serial_assistant)