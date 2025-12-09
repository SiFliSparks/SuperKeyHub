#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义按键管理模块
负责配置管理和串口下发
仅支持组0的3个按键
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Callable
import platform

# ============================================================================
# HID Keycode 定义
# ============================================================================

class Modifier:
    NONE = 0x00
    CTRL = 0x01
    SHIFT = 0x02
    ALT = 0x04
    GUI = 0x08  # Win/Cmd

class KeyCode:
    NONE = 0x00
    # 字母
    A, B, C, D, E, F = 0x04, 0x05, 0x06, 0x07, 0x08, 0x09
    G, H, I, J, K, L = 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F
    M, N, O, P, Q, R = 0x10, 0x11, 0x12, 0x13, 0x14, 0x15
    S, T, U, V, W, X = 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B
    Y, Z = 0x1C, 0x1D
    # 数字
    N1, N2, N3, N4, N5 = 0x1E, 0x1F, 0x20, 0x21, 0x22
    N6, N7, N8, N9, N0 = 0x23, 0x24, 0x25, 0x26, 0x27
    # 功能键
    F1, F2, F3, F4, F5, F6 = 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F
    F7, F8, F9, F10, F11, F12 = 0x40, 0x41, 0x42, 0x43, 0x44, 0x45
    # 特殊键
    ENTER = 0x28
    ESCAPE = 0x29
    BACKSPACE = 0x2A
    TAB = 0x2B
    SPACE = 0x2C
    DELETE = 0x4C
    PAGE_UP = 0x4B
    PAGE_DOWN = 0x4E
    RIGHT = 0x4F
    LEFT = 0x50
    DOWN = 0x51
    UP = 0x52
    HOME = 0x4A
    END = 0x4D

# 按键名称映射
KEY_NAME_MAP = {
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
    KeyCode.F9: "F9", KeyCode.F10: "F10", KeyCode.F11: "F11", KeyCode.F12: "F12",
    KeyCode.ENTER: "Enter", KeyCode.ESCAPE: "Esc", KeyCode.BACKSPACE: "Backspace",
    KeyCode.TAB: "Tab", KeyCode.SPACE: "Space", KeyCode.DELETE: "Delete",
    KeyCode.PAGE_UP: "PgUp", KeyCode.PAGE_DOWN: "PgDn",
    KeyCode.UP: "↑", KeyCode.DOWN: "↓", KeyCode.LEFT: "←", KeyCode.RIGHT: "→",
    KeyCode.HOME: "Home", KeyCode.END: "End",
}

NAME_TO_KEY = {v: k for k, v in KEY_NAME_MAP.items()}

