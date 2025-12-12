#!/usr/bin/env python3
"""
自定义按键管理
"""
import json
import os
import platform
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ============================================================================
# HID Keycode 定义
# ============================================================================


class Modifier:
    NONE: int = 0x00
    CTRL: int = 0x01
    SHIFT: int = 0x02
    ALT: int = 0x04
    GUI: int = 0x08  # Win/Cmd


class KeyCode:
    NONE: int = 0x00
    # 字母
    A: int = 0x04
    B: int = 0x05
    C: int = 0x06
    D: int = 0x07
    E: int = 0x08
    F: int = 0x09
    G: int = 0x0A
    H: int = 0x0B
    I: int = 0x0C
    J: int = 0x0D
    K: int = 0x0E
    L: int = 0x0F
    M: int = 0x10
    N: int = 0x11
    O: int = 0x12
    P: int = 0x13
    Q: int = 0x14
    R: int = 0x15
    S: int = 0x16
    T: int = 0x17
    U: int = 0x18
    V: int = 0x19
    W: int = 0x1A
    X: int = 0x1B
    Y: int = 0x1C
    Z: int = 0x1D
    # 数字
    N1: int = 0x1E
    N2: int = 0x1F
    N3: int = 0x20
    N4: int = 0x21
    N5: int = 0x22
    N6: int = 0x23
    N7: int = 0x24
    N8: int = 0x25
    N9: int = 0x26
    N0: int = 0x27
    # 功能键
    F1: int = 0x3A
    F2: int = 0x3B
    F3: int = 0x3C
    F4: int = 0x3D
    F5: int = 0x3E
    F6: int = 0x3F
    F7: int = 0x40
    F8: int = 0x41
    F9: int = 0x42
    F10: int = 0x43
    F11: int = 0x44
    F12: int = 0x45
    # 特殊键
    ENTER: int = 0x28
    ESCAPE: int = 0x29
    BACKSPACE: int = 0x2A
    TAB: int = 0x2B
    SPACE: int = 0x2C
    DELETE: int = 0x4C
    PAGE_UP: int = 0x4B
    PAGE_DOWN: int = 0x4E
    RIGHT: int = 0x4F
    LEFT: int = 0x50
    DOWN: int = 0x51
    UP: int = 0x52
    HOME: int = 0x4A
    END: int = 0x4D


# 按键名称映射
KEY_NAME_MAP: dict[int, str] = {
    KeyCode.NONE: "无",
    KeyCode.A: "A", KeyCode.B: "B", KeyCode.C: "C", KeyCode.D: "D",
    KeyCode.E: "E", KeyCode.F: "F", KeyCode.G: "G", KeyCode.H: "H",
    KeyCode.I: "I", KeyCode.J: "J", KeyCode.K: "K", KeyCode.L: "L",
    KeyCode.M: "M", KeyCode.N: "N", KeyCode.O: "O", KeyCode.P: "P",
    KeyCode.Q: "Q", KeyCode.R: "R", KeyCode.S: "S", KeyCode.T: "T",
    KeyCode.U: "U", KeyCode.V: "V", KeyCode.W: "W", KeyCode.X: "X",
    KeyCode.Y: "Y", KeyCode.Z: "Z",
    KeyCode.N0: "0", KeyCode.N1: "1", KeyCode.N2: "2", KeyCode.N3: "3",
    KeyCode.N4: "4", KeyCode.N5: "5", KeyCode.N6: "6", KeyCode.N7: "7",
    KeyCode.N8: "8", KeyCode.N9: "9",
    KeyCode.F1: "F1", KeyCode.F2: "F2", KeyCode.F3: "F3", KeyCode.F4: "F4",
    KeyCode.F5: "F5", KeyCode.F6: "F6", KeyCode.F7: "F7", KeyCode.F8: "F8",
    KeyCode.F9: "F9", KeyCode.F10: "F10", KeyCode.F11: "F11",
    KeyCode.F12: "F12",
    KeyCode.ENTER: "Enter", KeyCode.ESCAPE: "Esc",
    KeyCode.BACKSPACE: "Backspace",
    KeyCode.TAB: "Tab", KeyCode.SPACE: "Space", KeyCode.DELETE: "Delete",
    KeyCode.PAGE_UP: "PgUp", KeyCode.PAGE_DOWN: "PgDn",
    KeyCode.UP: "↑", KeyCode.DOWN: "↓", KeyCode.LEFT: "←", KeyCode.RIGHT: "→",
    KeyCode.HOME: "Home", KeyCode.END: "End",
}

NAME_TO_KEY: dict[str, int] = {v: k for k, v in KEY_NAME_MAP.items()}

