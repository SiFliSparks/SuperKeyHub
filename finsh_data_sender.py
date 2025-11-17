#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

class DataCategory(Enum):
    TIME = "time"
    API = "api"
    PERFORMANCE = "performance"

class CityCodeMapper:
    CITY_MAPPING = {
        # Popular cities
        "未知": 999, "Error": 999,
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
        
        # Hebei Province
        "石家庄": 15, "shijiazhuang": 15,
        "唐山": 16, "tangshan": 16,
        "秦皇岛": 17, "qinhuangdao": 17,
        "邯郸": 18, "handan": 18,
        "邢台": 19, "xingtai": 19,
        "保定": 20, "baoding": 20,
        "张家口": 21, "zhangjiakou": 21,
        "承德": 22, "chengde": 22,
        "沧州": 23, "cangzhou": 23,
        "廊坊": 24, "langfang": 24,
        "衡水": 25, "hengshui": 25,
        
        # Shanxi Province
        "太原": 26, "taiyuan": 26,
        "大同": 27, "datong": 27,
        "阳泉": 28, "yangquan": 28,
        "长治": 29, "changzhi": 29,
        "晋城": 30, "jincheng": 30,
        "朔州": 31, "shuozhou": 31,
        "晋中": 32, "jinzhong": 32,
        "运城": 33, "yuncheng": 33,
        "忻州": 34, "xinzhou": 34,
        "临汾": 35, "linfen": 35,
        "吕梁": 36, "lvliang": 36,
        
        # the Nei Monggol [Inner Mongolia] Autonomous Region
        "呼和浩特": 37, "hohhot": 37,
        "包头": 38, "baotou": 38,
        "乌海": 39, "wuhai": 39,
        "赤峰": 40, "chifeng": 40,
        "通辽": 41, "tongliao": 41,
        "鄂尔多斯": 42, "ordos": 42,
        "呼伦贝尔": 43, "hulunbuir": 43,
        "巴彦淖尔": 44, "bayannur": 44,
        "乌兰察布": 45, "ulanqab": 45,
        
        # Liaoning Province
        "沈阳": 46, "shenyang": 46,
        "大连": 47, "dalian": 47,
        "鞍山": 48, "anshan": 48,
        "抚顺": 49, "fushun": 49,
        "本溪": 50, "benxi": 50,
        "丹东": 51, "dandong": 51,
        "锦州": 52, "jinzhou": 52,
        "营口": 53, "yingkou": 53,
        "阜新": 54, "fuxin": 54,
        "辽阳": 55, "liaoyang": 55,
        "盘锦": 56, "panjin": 56,
        "铁岭": 57, "tieling": 57,
        "朝阳": 58, "chaoyang": 58,
        "葫芦岛": 59, "huludao": 59,
        
        # Jilin Province
        "长春": 60, "changchun": 60,
        "吉林": 61, "jilin": 61,
        "四平": 62, "siping": 62,
        "辽源": 63, "liaoyuan": 63,
        "通化": 64, "tonghua": 64,
        "白山": 65, "baishan": 65,
        "松原": 66, "songyuan": 66,
        "白城": 67, "baicheng": 67,
        
        # Heilongjiang Province
        "哈尔滨": 68, "harbin": 68,
        "齐齐哈尔": 69, "qiqihar": 69,
        "鸡西": 70, "jixi": 70,
        "鹤岗": 71, "hegang": 71,
        "双鸭山": 72, "shuangyashan": 72,
        "大庆": 73, "daqing": 73,
        "伊春": 74, "yichun": 74,
        "佳木斯": 75, "jiamusi": 75,
        "七台河": 76, "qitaihe": 76,
        "牡丹江": 77, "mudanjiang": 77,
        "黑河": 78, "heihe": 78,
        "绥化": 79, "suihua": 79,
        
        # Jiangsu Province
        "无锡": 80, "wuxi": 80,
        "徐州": 81, "xuzhou": 81,
        "南通": 82, "nantong": 82,
        "连云港": 83, "lianyungang": 83,
        "扬州": 84, "yangzhou": 84,
        "盐城": 85, "yancheng": 85,
        "淮安": 86, "huaian": 86,
        "常州": 87, "changzhou": 87,
        "镇江": 88, "zhenjiang": 88,
        "泰州": 89, "taizhou": 89,
        "宿迁": 90, "suqian": 90,
        
        # Zhejiang Province
        "宁波": 91, "ningbo": 91,
        "温州": 92, "wenzhou": 92,
        "嘉兴": 93, "jiaxing": 93,
        "湖州": 94, "huzhou": 94,
        "绍兴": 95, "shaoxing": 95,
        "金华": 96, "jinhua": 96,
        "衢州": 97, "quzhou": 97,
        "舟山": 98, "zhoushan": 98,
        "台州": 99, "taizhou_zj": 99,
        "丽水": 100, "lishui": 100,
        
        # Anhui Province
        "合肥": 101, "hefei": 101,
        "芜湖": 102, "wuhu": 102,
        "蚌埠": 103, "bengbu": 103,
        "淮南": 104, "huainan": 104,
        "马鞍山": 105, "maanshan": 105,
        "淮北": 106, "huaibei": 106,
        "铜陵": 107, "tongling": 107,
        "安庆": 108, "anqing": 108,
        "黄山": 109, "huangshan": 109,
        "滁州": 110, "chuzhou": 110,
        "阜阳": 111, "fuyang": 111,
        "宿州": 112, "suzhou_ah": 112,
        "六安": 113, "luan": 113,
        "亳州": 114, "bozhou": 114,
        "池州": 115, "chizhou": 115,
        "宣城": 116, "xuancheng": 116,
        
        # Fujian Province
        "福州": 117, "fuzhou": 117,
        "莆田": 118, "putian": 118,
        "三明": 119, "sanming": 119,
        "泉州": 120, "quanzhou": 120,
        "漳州": 121, "zhangzhou": 121,
        "南平": 122, "nanping": 122,
        "龙岩": 123, "longyan": 123,
        "宁德": 124, "ningde": 124,
        
        # Jiangxi Province
        "南昌": 125, "nanchang": 125,
        "景德镇": 126, "jingdezhen": 126,
        "萍乡": 127, "pingxiang": 127,
        "九江": 128, "jiujiang": 128,
        "新余": 129, "xinyu": 129,
        "鹰潭": 130, "yingtan": 130,
        "赣州": 131, "ganzhou": 131,
        "吉安": 132, "jian": 132,
        "宜春": 133, "yichun_jx": 133,
        "抚州": 134, "fuzhou_jx": 134,
        "上饶": 135, "shangrao": 135,
        
        # Shandong province
        "济南": 136, "jinan": 136,
        "淄博": 137, "zibo": 137,
        "枣庄": 138, "zaozhuang": 138,
        "东营": 139, "dongying": 139,
        "烟台": 140, "yantai": 140,
        "潍坊": 141, "weifang": 141,
        "济宁": 142, "jining": 142,
        "泰安": 143, "taian": 143,
        "威海": 144, "weihai": 144,
        "日照": 145, "rizhao": 145,
        "莱芜": 146, "laiwu": 146,
        "临沂": 147, "linyi": 147,
        "德州": 148, "dezhou": 148,
        "聊城": 149, "liaocheng": 149,
        "滨州": 150, "binzhou": 150,
        "菏泽": 151, "heze": 151,
        
        # Henan Province
        "郑州": 152, "zhengzhou": 152,
        "开封": 153, "kaifeng": 153,
        "洛阳": 154, "luoyang": 154,
        "平顶山": 155, "pingdingshan": 155,
        "安阳": 156, "anyang": 156,
        "鹤壁": 157, "hebi": 157,
        "新乡": 158, "xinxiang": 158,
        "焦作": 159, "jiaozuo": 159,
        "濮阳": 160, "puyang": 160,
        "许昌": 161, "xuchang": 161,
        "漯河": 162, "luohe": 162,
        "三门峡": 163, "sanmenxia": 163,
        "南阳": 164, "nanyang": 164,
        "商丘": 165, "shangqiu": 165,
        "信阳": 166, "xinyang": 166,
        "周口": 167, "zhoukou": 167,
        "驻马店": 168, "zhumadian": 168,
        
        # Hubei Province
        "黄石": 169, "huangshi": 169,
        "十堰": 170, "shiyan": 170,
        "宜昌": 171, "yichang": 171,
        "襄阳": 172, "xiangyang": 172,
        "鄂州": 173, "ezhou": 173,
        "荆门": 174, "jingmen": 174,
        "孝感": 175, "xiaogan": 175,
        "荆州": 176, "jingzhou": 176,
        "黄冈": 177, "huanggang": 177,
        "咸宁": 178, "xianning": 178,
        "随州": 179, "suizhou": 179,
        "恩施": 180, "enshi": 180,
        
        # Hunan Province
        "长沙": 14, "changsha": 14,
        "株洲": 181, "zhuzhou": 181,
        "湘潭": 182, "xiangtan": 182,
        "衡阳": 183, "hengyang": 183,
        "邵阳": 184, "shaoyang": 184,
        "岳阳": 185, "yueyang": 185,
        "常德": 186, "changde": 186,
        "张家界": 187, "zhangjiajie": 187,
        "益阳": 188, "yiyang": 188,
        "郴州": 189, "chenzhou": 189,
        "永州": 190, "yongzhou": 190,
        "怀化": 191, "huaihua": 191,
        "娄底": 192, "loudi": 192,
        
        # Guangdong Province
        "广州": 3, "guangzhou": 3,
        "深圳": 4, "shenzhen": 4,
        "韶关": 193, "shaoguan": 193,
        "珠海": 194, "zhuhai": 194,
        "汕头": 195, "shantou": 195,
        "佛山": 196, "foshan": 196,
        "江门": 197, "jiangmen": 197,
        "湛江": 198, "zhanjiang": 198,
        "茂名": 199, "maoming": 199,
        "肇庆": 200, "zhaoqing": 200,
        "惠州": 201, "huizhou": 201,
        "梅州": 202, "meizhou": 202,
        "汕尾": 203, "shanwei": 203,
        "河源": 204, "heyuan": 204,
        "阳江": 205, "yangjiang": 205,
        "清远": 206, "qingyuan": 206,
        "东莞": 207, "dongguan": 207,
        "中山": 208, "zhongshan": 208,
        "潮州": 209, "chaozhou": 209,
        "揭阳": 210, "jieyang": 210,
        "云浮": 211, "yunfu": 211,
        
        # Guangxi Zhuang Autonomous Region
        "南宁": 212, "nanning": 212,
        "柳州": 213, "liuzhou": 213,
        "桂林": 214, "guilin": 214,
        "梧州": 215, "wuzhou": 215,
        "北海": 216, "beihai": 216,
        "防城港": 217, "fangchenggang": 217,
        "钦州": 218, "qinzhou": 218,
        "贵港": 219, "guigang": 219,
        "玉林": 220, "yulin": 220,
        "百色": 221, "baise": 221,
        "贺州": 222, "hezhou": 222,
        "河池": 223, "hechi": 223,
        "来宾": 224, "laibin": 224,
        "崇左": 225, "chongzuo": 225,
        
        # Hainan Province
        "海口": 226, "haikou": 226,
        "三亚": 227, "sanya": 227,
        "三沙": 228, "sansha": 228,
        "儋州": 229, "danzhou": 229,
        
        # Sichuan Province
        "成都": 5, "chengdu": 5,
        "自贡": 230, "zigong": 230,
        "攀枝花": 231, "panzhihua": 231,
        "泸州": 232, "luzhou": 232,
        "德阳": 233, "deyang": 233,
        "绵阳": 234, "mianyang": 234,
        "广元": 235, "guangyuan": 235,
        "遂宁": 236, "suining": 236,
        "内江": 237, "neijiang": 237,
        "乐山": 238, "leshan": 238,
        "南充": 239, "nanchong": 239,
        "眉山": 240, "meishan": 240,
        "宜宾": 241, "yibin": 241,
        "广安": 242, "guangan": 242,
        "达州": 243, "dazhou": 243,
        "雅安": 244, "yaan": 244,
        "巴中": 245, "bazhong": 245,
        "资阳": 246, "ziyang": 246,
        
        # Guizhou Province
        "贵阳": 247, "guiyang": 247,
        "六盘水": 248, "liupanshui": 248,
        "遵义": 249, "zunyi": 249,
        "安顺": 250, "anshun": 250,
        "毕节": 251, "bijie": 251,
        "铜仁": 252, "tongren": 252,
        
        # Yunnan Province
        "昆明": 253, "kunming": 253,
        "曲靖": 254, "qujing": 254,
        "玉溪": 255, "yuxi": 255,
        "保山": 256, "baoshan": 256,
        "昭通": 257, "zhaotong": 257,
        "丽江": 258, "lijiang": 258,
        "普洱": 259, "puer": 259,
        "临沧": 260, "lincang": 260,
        
        # Tibet (Xizang) Autonomous Region
        "拉萨": 261, "lhasa": 261,
        "日喀则": 262, "rikaze": 262,
        "昌都": 263, "changdu": 263,
        "林芝": 264, "linzhi": 264,
        "山南": 265, "shannan": 265,
        "那曲": 266, "naqu": 266,
        
        # Shaanxi Province
        "西安": 8, "xian": 8,
        "铜川": 267, "tongchuan": 267,
        "宝鸡": 268, "baoji": 268,
        "咸阳": 269, "xianyang": 269,
        "渭南": 270, "weinan": 270,
        "延安": 271, "yanan": 271,
        "汉中": 272, "hanzhong": 272,
        "榆林": 273, "yulin_sx": 273,
        "安康": 274, "ankang": 274,
        "商洛": 275, "shangluo": 275,
        
        # Gansu Province
        "兰州": 276, "lanzhou": 276,
        "嘉峪关": 277, "jiayuguan": 277,
        "金昌": 278, "jinchang": 278,
        "白银": 279, "baiyin": 279,
        "天水": 280, "tianshui": 280,
        "武威": 281, "wuwei": 281,
        "张掖": 282, "zhangye": 282,
        "平凉": 283, "pingliang": 283,
        "酒泉": 284, "jiuquan": 284,
        "庆阳": 285, "qingyang": 285,
        "定西": 286, "dingxi": 286,
        "陇南": 287, "longnan": 287,
        
        # Qinghai Province
        "西宁": 288, "xining": 288,
        "海东": 289, "haidong": 289,
        
        # Ningxia Hui Autonomous Region
        "银川": 290, "yinchuan": 290,
        "石嘴山": 291, "shizuishan": 291,
        "吴忠": 292, "wuzhong": 292,
        "固原": 293, "guyuan": 293,
        "中卫": 294, "zhongwei": 294,
        
        # Xinjiang Uighur Autonomous Region
        "乌鲁木齐": 295, "urumqi": 295,
        "克拉玛依": 296, "kelamayi": 296,
        "吐鲁番": 297, "tulufan": 297,
        "哈密": 298, "hami": 298,
        
        # Hong Kong SAR
        "香港": 299, "hongkong": 299, "HongKong": 299,
        
        # Macau SAR
        "澳门": 300, "macau": 300, "Macau": 300,
        
        # Taiwan (for reference)
        "台北": 301, "taipei": 301, "Taipei": 301,
    }
    
    @classmethod
    def get_city_code(cls, city_name: str) -> int:
        return cls.CITY_MAPPING.get(city_name, 999)

