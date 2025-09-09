#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

class QWeatherAPI:
    def __init__(self, api_key: str = "", default_city: str = "hangzhou", api_host: str = "", use_jwt: bool = False):
        self.api_key = api_key or ""
        self.default_city = default_city
        self.use_jwt = use_jwt
        
        if api_host:
            self.api_host = api_host.rstrip('/')
            if not api_host.startswith(('http://', 'https://')):
                self.api_host = f"https://{api_host}"
        else:
            self.api_host = "https://devapi.qweather.com"
        
        if self.api_host == "https://devapi.qweather.com":
            self.base_url = f"{self.api_host}/v7"
            self.geo_url = "https://geoapi.qweather.com/v2"
        else:
            self.base_url = f"{self.api_host}/v7"
            self.geo_url = f"{self.api_host}/v2"
        
        self.city_id_cache = {}
        self.predefined_cities = {
            "北京": "101010100", "上海": "101020100", "天津": "101030100", "重庆": "101040100",
            "哈尔滨": "101050101", "长春": "101060101", "沈阳": "101070101", "呼和浩特": "101080101",
            "石家庄": "101090101", "太原": "101100101", "济南": "101120101", "南京": "101190101", 
            "杭州": "101210101", "合肥": "101220101", "福州": "101230101", "南昌": "101240101",
            "郑州": "101180101", "武汉": "101200101", "长沙": "101250101", "广州": "101280101",
            "南宁": "101300101", "海口": "101310101", "成都": "101270101", "贵阳": "101260101",
            "昆明": "101290101", "拉萨": "101140101", "西安": "101110101", "兰州": "101160101",
            "西宁": "101150101", "银川": "101170101", "乌鲁木齐": "101130101",
            "大连": "101070201", "青岛": "101120201", "宁波": "101210401", "温州": "101210301",
            "苏州": "101190401", "无锡": "101190201", "常州": "101191001", "扬州": "101190701",
            "徐州": "101190301", "厦门": "101230201", "泉州": "101230501", "洛阳": "101180801",
            "开封": "101181001", "深圳": "101280601", "珠海": "101280701", "佛山": "101280800",
            "东莞": "101281601", "中山": "101281701", "桂林": "101300501", "三亚": "101310201",
            "beijing": "101010100", "shanghai": "101020100", "tianjin": "101030100", "chongqing": "101040100",
            "harbin": "101050101", "changchun": "101060101", "shenyang": "101070101", "hohhot": "101080101",
            "shijiazhuang": "101090101", "taiyuan": "101100101", "jinan": "101120101", "nanjing": "101190101",
            "hangzhou": "101210101", "hefei": "101220101", "fuzhou": "101230101", "nanchang": "101240101",
            "zhengzhou": "101180101", "wuhan": "101200101", "changsha": "101250101", "guangzhou": "101280101",
            "nanning": "101300101", "haikou": "101310101", "chengdu": "101270101", "guiyang": "101260101",
            "kunming": "101290101", "lhasa": "101140101", "xian": "101110101", "lanzhou": "101160101",
            "xining": "101150101", "yinchuan": "101170101", "urumqi": "101130101",
            "dalian": "101070201", "qingdao": "101120201", "ningbo": "101210401", "wenzhou": "101210301",
            "suzhou": "101190401", "wuxi": "101190201", "changzhou": "101191001", "yangzhou": "101190701",
            "xuzhou": "101190301", "xiamen": "101230201", "quanzhou": "101230501", "luoyang": "101180801",
            "kaifeng": "101181001", "shenzhen": "101280601", "zhuhai": "101280701", "foshan": "101280800",
            "dongguan": "101281601", "zhongshan": "101281701", "guilin": "101300501", "sanya": "101310201",
            "Beijing": "101010100", "Shanghai": "101020100", "Tianjin": "101030100", "Chongqing": "101040100",
            "Harbin": "101050101", "Changchun": "101060101", "Shenyang": "101070101", "Hohhot": "101080101",
            "Shijiazhuang": "101090101", "Taiyuan": "101100101", "Jinan": "101120101", "Nanjing": "101190101",
            "Hangzhou": "101210101", "Hefei": "101220101", "Fuzhou": "101230101", "Nanchang": "101240101",
            "Zhengzhou": "101180101", "Wuhan": "101200101", "Changsha": "101250101", "Guangzhou": "101280101",
            "Nanning": "101300101", "Haikou": "101310101", "Chengdu": "101270101", "Guiyang": "101260101",
            "Kunming": "101290101", "Lhasa": "101140101", "Xian": "101110101", "Lanzhou": "101160101",
            "Xining": "101150101", "Yinchuan": "101170101", "Urumqi": "101130101",
            "Dalian": "101070201", "Qingdao": "101120201", "Ningbo": "101210401", "Wenzhou": "101210301",
            "Suzhou": "101190401", "Wuxi": "101190201", "Changzhou": "101191001", "Yangzhou": "101190701",
            "Xuzhou": "101190301", "Xiamen": "101230201", "Quanzhou": "101230501", "Luoyang": "101180801",
            "Kaifeng": "101181001", "Shenzhen": "101280601", "Zhuhai": "101280701", "Foshan": "101280800",
            "Dongguan": "101281601", "Zhongshan": "101281701", "Guilin": "101300501", "Sanya": "101310201"
        }
        
        self.cache = {}
        self.cache_duration = 600

    def update_config(self, api_key: str = None, api_host: str = None, 
                      use_jwt: bool = None, default_city: str = None):
        config_changed = False
        
        if api_key is not None and api_key != self.api_key:
            self.api_key = api_key
            config_changed = True
            
        if api_host is not None:
            normalized_host = api_host.strip()
            if normalized_host and not normalized_host.startswith(('http://', 'https://')):
                normalized_host = f"https://{normalized_host}"
            elif not normalized_host:
                normalized_host = "https://devapi.qweather.com"
            
            if normalized_host != self.api_host:
                self.api_host = normalized_host
                
                if self.api_host == "https://devapi.qweather.com":
                    self.base_url = f"{self.api_host}/v7"
                    self.geo_url = "https://geoapi.qweather.com/v2"
                else:
                    self.base_url = f"{self.api_host}/v7"
                    self.geo_url = f"{self.api_host}/v2"
                
                config_changed = True
            
        if use_jwt is not None and use_jwt != self.use_jwt:
            self.use_jwt = use_jwt
            config_changed = True
            
        if default_city is not None and default_city != self.default_city:
            self.default_city = default_city
            config_changed = True
        
        if config_changed:
            self.clear_cache()
            
        return config_changed

    def get_config(self) -> Dict[str, Any]:
        return {
            'api_key': self.api_key,
            'api_host': self.api_host,
            'geo_url': self.geo_url,
            'use_jwt': self.use_jwt,
            'default_city': self.default_city,
            'api_configured': bool(self.api_key)
        }

    def set_api_key(self, api_key: str):
        self.update_config(api_key=api_key)

    def set_default_city(self, city: str):
        self.update_config(default_city=city)

    def _get_request_headers(self) -> Dict[str, str]:
        headers = {
            'User-Agent': 'QWeatherAPI/1.0',
            'Accept-Encoding': 'gzip'
        }
        
        if self.use_jwt:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        return headers
    
    def _get_request_params(self, base_params: Dict[str, str]) -> Dict[str, str]:
        if not self.use_jwt:
            base_params['key'] = self.api_key
        
        return base_params

    def _get_city_id(self, city: str) -> str:
        if city in self.city_id_cache:
            return self.city_id_cache[city]
        
        if city in self.predefined_cities:
            city_id = self.predefined_cities[city]
            self.city_id_cache[city] = city_id
            self.city_id_cache[f"{city}_name"] = city
            return city_id
        
        city_id = self._try_geo_api(city, "https://geoapi.qweather.com/v2/city/lookup")
        if city_id:
            return city_id
        
        if self.api_host != "https://devapi.qweather.com":
            for path in ["/v2/city/lookup", "/city/lookup", "/geo/city/lookup"]:
                city_id = self._try_geo_api(city, f"{self.api_host}{path}")
                if city_id:
                    return city_id
        
        try:
            params = self._get_request_params({'location': city})
            headers = self._get_request_headers()
            response = requests.get(f"{self.base_url}/weather/now", 
                                  params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '200' and data.get('now'):
                    self.city_id_cache[city] = city
                    self.city_id_cache[f"{city}_name"] = city
                    return city
        except:
            pass
        
        return ""
    
    def _try_geo_api(self, city: str, api_url: str) -> str:
        try:
            params = self._get_request_params({'location': city, 'number': '1'})
            headers = self._get_request_headers()
            
            response = requests.get(api_url, params=params, headers=headers, timeout=8)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '200' and data.get('location'):
                    city_id = data['location'][0]['id']
                    city_name = data['location'][0]['name']
                    self.city_id_cache[city] = city_id
                    self.city_id_cache[f"{city}_name"] = city_name
                    return city_id
        except:
            pass
        
        return ""

    def get_city_name(self, city: str) -> str:
        self._get_city_id(city)
        return self.city_id_cache.get(f"{city}_name", city)

    def _should_use_cache(self, city: str) -> bool:
        cache_key = f"weather_{city}"
        if cache_key in self.cache:
            cache_time = self.cache[cache_key].get('timestamp', 0)
            return time.time() - cache_time < self.cache_duration
        return False

    def _fetch_current_weather(self, city: str) -> Optional[Dict[str, Any]]:
        try:
            city_id = self._get_city_id(city)
            if not city_id:
                return None
            
            params = self._get_request_params({'location': city_id})
            headers = self._get_request_headers()
            
            response = requests.get(f"{self.base_url}/weather/now", 
                                  params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('code') == '200' and data.get('now'):
                    now = data['now']
                    city_name = self.get_city_name(city)
                    
                    return {
                        'temperature': float(now.get('temp', 0)),
                        'feels_like': float(now.get('feelsLike', 0)),
                        'description': now.get('text', '未知'),
                        'icon_code': now.get('icon', '999'),
                        'wind_direction_360': int(now.get('wind360', 0)),
                        'wind_direction': now.get('windDir', '无风'),
                        'wind_scale': now.get('windScale', '0'),
                        'wind_speed': float(now.get('windSpeed', 0)),
                        'humidity': int(now.get('humidity', 0)),
                        'precipitation': float(now.get('precip', 0)),
                        'pressure': float(now.get('pressure', 0)),
                        'visibility': float(now.get('vis', 0)),
                        'cloud_cover': int(now.get('cloud', 0)),
                        'dew_point': float(now.get('dew', 0)),
                        'city_name': city_name,
                        'city_id': city_id,
                        'city_input': city,
                        'update_time': data.get('updateTime', ''),
                        'obs_time': now.get('obsTime', ''),
                        'source': '和风天气API',
                        'success': True
                    }
        except:
            pass
        
        return None

    def _fetch_weather_forecast(self, city: str, days: int = 3) -> Optional[List[Dict[str, Any]]]:
        try:
            city_id = self._get_city_id(city)
            if not city_id:
                return None
            
            endpoint = "weather/3d" if days <= 3 else "weather/7d"
            if days > 7:
                days = 7
            
            params = self._get_request_params({'location': city_id})
            headers = self._get_request_headers()
            
            response = requests.get(f"{self.base_url}/{endpoint}", 
                                  params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('code') == '200' and data.get('daily'):
                    forecast_list = []
                    
                    for daily in data['daily'][:days]:
                        forecast_data = {
                            'date': daily.get('fxDate', ''),
                            'sunrise': daily.get('sunrise', ''),
                            'sunset': daily.get('sunset', ''),
                            'moonrise': daily.get('moonrise', ''),
                            'moonset': daily.get('moonset', ''),
                            'moon_phase': daily.get('moonPhase', ''),
                            'temp_max': int(daily.get('tempMax', 0)),
                            'temp_min': int(daily.get('tempMin', 0)),
                            'icon_day': daily.get('iconDay', '999'),
                            'text_day': daily.get('textDay', '未知'),
                            'icon_night': daily.get('iconNight', '999'),
                            'text_night': daily.get('textNight', '未知'),
                            'wind360_day': int(daily.get('wind360Day', 0)),
                            'wind_dir_day': daily.get('windDirDay', '无风'),
                            'wind_scale_day': daily.get('windScaleDay', '0'),
                            'wind_speed_day': int(daily.get('windSpeedDay', 0)),
                            'wind360_night': int(daily.get('wind360Night', 0)),
                            'wind_dir_night': daily.get('windDirNight', '无风'),
                            'wind_scale_night': daily.get('windScaleNight', '0'),
                            'wind_speed_night': int(daily.get('windSpeedNight', 0)),
                            'humidity': int(daily.get('humidity', 0)),
                            'precipitation': float(daily.get('precip', 0)),
                            'pressure': float(daily.get('pressure', 0)),
                            'visibility': float(daily.get('vis', 0)),
                            'cloud_cover': int(daily.get('cloud', 0)),
                            'uv_index': int(daily.get('uvIndex', 0))
                        }
                        forecast_list.append(forecast_data)
                    
                    return forecast_list
        except:
            pass
        
        return None

    def get_weather_data(self, city: str = None, force_refresh: bool = False) -> Dict[str, Any]:
        if city is None:
            city = self.default_city
            
        cache_key = f"weather_{city}"
        
        if not force_refresh and self._should_use_cache(city):
            return self.cache[cache_key]['data']
        
        weather_data = self._fetch_current_weather(city)
        forecast_data = self._fetch_weather_forecast(city, 3)
        
        if weather_data is None:
            weather_data = {
                'temperature': 0, 'feels_like': 0, 'description': 'API错误',
                'icon_code': '999', 'wind_direction_360': 0, 'wind_direction': '无风',
                'wind_scale': '0', 'wind_speed': 0, 'humidity': 0, 'precipitation': 0,
                'pressure': 0, 'visibility': 0, 'cloud_cover': 0, 'dew_point': 0,
                'city_name': city, 'city_id': '', 'city_input': city,
                'update_time': '', 'obs_time': '', 'source': 'API错误', 'success': False
            }
        else:
            self.cache[cache_key] = {'data': weather_data, 'timestamp': time.time()}
        
        weather_data['forecast'] = forecast_data or []
        
        return weather_data

    def get_formatted_data(self, city: str = None, force_refresh: bool = False) -> Dict[str, Any]:
        raw_data = self.get_weather_data(city, force_refresh)
        
        wind_display = f"{raw_data['wind_direction']} {raw_data['wind_scale']}级"
        if raw_data['wind_speed'] > 0:
            wind_display += f" ({raw_data['wind_speed']}km/h)"
        
        def get_weather_quality(temp, humidity, vis, pressure):
            score = 100
            if temp < -10 or temp > 38: score -= 30
            elif temp < 0 or temp > 35: score -= 15
            if humidity > 80 or humidity < 20: score -= 15
            if vis < 3: score -= 20
            elif vis < 10: score -= 10
            if pressure < 990 or pressure > 1040: score -= 10
            
            if score >= 85: return "优秀"
            elif score >= 70: return "良好"
            elif score >= 50: return "一般"
            else: return "较差"
        
        weather_quality = get_weather_quality(
            raw_data['temperature'], raw_data['humidity'], 
            raw_data['visibility'], raw_data['pressure']
        )
        
        return {
            'weather_temp': raw_data['temperature'],
            'weather_feels_like': raw_data['feels_like'],
            'weather_desc': raw_data['description'],
            'weather_icon': raw_data['icon_code'],
            'weather_city': raw_data['city_name'],
            'weather_source': raw_data['source'],
            'weather_update_time': raw_data['update_time'],
            'weather_obs_time': raw_data['obs_time'],
            'weather_api_success': raw_data['success'],
            'weather_humidity': raw_data['humidity'],
            'weather_pressure': raw_data['pressure'],
            'weather_visibility': raw_data['visibility'],
            'weather_cloud_cover': raw_data['cloud_cover'],
            'weather_dew_point': raw_data['dew_point'],
            'weather_precipitation': raw_data['precipitation'],
            'weather_wind_direction': raw_data['wind_direction'],
            'weather_wind_direction_360': raw_data['wind_direction_360'],
            'weather_wind_scale': raw_data['wind_scale'],
            'weather_wind_speed': raw_data['wind_speed'],
            'weather_wind_display': wind_display,
            'weather_quality': weather_quality,
            'weather_comfort_index': self._calculate_comfort_index(
                raw_data['temperature'], raw_data['humidity'], raw_data['wind_speed']
            ),
            'weather_forecast': raw_data.get('forecast', []),
            'weather_forecast_count': len(raw_data.get('forecast', [])),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _calculate_comfort_index(self, temp: float, humidity: int, wind_speed: float) -> str:
        if 18 <= temp <= 26 and 40 <= humidity <= 70 and wind_speed <= 20:
            if 20 <= temp <= 24 and 45 <= humidity <= 65:
                return "非常舒适"
            else:
                return "舒适"
        elif 15 <= temp <= 30 and 30 <= humidity <= 80:
            return "较舒适"
        elif 10 <= temp <= 35 and 20 <= humidity <= 90:
            return "一般"
        else:
            return "不舒适"

    def get_all_cities(self) -> Dict[str, str]:
        cities = {}
        for key, value in self.city_id_cache.items():
            if not key.endswith('_name'):
                city_name = self.city_id_cache.get(f"{key}_name", key)
                cities[key] = city_name
        return cities

    def validate_config(self) -> Dict[str, Any]:
        issues = []
        
        if not self.api_key:
            issues.append("API密钥未设置")
        elif len(self.api_key) < 10:
            issues.append("API密钥格式可能不正确")
            
        if not self.api_host:
            issues.append("API Host未设置")
        elif not self.api_host.startswith('http'):
            issues.append("API Host格式不正确，应以http://或https://开头")
            
        if not self.default_city:
            issues.append("默认城市未设置")
            
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'config': self.get_config()
        }

    def test_connection(self) -> Dict[str, Any]:
        try:
            test_city = self.default_city or "北京"
            result = self.get_weather_data(test_city, force_refresh=True)
            
            if result.get('success', False):
                return {
                    'success': True,
                    'message': f'API连接成功，获取到{result["city_name"]}天气数据',
                    'data': {
                        'city': result["city_name"],
                        'temperature': result["temperature"],
                        'description': result["description"]
                    }
                }
            else:
                return {
                    'success': False,
                    'message': 'API连接失败，请检查配置',
                    'error': 'API返回数据异常'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'API连接测试失败: {str(e)}',
                'error': str(e)
            }

    def clear_cache(self, city: str = None):
        if city:
            cache_key = f"weather_{city}"
            if cache_key in self.cache:
                del self.cache[cache_key]
        else:
            self.cache.clear()

    def get_cache_status(self) -> Dict[str, Any]:
        cache_info = {}
        for key, data in self.cache.items():
            city = key.replace('weather_', '')
            cache_time = data.get('timestamp', 0)
            age = time.time() - cache_time
            remaining = max(0, self.cache_duration - age)
            
            cache_info[city] = {
                'age_minutes': round(age / 60, 1),
                'remaining_minutes': round(remaining / 60, 1),
                'valid': remaining > 0,
                'source': data['data'].get('source', '未知')
            }
        
        return {
            'cached_cities': [k.replace('weather_', '') for k in self.cache.keys()],
            'cache_count': len(self.cache),
            'cache_duration_minutes': self.cache_duration // 60,
            'default_city': self.default_city,
            'api_configured': bool(self.api_key),
            'api_key_masked': f"{self.api_key[:8]}***{self.api_key[-4:]}" if len(self.api_key) > 12 else "未配置",
            'cache_details': cache_info
        }

WeatherAPI = QWeatherAPI