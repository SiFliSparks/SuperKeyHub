#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

class StockAPI:
    def __init__(self, default_symbol: str = "1010"):
        self.appkey = "77232"
        self.sign = "773480ccda0000da98e9e159fb1e653b"
        
        self.api_url = "https://sapi.k780.com/"
        
        self.supported_indexes = {
            '1010': '上证指数',
            '1011': '深证成指', 
            '1012': '沪深300',
            '1013': '创业板指',
            '1014': '中小板指',
            '1015': '恒生指数',
            '1016': '国企指数', 
            '1017': '红筹指数',
            '1111': '道琼斯',
            '1112': '标普500',
            '1114': '纳斯达克'
        }
        
        if default_symbol in self.supported_indexes:
            self.current_index = default_symbol
        else:
            self.current_index = "1010"
        
        self.cache = {}
        self.cache_duration = 1800
        self.last_request_time = 0
    
    def switch_to_index(self, index_code: str) -> bool:
        if index_code not in self.supported_indexes:
            return False
        
        self.current_index = index_code
        self._fetch_current_index_data(force_update=True)
        return True
    
    def get_supported_indexes(self) -> Dict[str, str]:
        return self.supported_indexes.copy()
    
    def get_current_index_info(self) -> Dict[str, str]:
        return {
            'code': self.current_index,
            'name': self.supported_indexes.get(self.current_index, '未知指数')
        }
    
    def _should_use_cache(self, symbol: str) -> bool:
        if symbol in self.cache:
            cache_time = self.cache[symbol].get('timestamp', 0)
            return time.time() - cache_time < self.cache_duration
        return False
    
    def _fetch_current_index_data(self, force_update: bool = False) -> Optional[Dict[str, Any]]:
        index_code = self.current_index
        
        if not force_update and self._should_use_cache(index_code):
            return self.cache[index_code]['data']
        
        data = self._fetch_single_index(index_code)
        
        if data:
            self.cache[index_code] = {
                'data': data,
                'timestamp': time.time()
            }
            return data
        else:
            error_data = {
                'symbol': index_code,
                'name': self.supported_indexes.get(index_code, index_code),
                'price': 0,
                'change': 0,
                'change_percent': 0,
                'volume': 0,
                'turnover': 0,
                'source': 'API错误',
                'update_time': datetime.now().strftime('%H:%M:%S'),
                'success': False
            }
            return error_data
    
    def _get_remaining_cache_time(self, symbol: str) -> str:
        if symbol not in self.cache:
            return "立即"
        
        cache_time = self.cache[symbol].get('timestamp', 0)
        next_update = cache_time + self.cache_duration
        remaining = next_update - time.time()
        
        if remaining <= 0:
            return "立即"
        
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        
        if hours > 0:
            return f"{hours}小时{minutes}分后"
        elif minutes > 0:
            return f"{minutes}分{seconds}秒后"
        else:
            return f"{seconds}秒后"
    
    def _fetch_single_index(self, inxid: str) -> Optional[Dict[str, Any]]:
        try:
            params = {
                'app': 'finance.globalindex',
                'inxids': inxid,
                'appkey': self.appkey,
                'sign': self.sign,
                'format': 'json'
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.post(self.api_url, data=params, headers=headers, timeout=10)
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success') == '1' or data.get('success') == 1:
                    result = data.get('result', {})
                    lists = result.get('lists', {})
                    
                    if inxid in lists:
                        index_data = lists[inxid]
                        
                        try:
                            current_price = float(index_data.get('last_price', 0))
                            rise_fall = float(index_data.get('rise_fall', 0))
                            rise_fall_per = index_data.get('rise_fall_per', '0%').replace('%', '')
                            rise_fall_per = float(rise_fall_per)
                            
                            volume_str = index_data.get('volume', '0')
                            turnover_str = index_data.get('turnover', '0')
                            
                            try:
                                volume = int(volume_str) if volume_str.isdigit() else 0
                                turnover = int(turnover_str) if turnover_str.isdigit() else 0
                            except:
                                volume = 0
                                turnover = 0
                            
                            return {
                                'symbol': inxid,
                                'name': self.supported_indexes.get(inxid, index_data.get('inxnm', inxid)),
                                'price': current_price,
                                'change': rise_fall,
                                'change_percent': rise_fall_per,
                                'volume': volume,
                                'turnover': turnover,
                                'source': 'K780 API',
                                'update_time': index_data.get('uptime', datetime.now().strftime('%H:%M:%S')),
                                'success': True
                            }
                        except Exception:
                            return None
                else:
                    return None
            else:
                return None
                
        except Exception:
            return None
    
    def get_stock_data(self, symbol: str = None, force_refresh: bool = False) -> Dict[str, Any]:
        if symbol is None:
            symbol = self.current_index
            
        if symbol not in self.supported_indexes:
            symbol = self.current_index
        
        if symbol == self.current_index:
            raw_data = self._fetch_current_index_data(force_update=force_refresh)
        else:
            raw_data = self._fetch_single_index(symbol)
            if raw_data is None:
                raw_data = {
                    'symbol': symbol,
                    'name': self.supported_indexes.get(symbol, symbol),
                    'price': 0,
                    'change': 0,
                    'change_percent': 0,
                    'volume': 0,
                    'turnover': 0,
                    'source': 'API错误',
                    'update_time': datetime.now().strftime('%H:%M:%S'),
                    'success': False
                }
        
        if raw_data is None:
            raw_data = {
                'symbol': self.current_index,
                'name': self.supported_indexes.get(self.current_index, self.current_index),
                'price': 0,
                'change': 0,
                'change_percent': 0,
                'volume': 0,
                'turnover': 0,
                'source': 'API错误',
                'update_time': datetime.now().strftime('%H:%M:%S'),
                'success': False
            }
        
        return raw_data
    
    def get_formatted_data(self, symbol: str = None, force_refresh: bool = False) -> Dict[str, Any]:
        raw_data = self.get_stock_data(symbol, force_refresh)
        
        return {
            'stock_symbol': raw_data['symbol'],
            'stock_name': raw_data['name'],
            'stock_price': raw_data['price'],
            'stock_change': raw_data['change'],
            'stock_change_percent': raw_data['change_percent'],
            'stock_volume': raw_data['volume'],
            'stock_turnover': raw_data['turnover'],
            'stock_source': raw_data['source'],
            'stock_update_time': raw_data['update_time'],
            'stock_api_success': raw_data.get('success', False),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_all_formatted_data(self) -> List[Dict[str, Any]]:
        current_data = self.get_formatted_data()
        return [current_data]
    
    def force_update_current_index(self) -> Dict[str, Any]:
        return self._fetch_current_index_data(force_update=True)
    
    def set_default_symbol(self, symbol: str):
        return self.switch_to_index(symbol)
    
    def clear_cache(self, symbol: str = None):
        if symbol:
            if symbol in self.cache:
                del self.cache[symbol]
        else:
            self.cache.clear()
    
    def get_cache_status(self) -> Dict[str, Any]:
        cache_info = {}
        for symbol, data in self.cache.items():
            cache_time = data.get('timestamp', 0)
            age = time.time() - cache_time
            remaining = max(0, self.cache_duration - age)
            
            cache_info[symbol] = {
                'name': self.supported_indexes.get(symbol, symbol),
                'age_minutes': round(age / 60, 1),
                'remaining_minutes': round(remaining / 60, 1),
                'valid': remaining > 0,
                'source': data['data'].get('source', '未知')
            }
        
        return {
            'cached_symbols': list(self.cache.keys()),
            'cache_count': len(self.cache),
            'cache_duration_minutes': self.cache_duration // 60,
            'current_index': self.current_index,
            'current_index_name': self.supported_indexes.get(self.current_index),
            'supported_indexes': self.supported_indexes,
            'cache_details': cache_info,
            'update_frequency': '每30分钟更新一次',
            'last_request_time': self.last_request_time,
            'api_configured': True
        }