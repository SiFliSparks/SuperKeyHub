#!/usr/bin/env python3
"""
Finsh数据发送模块
"""

import threading
import time
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any


class DataCategory(Enum):
    TIME = "time"
    API = "api"
    PERFORMANCE = "performance"


class CityCodeMapper:
    CITY_MAPPING: dict[str, int] = {
        # Popular cities
        "未知": 999,
        "Error": 999,
        "杭州": 0,
        "hangzhou": 0,
        "上海": 1,
        "shanghai": 1,
        "北京": 2,
        "beijing": 2,
        "广州": 3,
        "guangzhou": 3,
        "深圳": 4,
        "shenzhen": 4,
        "成都": 5,
        "chengdu": 5,
        "重庆": 6,
        "chongqing": 6,
        "武汉": 7,
        "wuhan": 7,
        "西安": 8,
        "xian": 8,
        "南京": 9,
        "nanjing": 9,
        "天津": 10,
        "tianjin": 10,
        "苏州": 11,
        "suzhou": 11,
        "青岛": 12,
        "qingdao": 12,
        "厦门": 13,
        "xiamen": 13,
        "长沙": 14,
        "changsha": 14,
        # Hebei Province
        "石家庄": 15,
        "shijiazhuang": 15,
        "唐山": 16,
        "tangshan": 16,
        "秦皇岛": 17,
        "qinhuangdao": 17,
        "邯郸": 18,
        "handan": 18,
        "邢台": 19,
        "xingtai": 19,
        "保定": 20,
        "baoding": 20,
        "张家口": 21,
        "zhangjiakou": 21,
        "承德": 22,
        "chengde": 22,
        "沧州": 23,
        "cangzhou": 23,
        "廊坊": 24,
        "langfang": 24,
        "衡水": 25,
        "hengshui": 25,
        # Shanxi Province
        "太原": 26,
        "taiyuan": 26,
        "大同": 27,
        "datong": 27,
        "阳泉": 28,
        "yangquan": 28,
        "长治": 29,
        "changzhi": 29,
        "晋城": 30,
        "jincheng": 30,
        "朔州": 31,
        "shuozhou": 31,
        "晋中": 32,
        "jinzhong": 32,
        "运城": 33,
        "yuncheng": 33,
        "忻州": 34,
        "xinzhou": 34,
        "临汾": 35,
        "linfen": 35,
        "吕梁": 36,
        "lvliang": 36,
        # the Nei Monggol [Inner Mongolia] Autonomous Region
        "呼和浩特": 37,
        "hohhot": 37,
        "包头": 38,
        "baotou": 38,
        "乌海": 39,
        "wuhai": 39,
        "赤峰": 40,
        "chifeng": 40,
        "通辽": 41,
        "tongliao": 41,
        "鄂尔多斯": 42,
        "ordos": 42,
        "呼伦贝尔": 43,
        "hulunbuir": 43,
        "巴彦淖尔": 44,
        "bayannur": 44,
        "乌兰察布": 45,
        "ulanqab": 45,
        # Liaoning Province
        "沈阳": 46,
        "shenyang": 46,
        "大连": 47,
        "dalian": 47,
        "鞍山": 48,
        "anshan": 48,
        "抚顺": 49,
        "fushun": 49,
        "本溪": 50,
        "benxi": 50,
        "丹东": 51,
        "dandong": 51,
        "锦州": 52,
        "jinzhou": 52,
        "营口": 53,
        "yingkou": 53,
        "阜新": 54,
        "fuxin": 54,
        "辽阳": 55,
        "liaoyang": 55,
        "盘锦": 56,
        "panjin": 56,
        "铁岭": 57,
        "tieling": 57,
        "朝阳": 58,
        "chaoyang": 58,
        "葫芦岛": 59,
        "huludao": 59,
        # Jilin Province
        "长春": 60,
        "changchun": 60,
        "吉林": 61,
        "jilin": 61,
        "四平": 62,
        "siping": 62,
        "辽源": 63,
        "liaoyuan": 63,
        "通化": 64,
        "tonghua": 64,
        "白山": 65,
        "baishan": 65,
        "松原": 66,
        "songyuan": 66,
        "白城": 67,
        "baicheng": 67,
        # Heilongjiang Province
        "哈尔滨": 68,
        "harbin": 68,
        "齐齐哈尔": 69,
        "qiqihar": 69,
        "鸡西": 70,
        "jixi": 70,
        "鹤岗": 71,
        "hegang": 71,
        "双鸭山": 72,
        "shuangyashan": 72,
        "大庆": 73,
        "daqing": 73,
        "伊春": 74,
        "yichun": 74,
        "佳木斯": 75,
        "jiamusi": 75,
        "七台河": 76,
        "qitaihe": 76,
        "牡丹江": 77,
        "mudanjiang": 77,
        "黑河": 78,
        "heihe": 78,
        "绥化": 79,
        "suihua": 79,
        # Jiangsu Province
        "无锡": 80,
        "wuxi": 80,
        "徐州": 81,
        "xuzhou": 81,
        "南通": 82,
        "nantong": 82,
        "连云港": 83,
        "lianyungang": 83,
        "扬州": 84,
        "yangzhou": 84,
        "盐城": 85,
        "yancheng": 85,
        "淮安": 86,
        "huaian": 86,
        "常州": 87,
        "changzhou": 87,
        "镇江": 88,
        "zhenjiang": 88,
        "泰州": 89,
        "taizhou": 89,
        "宿迁": 90,
        "suqian": 90,
        # Zhejiang Province
        "宁波": 91,
        "ningbo": 91,
        "温州": 92,
        "wenzhou": 92,
        "嘉兴": 93,
        "jiaxing": 93,
        "湖州": 94,
        "huzhou": 94,
        "绍兴": 95,
        "shaoxing": 95,
        "金华": 96,
        "jinhua": 96,
        "衢州": 97,
        "quzhou": 97,
        "舟山": 98,
        "zhoushan": 98,
        "台州": 99,
        "taizhou_zj": 99,
        "丽水": 100,
        "lishui": 100,
        # Anhui Province
        "合肥": 101,
        "hefei": 101,
        "芜湖": 102,
        "wuhu": 102,
        "蚌埠": 103,
        "bengbu": 103,
        "淮南": 104,
        "huainan": 104,
        "马鞍山": 105,
        "maanshan": 105,
        "淮北": 106,
        "huaibei": 106,
        "铜陵": 107,
        "tongling": 107,
        "安庆": 108,
        "anqing": 108,
        "黄山": 109,
        "huangshan": 109,
        "滁州": 110,
        "chuzhou": 110,
        "阜阳": 111,
        "fuyang": 111,
        "宿州": 112,
        "suzhou_ah": 112,
        "六安": 113,
        "luan": 113,
        "亳州": 114,
        "bozhou": 114,
        "池州": 115,
        "chizhou": 115,
        "宣城": 116,
        "xuancheng": 116,
        # Fujian Province
        "福州": 117,
        "fuzhou": 117,
        "莆田": 118,
        "putian": 118,
        "三明": 119,
        "sanming": 119,
        "泉州": 120,
        "quanzhou": 120,
        "漳州": 121,
        "zhangzhou": 121,
        "南平": 122,
        "nanping": 122,
        "龙岩": 123,
        "longyan": 123,
        "宁德": 124,
        "ningde": 124,
        # Jiangxi Province
        "南昌": 125,
        "nanchang": 125,
        "景德镇": 126,
        "jingdezhen": 126,
        "萍乡": 127,
        "pingxiang": 127,
        "九江": 128,
        "jiujiang": 128,
        "新余": 129,
        "xinyu": 129,
        "鹰潭": 130,
        "yingtan": 130,
        "赣州": 131,
        "ganzhou": 131,
        "吉安": 132,
        "jian": 132,
        "宜春": 133,
        "yichun_jx": 133,
        "抚州": 134,
        "fuzhou_jx": 134,
        "上饶": 135,
        "shangrao": 135,
        # Shandong province
        "济南": 136,
        "jinan": 136,
        "淄博": 137,
        "zibo": 137,
        "枣庄": 138,
        "zaozhuang": 138,
        "东营": 139,
        "dongying": 139,
        "烟台": 140,
        "yantai": 140,
        "潍坊": 141,
        "weifang": 141,
        "济宁": 142,
        "jining": 142,
        "泰安": 143,
        "taian": 143,
        "威海": 144,
        "weihai": 144,
        "日照": 145,
        "rizhao": 145,
        "莱芜": 146,
        "laiwu": 146,
        "临沂": 147,
        "linyi": 147,
        "德州": 148,
        "dezhou": 148,
        "聊城": 149,
        "liaocheng": 149,
        "滨州": 150,
        "binzhou": 150,
        "菏泽": 151,
        "heze": 151,
        # Henan Province
        "郑州": 152,
        "zhengzhou": 152,
        "开封": 153,
        "kaifeng": 153,
        "洛阳": 154,
        "luoyang": 154,
        "平顶山": 155,
        "pingdingshan": 155,
        "安阳": 156,
        "anyang": 156,
        "鹤壁": 157,
        "hebi": 157,
        "新乡": 158,
        "xinxiang": 158,
        "焦作": 159,
        "jiaozuo": 159,
        "濮阳": 160,
        "puyang": 160,
        "许昌": 161,
        "xuchang": 161,
        "漯河": 162,
        "luohe": 162,
        "三门峡": 163,
        "sanmenxia": 163,
        "南阳": 164,
        "nanyang": 164,
        "商丘": 165,
        "shangqiu": 165,
        "信阳": 166,
        "xinyang": 166,
        "周口": 167,
        "zhoukou": 167,
        "驻马店": 168,
        "zhumadian": 168,
        "济源": 169,
        "jiyuan": 169,
        # Hubei Province
        "荆州": 170,
        "jingzhou": 170,
        "宜昌": 171,
        "yichang": 171,
        "襄阳": 172,
        "xiangyang": 172,
        "十堰": 173,
        "shiyan": 173,
        "荆门": 174,
        "jingmen": 174,
        "鄂州": 175,
        "ezhou": 175,
        "孝感": 176,
        "xiaogan": 176,
        "黄冈": 177,
        "huanggang": 177,
        "咸宁": 178,
        "xianning": 178,
        "随州": 179,
        "suizhou": 179,
        "恩施": 180,
        "enshi": 180,
        "黄石": 181,
        "huangshi": 181,
        # Hunan Province
        "株洲": 182,
        "zhuzhou": 182,
        "湘潭": 183,
        "xiangtan": 183,
        "衡阳": 184,
        "hengyang": 184,
        "邵阳": 185,
        "shaoyang": 185,
        "岳阳": 186,
        "yueyang": 186,
        "常德": 187,
        "changde": 187,
        "张家界": 188,
        "zhangjiajie": 188,
        "益阳": 189,
        "yiyang": 189,
        "郴州": 190,
        "chenzhou": 190,
        "永州": 191,
        "yongzhou": 191,
        "怀化": 192,
        "huaihua": 192,
        "娄底": 193,
        "loudi": 193,
        "湘西": 194,
        "xiangxi": 194,
        # Guangdong Province
        "珠海": 195,
        "zhuhai": 195,
        "汕头": 196,
        "shantou": 196,
        "佛山": 197,
        "foshan": 197,
        "韶关": 198,
        "shaoguan": 198,
        "湛江": 199,
        "zhanjiang": 199,
        "肇庆": 200,
        "zhaoqing": 200,
        "江门": 201,
        "jiangmen": 201,
        "茂名": 202,
        "maoming": 202,
        "惠州": 203,
        "huizhou": 203,
        "梅州": 204,
        "meizhou": 204,
        "汕尾": 205,
        "shanwei": 205,
        "河源": 206,
        "heyuan": 206,
        "阳江": 207,
        "yangjiang": 207,
        "清远": 208,
        "qingyuan": 208,
        "东莞": 209,
        "dongguan": 209,
        "中山": 210,
        "zhongshan": 210,
        "潮州": 211,
        "chaozhou": 211,
        "揭阳": 212,
        "jieyang": 212,
        "云浮": 213,
        "yunfu": 213,
        # Guangxi Zhuang Autonomous Region
        "南宁": 214,
        "nanning": 214,
        "柳州": 215,
        "liuzhou": 215,
        "桂林": 216,
        "guilin": 216,
        "梧州": 217,
        "wuzhou": 217,
        "北海": 218,
        "beihai": 218,
        "防城港": 219,
        "fangchenggang": 219,
        "钦州": 220,
        "qinzhou": 220,
        "贵港": 221,
        "guigang": 221,
        "玉林": 222,
        "yulin": 222,
        "百色": 223,
        "baise": 223,
        "贺州": 224,
        "hezhou": 224,
        "河池": 225,
        "hechi": 225,
        "来宾": 226,
        "laibin": 226,
        "崇左": 227,
        "chongzuo": 227,
        # Hainan Province
        "海口": 228,
        "haikou": 228,
        "三亚": 229,
        "sanya": 229,
        "三沙": 230,
        "sansha": 230,
        "儋州": 231,
        "danzhou": 231,
        # Sichuan Province
        "绵阳": 232,
        "mianyang": 232,
        "自贡": 233,
        "zigong": 233,
        "攀枝花": 234,
        "panzhihua": 234,
        "泸州": 235,
        "luzhou": 235,
        "德阳": 236,
        "deyang": 236,
        "广元": 237,
        "guangyuan": 237,
        "遂宁": 238,
        "suining": 238,
        "内江": 239,
        "neijiang": 239,
        "乐山": 240,
        "leshan": 240,
        "南充": 241,
        "nanchong": 241,
        "眉山": 242,
        "meishan": 242,
        "宜宾": 243,
        "yibin": 243,
        "广安": 244,
        "guangan": 244,
        "达州": 245,
        "dazhou": 245,
        "雅安": 246,
        "yaan": 246,
        "巴中": 247,
        "bazhong": 247,
        "资阳": 248,
        "ziyang": 248,
        "阿坝": 249,
        "aba": 249,
        "甘孜": 250,
        "ganzi": 250,
        "凉山": 251,
        "liangshan": 251,
        # Guizhou Province
        "贵阳": 252,
        "guiyang": 252,
        "六盘水": 253,
        "liupanshui": 253,
        "遵义": 254,
        "zunyi": 254,
        "安顺": 255,
        "anshun": 255,
        "毕节": 256,
        "bijie": 256,
        "铜仁": 257,
        "tongren": 257,
        "黔西南": 258,
        "qianxinan": 258,
        "黔东南": 259,
        "qiandongnan": 259,
        "黔南": 260,
        "qiannan": 260,
        # Yunnan Province
        "昆明": 261,
        "kunming": 261,
        "曲靖": 262,
        "qujing": 262,
        "玉溪": 263,
        "yuxi": 263,
        "保山": 264,
        "baoshan": 264,
        "昭通": 265,
        "zhaotong": 265,
        "丽江": 266,
        "lijiang": 266,
        "普洱": 267,
        "puer": 267,
        "临沧": 268,
        "lincang": 268,
        "楚雄": 269,
        "chuxiong": 269,
        "红河": 270,
        "honghe": 270,
        "文山": 271,
        "wenshan": 271,
        "西双版纳": 272,
        "xishuangbanna": 272,
        "大理": 273,
        "dali": 273,
        "德宏": 274,
        "dehong": 274,
        "怒江": 275,
        "nujiang": 275,
        "迪庆": 276,
        "diqing": 276,
        # Tibet Autonomous Region
        "拉萨": 277,
        "lasa": 277,
        "日喀则": 278,
        "rikaze": 278,
        "昌都": 279,
        "changdu": 279,
        "林芝": 280,
        "linzhi": 280,
        "山南": 281,
        "shannan": 281,
        "那曲": 282,
        "naqu": 282,
        "阿里": 283,
        "ali": 283,
        # Shaanxi Province
        "咸阳": 284,
        "xianyang": 284,
        "铜川": 285,
        "tongchuan": 285,
        "宝鸡": 286,
        "baoji": 286,
        "延安": 287,
        "yanan": 287,
        "汉中": 288,
        "hanzhong": 288,
        "榆林": 289,
        "yulin_sx": 289,
        "安康": 290,
        "ankang": 290,
        "商洛": 291,
        "shangluo": 291,
        # Gansu Province
        "兰州": 292,
        "lanzhou": 292,
        "嘉峪关": 293,
        "jiayuguan": 293,
        "金昌": 294,
        "jinchang": 294,
        "白银": 295,
        "baiyin": 295,
        "天水": 296,
        "tianshui": 296,
        "武威": 297,
        "wuwei": 297,
        "张掖": 298,
        "zhangye": 298,
        "平凉": 299,
        "pingliang": 299,
        "酒泉": 300,
        "jiuquan": 300,
        "庆阳": 301,
        "qingyang": 301,
        "定西": 302,
        "dingxi": 302,
        "陇南": 303,
        "longnan": 303,
        "临夏": 304,
        "linxia": 304,
        "甘南": 305,
        "gannan": 305,
        # Qinghai Province
        "西宁": 306,
        "xining": 306,
        "海东": 307,
        "haidong": 307,
        "海北": 308,
        "haibei": 308,
        "黄南": 309,
        "huangnan": 309,
        "海南": 310,
        "hainan_qh": 310,
        "果洛": 311,
        "guoluo": 311,
        "玉树": 312,
        "yushu": 312,
        "海西": 313,
        "haixi": 313,
        # Ningxia Hui Autonomous Region
        "银川": 314,
        "yinchuan": 314,
        "石嘴山": 315,
        "shizuishan": 315,
        "吴忠": 316,
        "wuzhong": 316,
        "固原": 317,
        "guyuan": 317,
        "中卫": 318,
        "zhongwei": 318,
        # Xinjiang Uygur Autonomous Region
        "乌鲁木齐": 319,
        "urumqi": 319,
        "克拉玛依": 320,
        "karamay": 320,
        "吐鲁番": 321,
        "turpan": 321,
        "哈密": 322,
        "hami": 322,
        "昌吉": 323,
        "changji": 323,
        "博尔塔拉": 324,
        "bortala": 324,
        "巴音郭楞": 325,
        "bayingolin": 325,
        "阿克苏": 326,
        "aksu": 326,
        "克孜勒苏": 327,
        "kizilsu": 327,
        "喀什": 328,
        "kashgar": 328,
        "和田": 329,
        "hotan": 329,
        "伊犁": 330,
        "ili": 330,
        "塔城": 331,
        "tacheng": 331,
        "阿勒泰": 332,
        "altay": 332,
        # Special Administrative Regions
        "香港": 333,
        "hongkong": 333,
        "澳门": 334,
        "macau": 334,
        "台北": 335,
        "taipei": 335,
        "高雄": 336,
        "kaohsiung": 336,
        "台中": 337,
        "taichung": 337,
        "台南": 338,
        "tainan": 338,
        "新竹": 339,
        "hsinchu": 339,
        "嘉义": 340,
        "chiayi": 340,
    }

    @classmethod
    def get_city_code(cls, city_name: str) -> int:
        """根据城市名称获取城市代码

        Args:
            city_name: 城市名称（中文或英文）

        Returns:
            城市代码，未找到时返回999
        """
        if not city_name:
            return 999

        city_name_clean = city_name.strip()

        if city_name_clean in cls.CITY_MAPPING:
            return cls.CITY_MAPPING[city_name_clean]

        city_name_lower = city_name_clean.lower()
        if city_name_lower in cls.CITY_MAPPING:
            return cls.CITY_MAPPING[city_name_lower]

        for key in cls.CITY_MAPPING:
            if city_name_clean in key or key in city_name_clean:
                return cls.CITY_MAPPING[key]

        return 999


