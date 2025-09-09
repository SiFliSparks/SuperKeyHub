#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from enum import Enum

class DataCategory(Enum):
    TIME = "time"
    API = "api"
    PERFORMANCE = "performance"

class WeatherCodeMapper:
    CODE_MAPPING = {
        "晴": 0, "晴朗": 0, "sunny": 0, "clear": 0,
        "多云": 1, "cloudy": 1, "partly cloudy": 1,
        "阴": 2, "阴天": 2, "overcast": 2,
        "小雨": 3, "light rain": 3, "drizzle": 3,
        "中雨": 4, "moderate rain": 4, "rain": 4,
        "大雨": 5, "heavy rain": 5,
        "雷阵雨": 6, "thunderstorm": 6, "thunder": 6,
        "小雪": 7, "light snow": 7,
        "中雪": 8, "moderate snow": 8, "snow": 8,
        "大雪": 9, "heavy snow": 9,
        "雨夹雪": 10, "sleet": 10,
        "雾": 11, "fog": 11, "mist": 11,
        "霾": 12, "haze": 12,
        "沙尘": 13, "dust": 13, "sandstorm": 13,
        "晴转多云": 14,
        "多云转阴": 15,
        "阴转雨": 16,
    }
    
    @classmethod
    def get_weather_code(cls, description: str) -> int:
        if not description:
            return 99
        
        desc_lower = description.lower().strip()
        
        if desc_lower in cls.CODE_MAPPING:
            return cls.CODE_MAPPING[desc_lower]
        
        for key, code in cls.CODE_MAPPING.items():
            if key in desc_lower or desc_lower in key:
                return cls.CODE_MAPPING[key]
        
        return 99

class CityCodeMapper:
    CITY_MAPPING = {
        "杭州": 0, "hangzhou": 0,
        "上海": 1, "shanghai": 1, 
        "北京": 2, "beijing": 2,
        "广州": 3, "guangzhou": 3,
        "深圳": 4, "shenzhen": 4,
        "成都": 5, "chengdu": 5,
        "重庆": 6, "chongqing": 6,
        "武汉": 7, "wuhan": 7,
        "西安": 8, "xian": 8,
        "南京": 9, "nanjing": 9,
        "天津": 10, "tianjin": 10,
        "苏州": 11, "suzhou": 11,
        "青岛": 12, "qingdao": 12,
        "厦门": 13, "xiamen": 13,
        "长沙": 14, "changsha": 14,
    }
    
    @classmethod
    def get_city_code(cls, city_name: str) -> int:
        if not city_name:
            return 99
        
        city_lower = city_name.lower().strip()
        
        if city_lower in cls.CITY_MAPPING:
            return cls.CITY_MAPPING[city_lower]
        
        for key, code in cls.CITY_MAPPING.items():
            if key in city_lower or city_lower in key:
                return cls.CITY_MAPPING[key]
        
        return 99