# Flet keyboard event key name -> HID keycode 映射
# 用于将键盘输入事件转换为 HID keycode
FLET_KEY_TO_HID: dict[str, int] = {
    # 字母键 (Flet 返回大写字母)
    "A": KeyCode.A, "B": KeyCode.B, "C": KeyCode.C, "D": KeyCode.D,
    "E": KeyCode.E, "F": KeyCode.F, "G": KeyCode.G, "H": KeyCode.H,
    "I": KeyCode.I, "J": KeyCode.J, "K": KeyCode.K, "L": KeyCode.L,
    "M": KeyCode.M, "N": KeyCode.N, "O": KeyCode.O, "P": KeyCode.P,
    "Q": KeyCode.Q, "R": KeyCode.R, "S": KeyCode.S, "T": KeyCode.T,
    "U": KeyCode.U, "V": KeyCode.V, "W": KeyCode.W, "X": KeyCode.X,
    "Y": KeyCode.Y, "Z": KeyCode.Z,
    # 数字键
    "0": KeyCode.N0, "1": KeyCode.N1, "2": KeyCode.N2, "3": KeyCode.N3,
    "4": KeyCode.N4, "5": KeyCode.N5, "6": KeyCode.N6, "7": KeyCode.N7,
    "8": KeyCode.N8, "9": KeyCode.N9,
    # 功能键
    "F1": KeyCode.F1, "F2": KeyCode.F2, "F3": KeyCode.F3, "F4": KeyCode.F4,
    "F5": KeyCode.F5, "F6": KeyCode.F6, "F7": KeyCode.F7, "F8": KeyCode.F8,
    "F9": KeyCode.F9, "F10": KeyCode.F10, "F11": KeyCode.F11,
    "F12": KeyCode.F12,
    # 特殊键
    "Enter": KeyCode.ENTER,
    "Escape": KeyCode.ESCAPE,
    "Backspace": KeyCode.BACKSPACE,
    "Tab": KeyCode.TAB,
    " ": KeyCode.SPACE,  # 空格键
    "Delete": KeyCode.DELETE,
    "Page Up": KeyCode.PAGE_UP,
    "Page Down": KeyCode.PAGE_DOWN,
    "Arrow Right": KeyCode.RIGHT,
    "Arrow Left": KeyCode.LEFT,
    "Arrow Down": KeyCode.DOWN,
    "Arrow Up": KeyCode.UP,
    "Home": KeyCode.HOME,
    "End": KeyCode.END,
}


def flet_key_to_hid(flet_key: str) -> int | None:
    """将 Flet 键盘事件的 key 转换为 HID keycode"""
    # 直接查找
    if flet_key in FLET_KEY_TO_HID:
        return FLET_KEY_TO_HID[flet_key]
    # 尝试大写
    if flet_key.upper() in FLET_KEY_TO_HID:
        return FLET_KEY_TO_HID[flet_key.upper()]
    return None


def get_key_display_name(keycode: int) -> str:
    """获取按键的显示名称"""
    return KEY_NAME_MAP.get(keycode, f"0x{keycode:02X}" if keycode else "无")


# 预设快捷键
PRESET_SHORTCUTS: dict[str, tuple[int, int]] = {
    "无": (Modifier.NONE, KeyCode.NONE),
    "复制 (Ctrl+C)": (Modifier.CTRL, KeyCode.C),
    "粘贴 (Ctrl+V)": (Modifier.CTRL, KeyCode.V),
    "剪切 (Ctrl+X)": (Modifier.CTRL, KeyCode.X),
    "撤销 (Ctrl+Z)": (Modifier.CTRL, KeyCode.Z),
    "重做 (Ctrl+Y)": (Modifier.CTRL, KeyCode.Y),
    "全选 (Ctrl+A)": (Modifier.CTRL, KeyCode.A),
    "保存 (Ctrl+S)": (Modifier.CTRL, KeyCode.S),
    "新建 (Ctrl+N)": (Modifier.CTRL, KeyCode.N),
    "打开 (Ctrl+O)": (Modifier.CTRL, KeyCode.O),
    "打印 (Ctrl+P)": (Modifier.CTRL, KeyCode.P),
    "查找 (Ctrl+F)": (Modifier.CTRL, KeyCode.F),
    "替换 (Ctrl+H)": (Modifier.CTRL, KeyCode.H),
    "新标签 (Ctrl+T)": (Modifier.CTRL, KeyCode.T),
    "关闭标签 (Ctrl+W)": (Modifier.CTRL, KeyCode.W),
    "刷新 (F5)": (Modifier.NONE, KeyCode.F5),
    "全屏 (F11)": (Modifier.NONE, KeyCode.F11),
    "锁屏 (Win+L)": (Modifier.GUI, KeyCode.L),
    "运行 (Win+R)": (Modifier.GUI, KeyCode.R),
    "资源管理器 (Win+E)": (Modifier.GUI, KeyCode.E),
    "桌面 (Win+D)": (Modifier.GUI, KeyCode.D),
}


