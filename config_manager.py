#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块 - 跨平台支持
自动保存和加载应用配置

配置文件位置:
- Windows: %APPDATA%/SuperKey/superkey_config.json
- macOS: ~/Library/Application Support/SuperKey/superkey_config.json
- Linux: ~/.config/SuperKey/superkey_config.json
"""
import os
import json
import sys
import platform
from typing import Dict, Any, Optional
from pathlib import Path

# 平台检测
SYSTEM = platform.system().lower()
IS_WINDOWS = SYSTEM == 'windows'
IS_MACOS = SYSTEM == 'darwin'
IS_LINUX = SYSTEM == 'linux'


class ConfigManager:
    """跨平台应用配置管理器"""
    
    CONFIG_FILENAME = "superkey_config.json"
    
    def __init__(self):
        # 根据平台设置配置目录
        if IS_WINDOWS:
            # Windows: %APPDATA%/SuperKey
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            self.config_dir = Path(appdata) / 'SuperKey'
        elif IS_MACOS:
            # macOS: ~/Library/Application Support/SuperKey
            self.config_dir = Path.home() / 'Library' / 'Application Support' / 'SuperKey'
        else:
            # Linux: ~/.config/SuperKey
            config_home = os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')
            self.config_dir = Path(config_home) / 'SuperKey'
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.config_dir / self.CONFIG_FILENAME
        
        # 默认配置
        self._default_config = {
            'weather': {
                'api_key': '',
                'api_host': '',
                'use_jwt': False,
                'default_city': '杭州',
            },
            'serial': {
                'last_port': '',
                'auto_connect': True,
            },
            'app': {
                'minimize_to_tray': True,   # 关闭时最小化到托盘
                'auto_start': False,        # 开机自启动
            },
        }
        
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """从文件加载配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                return self._merge_config(self._default_config, loaded)
            except Exception:
                return self._default_config.copy()
        return self._default_config.copy()
    
    def _merge_config(self, default: Dict, loaded: Dict) -> Dict:
        """合并配置，保留默认值中缺失的键"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def get_config_path(self) -> str:
        """获取配置文件路径"""
        return str(self.config_path)
    
    # ===== 天气配置 =====
    
    def get_weather_config(self) -> Dict[str, Any]:
        """获取天气API配置"""
        return self._config.get('weather', {}).copy()
    
    def set_weather_config(self, api_key: str = None, api_host: str = None,
                          use_jwt: bool = None, default_city: str = None):
        """设置并保存天气API配置"""
        weather = self._config.setdefault('weather', {})
        
        if api_key is not None:
            weather['api_key'] = api_key
        if api_host is not None:
            weather['api_host'] = api_host
        if use_jwt is not None:
            weather['use_jwt'] = use_jwt
        if default_city is not None:
            weather['default_city'] = default_city
        
        self.save()
    
    # ===== 串口配置 =====
    
    def get_last_port(self) -> str:
        """获取上次使用的端口"""
        return self._config.get('serial', {}).get('last_port', '')
    
    def set_last_port(self, port: str):
        """保存上次使用的端口"""
        self._config.setdefault('serial', {})['last_port'] = port
        self.save()
    
    def should_auto_connect(self) -> bool:
        """是否自动连接"""
        return self._config.get('serial', {}).get('auto_connect', True)
    
    # ===== 应用配置 =====
    
    def should_minimize_to_tray(self) -> bool:
        """关闭时是否最小化到托盘"""
        return self._config.get('app', {}).get('minimize_to_tray', True)
    
    def set_minimize_to_tray(self, value: bool):
        """设置关闭时是否最小化到托盘"""
        self._config.setdefault('app', {})['minimize_to_tray'] = value
        self.save()
    
    def is_auto_start_enabled(self) -> bool:
        """是否开机自启动"""
        return self._config.get('app', {}).get('auto_start', False)
    
    def set_auto_start(self, value: bool):
        """设置开机自启动"""
        self._config.setdefault('app', {})['auto_start'] = value
        self.save()


# 全局实例
_instance: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """获取全局配置管理器"""
    global _instance
    if _instance is None:
        _instance = ConfigManager()
    return _instance


if __name__ == "__main__":
    # 测试
    cm = get_config_manager()
    print(f"平台: {SYSTEM}")
    print(f"配置文件路径: {cm.get_config_path()}")
    print(f"天气配置: {cm.get_weather_config()}")