class FinshDataSender:
    """Finsh协议数据发送器 - 支持延迟发送"""

    def __init__(
        self,
        serial_assistant: Any,
        hardware_monitor: Any | None = None,
        weather_api: Any | None = None,
    ) -> None:
        """初始化数据发送器

        Args:
            serial_assistant: 串口助手实例
            hardware_monitor: 硬件监控器实例（可选）
            weather_api: 天气API实例（可选）
        """
        self.serial_assistant: Any = serial_assistant
        self.hardware_monitor: Any | None = hardware_monitor
        self.weather_api: Any | None = weather_api

        # GPU选择索引，默认为0（核显），可通过set_gpu_index更新
        self.gpu_index: int = 0

        self.enabled: bool = False
        self.send_time_data: bool = True
        self.send_api_data: bool = True
        self.send_performance_data: bool = True

        self.intervals: dict[DataCategory, float] = {
            DataCategory.TIME: 1.0,
            DataCategory.API: 300.0,
            DataCategory.PERFORMANCE: 1.0,
        }

        self.initial_delays: dict[DataCategory, float] = {
            DataCategory.TIME: 0.0,
            DataCategory.API: 5.0,
            DataCategory.PERFORMANCE: 0.0,
        }

        self.min_command_interval: int = 10

        self.stop_event: threading.Event = threading.Event()
        self.sender_threads: dict[DataCategory, threading.Thread] = {}

        self.data_providers: dict[DataCategory, Callable[[], dict[str, Any]]] = {
            DataCategory.TIME: self._get_time_data,
            DataCategory.API: self._get_api_data,
            DataCategory.PERFORMANCE: self._get_performance_data,
        }

        self.stats: dict[str, Any] = {
            "commands_sent": 0,
            "errors": 0,
            "last_send_time": None,
        }

    def set_api_initial_delay(self, delay_seconds: float) -> None:
        """设置天气数据的初始发送延迟

        Args:
            delay_seconds: 延迟秒数
        """
        self.initial_delays[DataCategory.API] = max(0.0, delay_seconds)

    def set_gpu_index(self, index: int) -> None:
        """设置GPU选择索引

        Args:
            index: GPU索引（0为第一个GPU，通常是核显）
        """
        self.gpu_index = max(0, index)

    def set_initial_delay(self, category: DataCategory, delay_seconds: float) -> None:
        """设置指定类型数据的初始发送延迟

        Args:
            category: 数据类型
            delay_seconds: 延迟秒数
        """
        self.initial_delays[category] = max(0.0, delay_seconds)

    def start(self) -> bool:
        """启动数据发送

        Returns:
            启动是否成功
        """
        if self.enabled:
            return True

        if not self.serial_assistant or not self.serial_assistant.is_connected:
            return False

        self.enabled = True
        self.stop_event.clear()

        try:
            if self.send_time_data:
                self._start_sender_thread(DataCategory.TIME)

            if self.send_api_data:
                self._start_sender_thread(DataCategory.API)

            if self.send_performance_data:
                self._start_sender_thread(DataCategory.PERFORMANCE)

            return True
        except Exception:
            self.enabled = False
            return False

    def stop(self) -> None:
        """停止数据发送"""
        if not self.enabled:
            return

        self.enabled = False
        self.stop_event.set()

        # 并行等待所有线程结束，而非顺序等待
        # 这样总超时时间是 max(各线程时间) 而非 sum(各线程时间)
        alive_threads = [t for t in self.sender_threads.values() if t and t.is_alive()]
        for thread in alive_threads:
            thread.join(timeout=0.5)  # 缩短单个超时时间

        self.sender_threads.clear()

    def _start_sender_thread(self, category: DataCategory) -> None:
        """启动指定类别的发送线程

        Args:
            category: 数据类别
        """
        if category in self.sender_threads:
            return

        thread = threading.Thread(
            target=self._sender_worker,
            args=(category,),
            daemon=True,
            name=f"FinshSender-{category.value}",
        )

        self.sender_threads[category] = thread
        thread.start()

    def _sender_worker(self, category: DataCategory) -> None:
        """发送工作线程 - 支持初始延迟

        Args:
            category: 数据类别
        """
        interval = self.intervals[category]
        data_provider = self.data_providers[category]
        initial_delay = self.initial_delays.get(category, 0.0)

        # 初始延迟（可被stop_event中断）
        if initial_delay > 0:
            # 分段等待，以便能够响应stop信号
            delay_remaining = initial_delay
            while delay_remaining > 0 and not self.stop_event.is_set():
                sleep_time = min(0.1, delay_remaining)
                time.sleep(sleep_time)
                delay_remaining -= sleep_time

            # 如果在延迟期间被停止，直接退出
            if self.stop_event.is_set():
                return

        # 首次发送
        try:
            data_dict = data_provider()
            self._send_data_dict(data_dict)
        except Exception:
            self.stats["errors"] += 1

        last_send = time.time()

        # 周期性发送
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
                self.stats["errors"] += 1
                time.sleep(1)

    def _send_data_dict(self, data_dict: dict[str, Any]) -> None:
        """发送数据字典

        Args:
            data_dict: 要发送的数据字典
        """
        if (
            not data_dict
            or not self.serial_assistant
            or not self.serial_assistant.is_connected
        ):
            return

        for key, value in data_dict.items():
            if value is not None:
                try:
                    command = self._format_command(key, value)
                    self._send_command(command)
                    if self.min_command_interval > 0:
                        time.sleep(self.min_command_interval / 1000.0)
                except Exception:
                    self.stats["errors"] += 1

    def _format_command(self, key: str, value: Any) -> str:
        """格式化命令字符串

        Args:
            key: 命令键
            value: 命令值

        Returns:
            格式化后的命令字符串
        """
        if isinstance(value, str):
            return f'sys_set {key} "{value}"\n'
        elif isinstance(value, (int, float)):
            if isinstance(value, float):
                return f"sys_set {key} {value:.2f}\n"
            else:
                return f"sys_set {key} {value}\n"
        else:
            return f'sys_set {key} "{str(value)}"\n'

    def _send_command(self, command: str) -> None:
        """发送命令

        Args:
            command: 要发送的命令字符串
        """
        if self.serial_assistant and self.serial_assistant.is_connected:
            success = self.serial_assistant.send_data(command)
            if success:
                self.stats["commands_sent"] += 1
                self.stats["last_send_time"] = datetime.now()
            else:
                self.stats["errors"] += 1

    def _get_time_data(self) -> dict[str, Any]:
        """获取时间数据

        Returns:
            包含时间、日期、星期的字典
        """
        now = datetime.now()
        weekdays = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        return {
            "time": now.strftime("%H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "weekday": weekdays[now.weekday()],
        }

    def _get_api_data(self) -> dict[str, Any]:
        """获取API数据（天气等）

        Returns:
            API数据字典
        """
        data: dict[str, Any] = {}

        if self.weather_api:
            try:
                weather_data = self.weather_api.get_weather_data()
                if weather_data.get("success", False):
                    icon_code = weather_data.get("icon_code", "999")

                    try:
                        weather_code_int = int(icon_code)
                    except ValueError:
                        weather_code_int = 999

                    # 实时天气数据
                    city_name = weather_data.get("city_name", "")
                    data.update(
                        {
                            "temp": int(round(weather_data.get("temperature", 0))),
                            "weather_code": weather_code_int,
                            "humidity": int(weather_data.get("humidity", 0)),
                            "pressure": int(weather_data.get("pressure", 0)),
                            "city_code": CityCodeMapper.get_city_code(city_name),
                        }
                    )

                    # 天气预报数据 (今天、明天、后天三天)
                    forecast_list = weather_data.get("forecast", [])
                    if forecast_list and len(forecast_list) >= 3:
                        # 今天的预报
                        day0 = forecast_list[0]
                        data.update(
                            {
                                "forecast_day0_text": day0.get("text_day", ""),
                                "forecast_day0_temp_max": int(day0.get("temp_max", 0)),
                                "forecast_day0_temp_min": int(day0.get("temp_min", 0)),
                                "forecast_day0_wind_dir": day0.get("wind_dir_day", ""),
                                "forecast_day0_wind_scale": day0.get(
                                    "wind_scale_day", ""
                                ),
                            }
                        )

                        # 明天的预报
                        day1 = forecast_list[1]
                        data.update(
                            {
                                "forecast_day1_text": day1.get("text_day", ""),
                                "forecast_day1_temp_max": int(day1.get("temp_max", 0)),
                                "forecast_day1_temp_min": int(day1.get("temp_min", 0)),
                                "forecast_day1_wind_dir": day1.get("wind_dir_day", ""),
                                "forecast_day1_wind_scale": day1.get(
                                    "wind_scale_day", ""
                                ),
                            }
                        )

                        # 后天的预报
                        day2 = forecast_list[2]
                        data.update(
                            {
                                "forecast_day2_text": day2.get("text_day", ""),
                                "forecast_day2_temp_max": int(day2.get("temp_max", 0)),
                                "forecast_day2_temp_min": int(day2.get("temp_min", 0)),
                                "forecast_day2_wind_dir": day2.get("wind_dir_day", ""),
                                "forecast_day2_wind_scale": day2.get(
                                    "wind_scale_day", ""
                                ),
                            }
                        )

            except Exception:
                pass

        return data

    def _get_performance_data(self) -> dict[str, Any]:
        """获取性能数据

        Returns:
            性能数据字典
        """
        if not self.hardware_monitor:
            return {}

        data: dict[str, Any] = {}

        try:
            cpu_data = self.hardware_monitor.get_cpu_data()
            data["cpu"] = float(cpu_data.get("usage", 0) or 0)
            data["cpu_temp"] = float(cpu_data.get("temp", 0) or 0)

            mem_data = self.hardware_monitor.get_memory_data()
            data["mem"] = float(mem_data.get("percent", 0) or 0)

            gpu_data = self.hardware_monitor.get_gpu_data(self.gpu_index)
            data["gpu"] = float(gpu_data.get("util", 0) or 0)
            data["gpu_temp"] = float(gpu_data.get("temp", 0) or 0)

            net_data = self.hardware_monitor.get_network_data()
            net_up = net_data.get("up", 0) or 0
            net_down = net_data.get("down", 0) or 0
            data["net_up"] = round(net_up / (1024 * 1024), 2) if net_up else 0.0
            data["net_down"] = round(net_down / (1024 * 1024), 2) if net_down else 0.0

        except Exception:
            pass

        return data

    def get_status(self) -> dict[str, Any]:
        """获取发送器状态

        Returns:
            状态信息字典
        """
        is_connected = False
        if self.serial_assistant:
            is_connected = self.serial_assistant.is_connected
        active_count = len(
            [t for t in self.sender_threads.values() if t and t.is_alive()]
        )
        return {
            "enabled": self.enabled,
            "connected": is_connected,
            "send_time_data": self.send_time_data,
            "send_api_data": self.send_api_data,
            "send_performance_data": self.send_performance_data,
            "intervals": dict(self.intervals),
            "initial_delays": dict(self.initial_delays),
            "min_command_interval": self.min_command_interval,
            "stats": dict(self.stats),
            "active_threads": active_count,
        }

    def get_configuration(self) -> dict[str, Any]:
        """获取发送器配置

        Returns:
            配置信息字典
        """
        return {
            "enabled": self.enabled,
            "send_time_data": self.send_time_data,
            "send_api_data": self.send_api_data,
            "send_performance_data": self.send_performance_data,
            "time_interval": self.intervals[DataCategory.TIME],
            "api_interval": self.intervals[DataCategory.API],
            "performance_interval": self.intervals[DataCategory.PERFORMANCE],
            "api_initial_delay": self.initial_delays[DataCategory.API],
            "min_command_interval": self.min_command_interval,
        }

    def __del__(self) -> None:
        """析构函数，确保资源释放"""
        self.stop()