# ============================================================================
# 数据结构
# ============================================================================


@dataclass
class KeyCombo:
    modifier: int = 0
    keycode: int = 0


@dataclass
class CustomKey:
    combos: list[KeyCombo] = field(
        default_factory=lambda: [KeyCombo() for _ in range(4)]
    )
    enabled: bool = False
    name: str = ""


@dataclass
class CustomKeyConfig:
    """仅包含组0的3个按键配置"""

    keys: list[CustomKey] = field(
        default_factory=lambda: [CustomKey() for _ in range(3)]
    )


# ============================================================================
# 管理器类
# ============================================================================


class CustomKeyManager:
    """自定义按键管理器 - 仅支持组0"""

    GROUP_ID: int = 0  # 固定为组0

    def __init__(
        self, send_command_func: Callable[[str], bool] | None = None
    ) -> None:
        self.config: CustomKeyConfig = CustomKeyConfig()
        self.send_command: Callable[[str], bool] | None = send_command_func
        self._config_path: Path = self._get_config_path()
        self.load_config()

    def _get_config_path(self) -> Path:
        system: str = platform.system().lower()
        if system == 'windows':
            base: Path = Path(os.environ.get('APPDATA', ''))
        elif system == 'darwin':
            base = Path.home() / 'Library' / 'Application Support'
        else:
            base = Path.home() / '.config'

        config_dir: Path = base / 'SuperKey'
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / 'custom_keys.json'

    def load_config(self) -> None:
        """从本地加载配置"""
        try:
            if self._config_path.exists():
                with open(self._config_path, encoding='utf-8') as f:
                    data: dict[str, Any] = json.load(f)
                    for ki, kdata in enumerate(data.get('keys', [])):
                        if ki < 3:
                            key: CustomKey = self.config.keys[ki]
                            key.enabled = kdata.get('enabled', False)
                            key.name = kdata.get('name', '')
                            combos: list[dict[str, int]] = kdata.get(
                                'combos', []
                            )
                            for ci, cdata in enumerate(combos):
                                if ci < 4:
                                    key.combos[ci].modifier = cdata.get(
                                        'modifier', 0
                                    )
                                    key.combos[ci].keycode = cdata.get(
                                        'keycode', 0
                                    )
        except Exception:
            pass

    def save_config(self) -> None:
        """保存配置到本地"""
        try:
            data: dict[str, list[dict[str, Any]]] = {'keys': []}
            for key in self.config.keys:
                kdata: dict[str, Any] = {
                    'enabled': key.enabled,
                    'name': key.name,
                    'combos': [
                        {'modifier': c.modifier, 'keycode': c.keycode}
                        for c in key.combos
                    ]
                }
                data['keys'].append(kdata)

            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def set_key_from_preset(self, key_idx: int, preset_name: str) -> bool:
        """从预设设置按键"""
        if key_idx < 0 or key_idx >= 3:
            return False
        if preset_name not in PRESET_SHORTCUTS:
            return False

        mod: int
        keycode: int
        mod, keycode = PRESET_SHORTCUTS[preset_name]
        key: CustomKey = self.config.keys[key_idx]
        key.combos[0].modifier = mod
        key.combos[0].keycode = keycode
        key.enabled = (keycode != 0)
        key.name = preset_name

        # 清除其他combo
        for i in range(1, 4):
            key.combos[i].modifier = 0
            key.combos[i].keycode = 0

        self.save_config()
        return True

    def set_combo(
        self, key_idx: int, combo_idx: int, modifier: int, keycode: int
    ) -> bool:
        """设置单个组合键"""
        if key_idx < 0 or key_idx >= 3:
            return False
        if combo_idx < 0 or combo_idx >= 4:
            return False

        key: CustomKey = self.config.keys[key_idx]
        key.combos[combo_idx].modifier = modifier
        key.combos[combo_idx].keycode = keycode

        # 检查是否有任何有效的combo
        has_valid: bool = any(c.keycode != 0 for c in key.combos)
        key.enabled = has_valid

        # 清除预设名称（因为是自定义的）
        key.name = ""

        self.save_config()
        return True

    def get_combo(self, key_idx: int, combo_idx: int) -> tuple[int, int]:
        """获取单个组合键配置"""
        if key_idx < 0 or key_idx >= 3:
            return (0, 0)
        if combo_idx < 0 or combo_idx >= 4:
            return (0, 0)

        combo: KeyCombo = self.config.keys[key_idx].combos[combo_idx]
        return (combo.modifier, combo.keycode)

    def get_combo_display_text(self, key_idx: int, combo_idx: int) -> str:
        """获取单个组合键的显示文本"""
        if key_idx < 0 or key_idx >= 3:
            return "无效"
        if combo_idx < 0 or combo_idx >= 4:
            return "无效"

        combo: KeyCombo = self.config.keys[key_idx].combos[combo_idx]
        if combo.keycode == 0:
            return "无"

        parts: list[str] = []
        if combo.modifier & Modifier.CTRL:
            parts.append("Ctrl")
        if combo.modifier & Modifier.SHIFT:
            parts.append("Shift")
        if combo.modifier & Modifier.ALT:
            parts.append("Alt")
        if combo.modifier & Modifier.GUI:
            parts.append("Win")

        key_name: str = KEY_NAME_MAP.get(
            combo.keycode, f"0x{combo.keycode:02X}"
        )
        parts.append(key_name)

        return "+".join(parts)

    def clear_key(self, key_idx: int) -> None:
        """清除按键配置"""
        if key_idx < 0 or key_idx >= 3:
            return
        key: CustomKey = self.config.keys[key_idx]
        key.enabled = False
        key.name = ""
        for combo in key.combos:
            combo.modifier = 0
            combo.keycode = 0
        self.save_config()

    def generate_command(self, key_idx: int) -> str:
        """生成串口命令"""
        if key_idx < 0 or key_idx >= 3:
            return ""
        key: CustomKey = self.config.keys[key_idx]
        params: list[str] = [str(self.GROUP_ID), str(key_idx)]

        for combo in key.combos:
            params.append(f"0x{combo.modifier:02X}")
            params.append(f"0x{combo.keycode:02X}")

        return f'sys_set custom_key "{",".join(params)}"'

    def sync_key_to_device(self, key_idx: int) -> bool:
        """同步单个按键到设备"""
        if self.send_command is None:
            return False
        if key_idx < 0 or key_idx >= 3:
            return False

        cmd: str = self.generate_command(key_idx)
        return self.send_command(cmd)

    def sync_all_to_device(self) -> bool:
        """同步所有配置到设备（仅组0的3个按键）"""
        if self.send_command is None:
            return False

        success: bool = True
        for ki in range(3):
            if not self.sync_key_to_device(ki):
                success = False
        return success

    def get_key_display_text(self, key_idx: int) -> str:
        """获取按键显示文本"""
        if key_idx < 0 or key_idx >= 3:
            return "无效"
        key: CustomKey = self.config.keys[key_idx]
        if not key.enabled:
            return "未配置"
        if key.name:
            return key.name

        # 生成显示文本
        combo: KeyCombo = key.combos[0]
        parts: list[str] = []
        if combo.modifier & Modifier.CTRL:
            parts.append("Ctrl")
        if combo.modifier & Modifier.SHIFT:
            parts.append("Shift")
        if combo.modifier & Modifier.ALT:
            parts.append("Alt")
        if combo.modifier & Modifier.GUI:
            parts.append("Win")

        key_name: str = KEY_NAME_MAP.get(
            combo.keycode, f"0x{combo.keycode:02X}"
        )
        if key_name != "无":
            parts.append(key_name)

        return "+".join(parts) if parts else "未配置"