# 预设快捷键
PRESET_SHORTCUTS = {
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
    combos: List[KeyCombo] = field(default_factory=lambda: [KeyCombo() for _ in range(4)])
    enabled: bool = False
    name: str = ""

@dataclass
class CustomKeyConfig:
    """仅包含组0的3个按键配置"""
    keys: List[CustomKey] = field(default_factory=lambda: [CustomKey() for _ in range(3)])

# ============================================================================
# 管理器类
# ============================================================================

class CustomKeyManager:
    """自定义按键管理器 - 仅支持组0"""
    
    GROUP_ID = 0  # 固定为组0
    
    def __init__(self, send_command_func: Optional[Callable[[str], bool]] = None):
        self.config = CustomKeyConfig()
        self.send_command = send_command_func
        self._config_path = self._get_config_path()
        self.load_config()
    
    def _get_config_path(self) -> Path:
        system = platform.system().lower()
        if system == 'windows':
            base = Path(os.environ.get('APPDATA', ''))
        elif system == 'darwin':
            base = Path.home() / 'Library' / 'Application Support'
        else:
            base = Path.home() / '.config'
        
        config_dir = base / 'SuperKey'
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / 'custom_keys.json'
    
    def load_config(self):
        """从本地加载配置"""
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for ki, kdata in enumerate(data.get('keys', [])):
                        if ki < 3:
                            key = self.config.keys[ki]
                            key.enabled = kdata.get('enabled', False)
                            key.name = kdata.get('name', '')
                            for ci, cdata in enumerate(kdata.get('combos', [])):
                                if ci < 4:
                                    key.combos[ci].modifier = cdata.get('modifier', 0)
                                    key.combos[ci].keycode = cdata.get('keycode', 0)
        except Exception:
            pass
    
    def save_config(self):
        """保存配置到本地"""
        try:
            data = {'keys': []}
            for key in self.config.keys:
                kdata = {
                    'enabled': key.enabled,
                    'name': key.name,
                    'combos': [{'modifier': c.modifier, 'keycode': c.keycode} for c in key.combos]
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
        
        mod, keycode = PRESET_SHORTCUTS[preset_name]
        key = self.config.keys[key_idx]
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
    
    def set_combo(self, key_idx: int, combo_idx: int, modifier: int, keycode: int) -> bool:
        """设置单个组合键"""
        if key_idx < 0 or key_idx >= 3:
            return False
        if combo_idx < 0 or combo_idx >= 4:
            return False
        
        key = self.config.keys[key_idx]
        key.combos[combo_idx].modifier = modifier
        key.combos[combo_idx].keycode = keycode
        
        # 检查是否有任何有效的combo
        has_valid = any(c.keycode != 0 for c in key.combos)
        key.enabled = has_valid
        
        # 清除预设名称（因为是自定义的）
        key.name = ""
        
        self.save_config()
        return True
    
    def get_combo(self, key_idx: int, combo_idx: int) -> tuple:
        """获取单个组合键配置"""
        if key_idx < 0 or key_idx >= 3:
            return (0, 0)
        if combo_idx < 0 or combo_idx >= 4:
            return (0, 0)
        
        combo = self.config.keys[key_idx].combos[combo_idx]
        return (combo.modifier, combo.keycode)
    
    def get_combo_display_text(self, key_idx: int, combo_idx: int) -> str:
        """获取单个组合键的显示文本"""
        if key_idx < 0 or key_idx >= 3:
            return "无效"
        if combo_idx < 0 or combo_idx >= 4:
            return "无效"
        
        combo = self.config.keys[key_idx].combos[combo_idx]
        if combo.keycode == 0:
            return "无"
        
        parts = []
        if combo.modifier & Modifier.CTRL:
            parts.append("Ctrl")
        if combo.modifier & Modifier.SHIFT:
            parts.append("Shift")
        if combo.modifier & Modifier.ALT:
            parts.append("Alt")
        if combo.modifier & Modifier.GUI:
            parts.append("Win")
        
        key_name = KEY_NAME_MAP.get(combo.keycode, f"0x{combo.keycode:02X}")
        parts.append(key_name)
        
        return "+".join(parts)
    
    def clear_key(self, key_idx: int):
        """清除按键配置"""
        if key_idx < 0 or key_idx >= 3:
            return
        key = self.config.keys[key_idx]
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
        key = self.config.keys[key_idx]
        params = [str(self.GROUP_ID), str(key_idx)]
        
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
        
        cmd = self.generate_command(key_idx)
        return self.send_command(cmd)
    
    def sync_all_to_device(self) -> bool:
        """同步所有配置到设备（仅组0的3个按键）"""
        if self.send_command is None:
            return False
        
        success = True
        for ki in range(3):
            if not self.sync_key_to_device(ki):
                success = False
        return success
    
    def get_key_display_text(self, key_idx: int) -> str:
        """获取按键显示文本"""
        if key_idx < 0 or key_idx >= 3:
            return "无效"
        key = self.config.keys[key_idx]
        if not key.enabled:
            return "未配置"
        if key.name:
            return key.name
        
        # 生成显示文本
        combo = key.combos[0]
        parts = []
        if combo.modifier & Modifier.CTRL:
            parts.append("Ctrl")
        if combo.modifier & Modifier.SHIFT:
            parts.append("Shift")
        if combo.modifier & Modifier.ALT:
            parts.append("Alt")
        if combo.modifier & Modifier.GUI:
            parts.append("Win")
        
        key_name = KEY_NAME_MAP.get(combo.keycode, f"0x{combo.keycode:02X}")
        if key_name != "无":
            parts.append(key_name)
        
        return "+".join(parts) if parts else "未配置"


# 全局实例
_manager_instance: Optional[CustomKeyManager] = None

def get_custom_key_manager(send_func: Optional[Callable[[str], bool]] = None) -> CustomKeyManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = CustomKeyManager(send_func)
    elif send_func is not None:
        _manager_instance.send_command = send_func
    return _manager_instance


# 获取所有可用按键选项（用于UI下拉框）
def get_all_key_options() -> List[tuple]:
    """返回所有可用按键的列表 [(显示名称, keycode), ...]"""
    return [(name, code) for code, name in KEY_NAME_MAP.items()]


def get_modifier_options() -> List[tuple]:
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