class FinshDataSender:
    def __init__(self, 
                 serial_assistant=None, 
                 weather_api=None, 
                 stock_api=None, 
                 hardware_monitor=None):
        self.serial_assistant = serial_assistant
        self.weather_api = weather_api
        self.stock_api = stock_api
        self.hardware_monitor = hardware_monitor
        
        self.enabled = False
        self.send_time_data = True
        self.send_api_data = True
        self.send_performance_data = True
        
        self.intervals = {
            DataCategory.TIME: 1.0,
            DataCategory.API: 300.0,
            DataCategory.PERFORMANCE: 1.0
        }
        
        self.min_command_interval = 10
        
        self.stop_event = threading.Event()
        self.sender_threads = {}
        
        self.data_providers = {
            DataCategory.TIME: self._get_time_data,
            DataCategory.API: self._get_api_data,
            DataCategory.PERFORMANCE: self._get_performance_data
        }
        
        self.stats = {
            'commands_sent': 0,
            'errors': 0,
            'last_send_time': None
        }
        
    def start(self):
        if self.enabled:
            return True  # 已经启动，返回True
            
        if not self.serial_assistant or not self.serial_assistant.is_connected:
            return False  # 串口未连接，返回False
            
        self.enabled = True
        self.stop_event.clear()
        
        try:
            if self.send_time_data:
                self._start_sender_thread(DataCategory.TIME)
                
            if self.send_api_data:
                self._start_sender_thread(DataCategory.API)
                
            if self.send_performance_data:
                self._start_sender_thread(DataCategory.PERFORMANCE)
                
            return True  # 启动成功
        except Exception:
            self.enabled = False
            return False  # 启动失败
            
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
        except Exception:
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
                
            except Exception:
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
                except Exception:
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
                    icon_code = weather_data.get('icon_code', '999')
                    
                    try:
                        weather_code_int = int(icon_code)
                    except:
                        weather_code_int = 999
                    
                    # 实时天气数据
                    data.update({
                        'temp': int(round(weather_data.get('temperature', 0))),
                        'weather_code': weather_code_int,
                        'humidity': int(weather_data.get('humidity', 0)),
                        'pressure': int(weather_data.get('pressure', 0)),
                        'city_code': CityCodeMapper.get_city_code(weather_data.get('city_name', ''))
                    })
                    
                    # 天气预报数据 (今天、明天、后天三天)
                    forecast_list = weather_data.get('forecast', [])
                    if forecast_list and len(forecast_list) >= 3:
                        # 今天的预报
                        day0 = forecast_list[0]
                        data.update({
                            'forecast_day0_text': day0.get('text_day', ''),
                            'forecast_day0_temp_max': int(day0.get('temp_max', 0)),
                            'forecast_day0_temp_min': int(day0.get('temp_min', 0)),
                            'forecast_day0_wind_dir': day0.get('wind_dir_day', ''),
                            'forecast_day0_wind_scale': day0.get('wind_scale_day', '')
                        })
                        
                        # 明天的预报
                        day1 = forecast_list[1]
                        data.update({
                            'forecast_day1_text': day1.get('text_day', ''),
                            'forecast_day1_temp_max': int(day1.get('temp_max', 0)),
                            'forecast_day1_temp_min': int(day1.get('temp_min', 0)),
                            'forecast_day1_wind_dir': day1.get('wind_dir_day', ''),
                            'forecast_day1_wind_scale': day1.get('wind_scale_day', '')
                        })
                        
                        # 后天的预报
                        day2 = forecast_list[2]
                        data.update({
                            'forecast_day2_text': day2.get('text_day', ''),
                            'forecast_day2_temp_max': int(day2.get('temp_max', 0)),
                            'forecast_day2_temp_min': int(day2.get('temp_min', 0)),
                            'forecast_day2_wind_dir': day2.get('wind_dir_day', ''),
                            'forecast_day2_wind_scale': day2.get('wind_scale_day', '')
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
            'sys_set weather_code 100',
            'sys_set humidity 65',
            'sys_set pressure 1013',
            'sys_set city_code 0',
            'sys_set forecast_day0_text "晴"',
            'sys_set forecast_day0_temp_max 28',
            'sys_set forecast_day0_temp_min 18',
            'sys_set forecast_day0_wind_dir "东南风"',
            'sys_set forecast_day0_wind_scale "3-4"',
            'sys_set forecast_day1_text "多云"',
            'sys_set forecast_day1_temp_max 26',
            'sys_set forecast_day1_temp_min 17',
            'sys_set forecast_day1_wind_dir "东风"',
            'sys_set forecast_day1_wind_scale "2-3"',
            'sys_set forecast_day2_text "小雨"',
            'sys_set forecast_day2_temp_max 24',
            'sys_set forecast_day2_temp_min 16',
            'sys_set forecast_day2_wind_dir "东北风"',
            'sys_set forecast_day2_wind_scale "1-2"',
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