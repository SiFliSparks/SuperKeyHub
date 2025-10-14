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
        
        # Hunan Province
        "株洲": 180, "zhuzhou": 180,
        "湘潭": 181, "xiangtan": 181,
        "衡阳": 182, "hengyang": 182,
        "邵阳": 183, "shaoyang": 183,
        "岳阳": 184, "yueyang": 184,
        "常德": 185, "changde": 185,
        "张家界": 186, "zhangjiajie": 186,
        "益阳": 187, "yiyang": 187,
        "郴州": 188, "chenzhou": 188,
        "永州": 189, "yongzhou": 189,
        "怀化": 190, "huaihua": 190,
        "娄底": 191, "loudi": 191,
        
        # Guangdong Province
        "韶关": 192, "shaoguan": 192,
        "汕头": 193, "shantou": 193,
        "佛山": 194, "foshan": 194,
        "江门": 195, "jiangmen": 195,
        "湛江": 196, "zhanjiang": 196,
        "茂名": 197, "maoming": 197,
        "肇庆": 198, "zhaoqing": 198,
        "惠州": 199, "huizhou": 199,
        "梅州": 200, "meizhou": 200,
        "汕尾": 201, "shanwei": 201,
        "河源": 202, "heyuan": 202,
        "阳江": 203, "yangjiang": 203,
        "清远": 204, "qingyuan": 204,
        "东莞": 205, "dongguan": 205,
        "中山": 206, "zhongshan": 206,
        "潮州": 207, "chaozhou": 207,
        "揭阳": 208, "jieyang": 208,
        "云浮": 209, "yunfu": 209,
        
        # the Guangxi Zhuang Autonomous Region
        "南宁": 210, "nanning": 210,
        "柳州": 211, "liuzhou": 211,
        "桂林": 212, "guilin": 212,
        "梧州": 213, "wuzhou": 213,
        "北海": 214, "beihai": 214,
        "防城港": 215, "fangchenggang": 215,
        "钦州": 216, "qinzhou": 216,
        "贵港": 217, "guigang": 217,
        "玉林": 218, "yulin_gx": 218,
        "百色": 219, "baise": 219,
        "贺州": 220, "hezhou": 220,
        "河池": 221, "hechi": 221,
        "来宾": 222, "laibin": 222,
        "崇左": 223, "chongzuo": 223,
        
        # Hainan Province
        "海口": 224, "haikou": 224,
        "三亚": 225, "sanya": 225,
        "三沙": 226, "sansha": 226,
        "儋州": 227, "danzhou": 227,
        
        # Sichuan Province
        "自贡": 228, "zigong": 228,
        "攀枝花": 229, "panzhihua": 229,
        "泸州": 230, "luzhou": 230,
        "德阳": 231, "deyang": 231,
        "绵阳": 232, "mianyang": 232,
        "广元": 233, "guangyuan": 233,
        "遂宁": 234, "suining": 234,
        "内江": 235, "neijiang": 235,
        "乐山": 236, "leshan": 236,
        "南充": 237, "nanchong": 237,
        "眉山": 238, "meishan": 238,
        "宜宾": 239, "yibin": 239,
        "广安": 240, "guangan": 240,
        "达州": 241, "dazhou": 241,
        "雅安": 242, "yaan": 242,
        "巴中": 243, "bazhong": 243,
        "资阳": 244, "ziyang": 244,
        
        # Guizhou Province
        "贵阳": 245, "guiyang": 245,
        "六盘水": 246, "liupanshui": 246,
        "遵义": 247, "zunyi": 247,
        "安顺": 248, "anshun": 248,
        "毕节": 249, "bijie": 249,
        "铜仁": 250, "tongren": 250,
        
        # Yunnan Province
        "昆明": 251, "kunming": 251,
        "曲靖": 252, "qujing": 252,
        "玉溪": 253, "yuxi": 253,
        "保山": 254, "baoshan": 254,
        "昭通": 255, "zhaotong": 255,
        "丽江": 256, "lijiang": 256,
        "普洱": 257, "puer": 257,
        "临沧": 258, "lincang": 258,
        
        # Xizang Autonomous Region
        "拉萨": 259, "lhasa": 259,
        "昌都": 260, "changdu": 260,
        "山南": 261, "shannan": 261,
        "日喀则": 262, "rikaze": 262,
        "那曲": 263, "naqu": 263,
        "阿里": 264, "ali": 264,
        "林芝": 265, "linzhi": 265,
        
        # Shaanxi Province
        "铜川": 266, "tongchuan": 266,
        "宝鸡": 267, "baoji": 267,
        "咸阳": 268, "xianyang": 268,
        "渭南": 269, "weinan": 269,
        "延安": 270, "yanan": 270,
        "汉中": 271, "hanzhong": 271,
        "榆林": 272, "yulin_sx": 272,
        "安康": 273, "ankang": 273,
        "商洛": 274, "shangluo": 274,
        
        # Gansu Province
        "兰州": 275, "lanzhou": 275,
        "嘉峪关": 276, "jiayuguan": 276,
        "金昌": 277, "jinchang": 277,
        "白银": 278, "baiyin": 278,
        "天水": 279, "tianshui": 279,
        "武威": 280, "wuwei": 280,
        "张掖": 281, "zhangye": 281,
        "平凉": 282, "pingliang": 282,
        "酒泉": 283, "jiuquan": 283,
        "庆阳": 284, "qingyang": 284,
        "定西": 285, "dingxi": 285,
        "陇南": 286, "longnan": 286,
        
        # Qinghai Province
        "西宁": 287, "xining": 287,
        "海东": 288, "haidong": 288,
        
        # the Ningxia Hui Autonomous Region
        "银川": 289, "yinchuan": 289,
        "石嘴山": 290, "shizuishan": 290,
        "吴忠": 291, "wuzhong": 291,
        "固原": 292, "guyuan": 292,
        "中卫": 293, "zhongwei": 293,
        
        # the Xinjiang Uygur [Uighur] Autonomous Region
        "乌鲁木齐": 294, "urumqi": 294,
        "克拉玛依": 295, "kelamayi": 295,
        "吐鲁番": 296, "turpan": 296,
        "哈密": 297, "hami": 297,
        "昌吉": 298, "changji": 298,
        "博尔塔拉": 299, "boertala": 299,
        "巴音郭楞": 300, "bayinguoleng": 300,
        "阿克苏": 301, "akesu": 301,
        "克孜勒苏": 302, "kezilesu": 302,
        "喀什": 303, "kashi": 303,
        "和田": 304, "hetian": 304,
        "伊犁": 305, "yili": 305,
        "塔城": 306, "tacheng": 306,
        "阿勒泰": 307, "aletai": 307,
        
        # special administrative region
        "香港": 308, "hongkong": 308,
        "澳门": 309, "macao": 309,
        
        # Taiwan Province (310-313) 
        "台北": 310, "taipei": 310,
        "高雄": 311, "kaohsiung": 311,
        "台中": 312, "taichung": 312,
        "台南": 313, "tainan": 313,
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
                    
                    data.update({
                        'temp': int(round(weather_data.get('temperature', 0))),
                        'weather_code': weather_code_int,
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
            'sys_set weather_code 100',
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