# 全局实例
_manager_instance: CustomKeyManager | None = None


def get_custom_key_manager(
    send_func: Callable[[str], bool] | None = None
) -> CustomKeyManager:
    """获取全局 CustomKeyManager 实例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = CustomKeyManager(send_func)
    elif send_func is not None:
        _manager_instance.send_command = send_func
    return _manager_instance


# 获取所有可用按键选项（用于UI下拉框）
def get_all_key_options() -> list[tuple[str, int]]:
    """返回所有可用按键的列表 [(显示名称, keycode), ...]"""
    return [(name, code) for code, name in KEY_NAME_MAP.items()]


def get_modifier_options() -> list[tuple[str, int]]:
    """返回所有修饰键选项 [(显示名称, modifier_value), ...]"""
    return [
        ("无", Modifier.NONE),
        ("Ctrl", Modifier.CTRL),
        ("Shift", Modifier.SHIFT),
        ("Alt", Modifier.ALT),
        ("Win", Modifier.GUI),
        ("Ctrl+Shift", Modifier.CTRL | Modifier.SHIFT),
        ("Ctrl+Alt", Modifier.CTRL | Modifier.ALT),
        ("Ctrl+Win", Modifier.CTRL | Modifier.GUI),
        ("Shift+Alt", Modifier.SHIFT | Modifier.ALT),
        ("Ctrl+Shift+Alt", Modifier.CTRL | Modifier.SHIFT | Modifier.ALT),
    ]