class FinshDataSender:
    def __init__(self, serial_assistant=None):
        self.serial_assistant = serial_assistant
        
        self.enabled = False
        self.send_time_data = True
        self.send_api_data = True  
        self.send_performance_data = True
        
        self.intervals = {
            DataCategory.TIME: 1.0,
            DataCategory.API: 30.0,
            DataCategory.PERFORMANCE: 5.0
        }
        
        self.min_command_interval = 5
        
        self.data_providers = {
            DataCategory.TIME: self._get_time_data,
            DataCategory.API: self._get_api_data,
            DataCategory.PERFORMANCE: self._get_performance_data
        }
        
        self.hardware_monitor = None
        self.weather_api = None
        self.stock_api = None
        
        self.sender_threads = {}
        self.stop_event = threading.Event()
        
        self.stats = {
            'commands_sent': 0,
            'errors': 0,
            'last_send_time': None
        }
        
        self.data_cache = {}
        
    def set_data_sources(self, hardware_monitor=None, weather_api=None, stock_api=None):
        self.hardware_monitor = hardware_monitor
        self.weather_api = weather_api
        self.stock_api = stock_api
        
    def set_serial_assistant(self, serial_assistant):
        self.serial_assistant = serial_assistant
        
    def configure(self, **kwargs):
        if 'enabled' in kwargs:
            self.enabled = kwargs['enabled']
        if 'send_time_data' in kwargs:
            self.send_time_data = kwargs['send_time_data']
        if 'send_api_data' in kwargs:
            self.send_api_data = kwargs['send_api_data']
        if 'send_performance_data' in kwargs:
            self.send_performance_data = kwargs['send_performance_data']
        if 'time_interval' in kwargs:
            self.intervals[DataCategory.TIME] = max(0.1, float(kwargs['time_interval']))
        if 'api_interval' in kwargs:
            self.intervals[DataCategory.API] = max(1.0, float(kwargs['api_interval']))
        if 'performance_interval' in kwargs:
            self.intervals[DataCategory.PERFORMANCE] = max(0.5, float(kwargs['performance_interval']))
        if 'min_command_interval' in kwargs:
            self.min_command_interval = max(1, int(kwargs['min_command_interval']))
    
    def start(self):
        if not self.serial_assistant:
            return False
            
        if self.enabled:
            return True
            
        self.enabled = True
        self.stop_event.clear()
        
        if self.send_time_data:
            self._start_sender_thread(DataCategory.TIME)
        if self.send_api_data:
            self._start_sender_thread(DataCategory.API)
        if self.send_performance_data:
            self._start_sender_thread(DataCategory.PERFORMANCE)
        
        return True
    
    def stop(self):
        if not self.enabled:
            return
            
        self.enabled = False
        self.stop_event.set()
        
        for thread in self.sender_threads.values():
            if thread and thread.is_alive():
                thread.join(timeout=2)
                
        self.sender_threads.clear()
        
    def _start_sender_thread(self, category: DataCategory):
        if category in self.sender_threads:
            return
            
        thread = threading.Thread(
            target=self._sender_worker,
            args=(category,),
            daemon=True,
            name=f"FinshSender-{category.value}"
        )
        
        self.sender_threads[category] = thread
        thread.start()
        
    def _sender_worker(self, category: DataCategory):
        interval = self.intervals[category]
        data_provider = self.data_providers[category]
        
        try:
            data_dict = data_provider()
            self._send_data_dict(data_dict)
        except Exception as e:
            self.stats['errors'] += 1
        
        last_send = time.time()
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                if current_time - last_send >= interval:
                    data_dict = data_provider()
                    if data_dict:
                        self._send_data_dict(data_dict)
                        last_send = current_time
                
                time.sleep(min(0.1, interval / 10))
                
            except Exception as e:
                self.stats['errors'] += 1
                time.sleep(1)
                
    def _send_data_dict(self, data_dict: Dict[str, Any]):
        if not data_dict or not self.serial_assistant or not self.serial_assistant.is_connected:
            return
            
        for key, value in data_dict.items():
            if value is not None:
                try:
                    command = self._format_command(key, value)
                    self._send_command(command)
                    if self.min_command_interval > 0:
                        time.sleep(self.min_command_interval / 1000.0)
                except Exception as e:
                    self.stats['errors'] += 1
                    
    def _format_command(self, key: str, value: Any) -> str:
        if isinstance(value, str):
            return f'sys_set {key} "{value}"\n'
        elif isinstance(value, (int, float)):
            if isinstance(value, float):
                return f'sys_set {key} {value:.2f}\n'
            else:
                return f'sys_set {key} {value}\n'
        else:
            return f'sys_set {key} "{str(value)}"\n'
            
    def _send_command(self, command: str):
        if self.serial_assistant and self.serial_assistant.is_connected:
            success = self.serial_assistant.send_data(command)
            if success:
                self.stats['commands_sent'] += 1
                self.stats['last_send_time'] = datetime.now()
            else:
                self.stats['errors'] += 1
                
    def _get_time_data(self) -> Dict[str, Any]:
        now = datetime.now()
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        return {
            'time': now.strftime('%H:%M:%S'),
            'date': now.strftime('%Y-%m-%d'), 
            'weekday': weekdays[now.weekday()]
        }
        
    def _get_api_data(self) -> Dict[str, Any]:
        data = {}
        
        if self.weather_api:
            try:
                weather_data = self.weather_api.get_weather_data()
                if weather_data.get('success', False):
                    data.update({
                        'temp': int(round(weather_data.get('temperature', 0))),
                        'weather_code': WeatherCodeMapper.get_weather_code(weather_data.get('description', '')),
                        'humidity': int(weather_data.get('humidity', 0)),
                        'pressure': int(weather_data.get('pressure', 0)),
                        'city_code': CityCodeMapper.get_city_code(weather_data.get('city_name', ''))
                    })
            except Exception:
                pass
                
        if self.stock_api:
            try:
                stock_data = self.stock_api.get_stock_data()
                if stock_data.get('success', False):
                    data.update({
                        'stock_name': stock_data.get('name', ''),
                        'stock_price': float(stock_data.get('price', 0)),
                        'stock_change': float(stock_data.get('change', 0))
                    })
            except Exception:
                pass
                
        return data
        
    def _get_performance_data(self) -> Dict[str, Any]:
        if not self.hardware_monitor:
            return {}
            
        data = {}
        
        try:
            cpu_data = self.hardware_monitor.get_cpu_data()
            data['cpu'] = float(cpu_data.get('usage', 0) or 0)
            data['cpu_temp'] = float(cpu_data.get('temp', 0) or 0)
            
            mem_data = self.hardware_monitor.get_memory_data()
            data['mem'] = float(mem_data.get('percent', 0) or 0)
            
            gpu_data = self.hardware_monitor.get_gpu_data(0)
            data['gpu'] = float(gpu_data.get('util', 0) or 0)
            data['gpu_temp'] = float(gpu_data.get('temp', 0) or 0)
            
            net_data = self.hardware_monitor.get_network_data()
            net_up = net_data.get('up', 0) or 0
            net_down = net_data.get('down', 0) or 0
            data['net_up'] = round(net_up / (1024 * 1024), 2) if net_up else 0.0
            data['net_down'] = round(net_down / (1024 * 1024), 2) if net_down else 0.0
            
        except Exception:
            pass
            
        return data
        
    def send_test_sequence(self):
        if not self.serial_assistant or not self.serial_assistant.is_connected:
            return False
        
        test_commands = [
            'sys_set time "12:34:56"',
            'sys_set date "2025-08-27"', 
            'sys_set weekday "Tuesday"',
            'sys_set temp 25',
            'sys_set weather_code 1',
            'sys_set humidity 65',
            'sys_set pressure 1013',
            'sys_set city_code 0',
            'sys_set stock_name "上证指数"',
            'sys_set stock_price 3245.67',
            'sys_set stock_change -12.34',
            'sys_set cpu 45.2',
            'sys_set cpu_temp 68.5',
            'sys_set mem 72.1',
            'sys_set gpu 89.3',
            'sys_set gpu_temp 75.0',
            'sys_set net_up 12.5',
            'sys_set net_down 45.8'
        ]
        
        success_count = 0
        for cmd in test_commands:
            try:
                command = cmd + '\n'
                success = self.serial_assistant.send_data(command)
                if success:
                    success_count += 1
                
                time.sleep(self.min_command_interval / 1000.0)
                
            except Exception:
                pass
                
        return success_count == len(test_commands)
        
    def get_status(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'connected': self.serial_assistant.is_connected if self.serial_assistant else False,
            'send_time_data': self.send_time_data,
            'send_api_data': self.send_api_data, 
            'send_performance_data': self.send_performance_data,
            'intervals': dict(self.intervals),
            'min_command_interval': self.min_command_interval,
            'stats': dict(self.stats),
            'active_threads': len([t for t in self.sender_threads.values() if t and t.is_alive()])
        }
        
    def get_configuration(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'send_time_data': self.send_time_data,
            'send_api_data': self.send_api_data,
            'send_performance_data': self.send_performance_data,
            'time_interval': self.intervals[DataCategory.TIME],
            'api_interval': self.intervals[DataCategory.API], 
            'performance_interval': self.intervals[DataCategory.PERFORMANCE],
            'min_command_interval': self.min_command_interval
        }
        
    def __del__(self):
        self.stop()