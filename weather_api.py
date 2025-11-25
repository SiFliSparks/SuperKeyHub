#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

class QWeatherAPI:
    def __init__(self, api_key: str = "", default_city: str = "beijing", api_host: str = "", use_jwt: bool = False):
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
        # 直辖市 (4个)
        "北京": "101010100", "beijing": "101010100", "Beijing": "101010100",
        "上海": "101020100", "shanghai": "101020100", "Shanghai": "101020100", 
        "天津": "101030100", "tianjin": "101030100", "Tianjin": "101030100",
        "重庆": "101040100", "chongqing": "101040100", "Chongqing": "101040100",
        
        # 河北省
        "石家庄": "101090101", "shijiazhuang": "101090101", "Shijiazhuang": "101090101",
        "唐山": "101090201", "tangshan": "101090201", "Tangshan": "101090201",
        "秦皇岛": "101091101", "qinhuangdao": "101091101", "Qinhuangdao": "101091101",
        "邯郸": "101090401", "handan": "101090401", "Handan": "101090401",
        "邢台": "101090501", "xingtai": "101090501", "Xingtai": "101090501",
        "保定": "101090601", "baoding": "101090601", "Baoding": "101090601",
        "张家口": "101090701", "zhangjiakou": "101090701", "Zhangjiakou": "101090701",
        "承德": "101090801", "chengde": "101090801", "Chengde": "101090801",
        "沧州": "101090901", "cangzhou": "101090901", "Cangzhou": "101090901",
        "廊坊": "101091001", "langfang": "101091001", "Langfang": "101091001",
        "衡水": "101091201", "hengshui": "101091201", "Hengshui": "101091201",
        
        # 山西省
        "太原": "101100101", "taiyuan": "101100101", "Taiyuan": "101100101",
        "大同": "101100201", "datong": "101100201", "Datong": "101100201",
        "阳泉": "101100301", "yangquan": "101100301", "Yangquan": "101100301",
        "长治": "101100401", "changzhi": "101100401", "Changzhi": "101100401",
        "晋城": "101100501", "jincheng": "101100501", "Jincheng": "101100501",
        "朔州": "101100601", "shuozhou": "101100601", "Shuozhou": "101100601",
        "晋中": "101100701", "jinzhong": "101100701", "Jinzhong": "101100701",
        "运城": "101100801", "yuncheng": "101100801", "Yuncheng": "101100801",
        "忻州": "101100901", "xinzhou": "101100901", "Xinzhou": "101100901",
        "临汾": "101101001", "linfen": "101101001", "Linfen": "101101001",
        "吕梁": "101101100", "lvliang": "101101100", "Lvliang": "101101100",
        
        # 内蒙古自治区
        "呼和浩特": "101080101", "hohhot": "101080101", "Hohhot": "101080101",
        "包头": "101080201", "baotou": "101080201", "Baotou": "101080201",
        "乌海": "101080301", "wuhai": "101080301", "Wuhai": "101080301",
        "赤峰": "101080401", "chifeng": "101080401", "Chifeng": "101080401",
        "通辽": "101080501", "tongliao": "101080501", "Tongliao": "101080501",
        "鄂尔多斯": "101080601", "ordos": "101080601", "Ordos": "101080601",
        "呼伦贝尔": "101080701", "hulunbuir": "101080701", "Hulunbuir": "101080701",
        "巴彦淖尔": "101080801", "bayannur": "101080801", "Bayannur": "101080801",
        "乌兰察布": "101080901", "ulanqab": "101080901", "Ulanqab": "101080901",
        
        # 辽宁省
        "沈阳": "101070101", "shenyang": "101070101", "Shenyang": "101070101",
        "大连": "101070201", "dalian": "101070201", "Dalian": "101070201",
        "鞍山": "101070301", "anshan": "101070301", "Anshan": "101070301",
        "抚顺": "101070401", "fushun": "101070401", "Fushun": "101070401",
        "本溪": "101070501", "benxi": "101070501", "Benxi": "101070501",
        "丹东": "101070601", "dandong": "101070601", "Dandong": "101070601",
        "锦州": "101070701", "jinzhou": "101070701", "Jinzhou": "101070701",
        "营口": "101070801", "yingkou": "101070801", "Yingkou": "101070801",
        "阜新": "101070901", "fuxin": "101070901", "Fuxin": "101070901",
        "辽阳": "101071001", "liaoyang": "101071001", "Liaoyang": "101071001",
        "盘锦": "101071101", "panjin": "101071101", "Panjin": "101071101",
        "铁岭": "101071201", "tieling": "101071201", "Tieling": "101071201",
        "朝阳": "101071301", "chaoyang": "101071301", "Chaoyang": "101071301",
        "葫芦岛": "101071401", "huludao": "101071401", "Huludao": "101071401",
        
        # 吉林省
        "长春": "101060101", "changchun": "101060101", "Changchun": "101060101",
        "吉林": "101060201", "jilin": "101060201", "Jilin": "101060201",
        "四平": "101060301", "siping": "101060301", "Siping": "101060301",
        "辽源": "101060401", "liaoyuan": "101060401", "Liaoyuan": "101060401",
        "通化": "101060501", "tonghua": "101060501", "Tonghua": "101060501",
        "白山": "101060601", "baishan": "101060601", "Baishan": "101060601",
        "松原": "101060701", "songyuan": "101060701", "Songyuan": "101060701",
        "白城": "101060801", "baicheng": "101060801", "Baicheng": "101060801",
        
        # 黑龙江省
        "哈尔滨": "101050101", "harbin": "101050101", "Harbin": "101050101",
        "齐齐哈尔": "101050201", "qiqihar": "101050201", "Qiqihar": "101050201",
        "鸡西": "101050301", "jixi": "101050301", "Jixi": "101050301",
        "鹤岗": "101050401", "hegang": "101050401", "Hegang": "101050401",
        "双鸭山": "101050501", "shuangyashan": "101050501", "Shuangyashan": "101050501",
        "大庆": "101050601", "daqing": "101050601", "Daqing": "101050601",
        "伊春": "101050701", "yichun": "101050701", "Yichun": "101050701",
        "佳木斯": "101050801", "jiamusi": "101050801", "Jiamusi": "101050801",
        "七台河": "101050901", "qitaihe": "101050901", "Qitaihe": "101050901",
        "牡丹江": "101051001", "mudanjiang": "101051001", "Mudanjiang": "101051001",
        "黑河": "101051101", "heihe": "101051101", "Heihe": "101051101",
        "绥化": "101051201", "suihua": "101051201", "Suihua": "101051201",
        
        # 江苏省
        "南京": "101190101", "nanjing": "101190101", "Nanjing": "101190101", 
        "无锡": "101190201", "wuxi": "101190201", "Wuxi": "101190201",
        "徐州": "101190301", "xuzhou": "101190301", "Xuzhou": "101190301",
        "苏州": "101190401", "suzhou": "101190401", "Suzhou": "101190401",
        "南通": "101190501", "nantong": "101190501", "Nantong": "101190501",
        "连云港": "101190601", "lianyungang": "101190601", "Lianyungang": "101190601",
        "扬州": "101190701", "yangzhou": "101190701", "Yangzhou": "101190701",
        "盐城": "101190801", "yancheng": "101190801", "Yancheng": "101190801",
        "淮安": "101190901", "huaian": "101190901", "Huaian": "101190901",
        "常州": "101191001", "changzhou": "101191001", "Changzhou": "101191001",
        "镇江": "101191101", "zhenjiang": "101191101", "Zhenjiang": "101191101",
        "泰州": "101191201", "taizhou": "101191201", "Taizhou": "101191201",
        "宿迁": "101191301", "suqian": "101191301", "Suqian": "101191301",
        
        # 浙江省
        "杭州": "101210101", "hangzhou": "101210101", "Hangzhou": "101210101",
        "宁波": "101210401", "ningbo": "101210401", "Ningbo": "101210401",
        "温州": "101210301", "wenzhou": "101210301", "Wenzhou": "101210301",
        "嘉兴": "101210501", "jiaxing": "101210501", "Jiaxing": "101210501",
        "湖州": "101210601", "huzhou": "101210601", "Huzhou": "101210601",
        "绍兴": "101210701", "shaoxing": "101210701", "Shaoxing": "101210701",
        "金华": "101210801", "jinhua": "101210801", "Jinhua": "101210801",
        "衢州": "101210901", "quzhou": "101210901", "Quzhou": "101210901",
        "舟山": "101211001", "zhoushan": "101211001", "Zhoushan": "101211001",
        "台州": "101211101", "taizhou_zj": "101211101", "Taizhou_ZJ": "101211101",
        "丽水": "101211201", "lishui": "101211201", "Lishui": "101211201",
        
        # 安徽省
        "合肥": "101220101", "hefei": "101220101", "Hefei": "101220101",
        "芜湖": "101220301", "wuhu": "101220301", "Wuhu": "101220301",
        "蚌埠": "101220201", "bengbu": "101220201", "Bengbu": "101220201",
        "淮南": "101220401", "huainan": "101220401", "Huainan": "101220401",
        "马鞍山": "101220501", "maanshan": "101220501", "Maanshan": "101220501",
        "淮北": "101220601", "huaibei": "101220601", "Huaibei": "101220601",
        "铜陵": "101220701", "tongling": "101220701", "Tongling": "101220701",
        "安庆": "101220801", "anqing": "101220801", "Anqing": "101220801",
        "黄山": "101220901", "huangshan": "101220901", "Huangshan": "101220901",
        "滁州": "101221001", "chuzhou": "101221001", "Chuzhou": "101221001",
        "阜阳": "101221101", "fuyang": "101221101", "Fuyang": "101221101",
        "宿州": "101221201", "suzhou_ah": "101221201", "Suzhou_AH": "101221201",
        "六安": "101221301", "luan": "101221301", "Luan": "101221301",
        "亳州": "101221401", "bozhou": "101221401", "Bozhou": "101221401",
        "池州": "101221501", "chizhou": "101221501", "Chizhou": "101221501",
        "宣城": "101221601", "xuancheng": "101221601", "Xuancheng": "101221601",
        
        # 福建省
        "福州": "101230101", "fuzhou": "101230101", "Fuzhou": "101230101",
        "厦门": "101230201", "xiamen": "101230201", "Xiamen": "101230201",
        "莆田": "101230301", "putian": "101230301", "Putian": "101230301",
        "三明": "101230401", "sanming": "101230401", "Sanming": "101230401",
        "泉州": "101230501", "quanzhou": "101230501", "Quanzhou": "101230501",
        "漳州": "101230601", "zhangzhou": "101230601", "Zhangzhou": "101230601",
        "南平": "101230701", "nanping": "101230701", "Nanping": "101230701",
        "龙岩": "101230801", "longyan": "101230801", "Longyan": "101230801",
        "宁德": "101230901", "ningde": "101230901", "Ningde": "101230901",
        
        # 江西省
        "南昌": "101240101", "nanchang": "101240101", "Nanchang": "101240101",
        "景德镇": "101240201", "jingdezhen": "101240201", "Jingdezhen": "101240201",
        "萍乡": "101240301", "pingxiang": "101240301", "Pingxiang": "101240301",
        "九江": "101240401", "jiujiang": "101240401", "Jiujiang": "101240401",
        "新余": "101240501", "xinyu": "101240501", "Xinyu": "101240501",
        "鹰潭": "101240601", "yingtan": "101240601", "Yingtan": "101240601",
        "赣州": "101240701", "ganzhou": "101240701", "Ganzhou": "101240701",
        "吉安": "101240801", "jian": "101240801", "Jian": "101240801",
        "宜春": "101240901", "yichun_jx": "101240901", "Yichun_JX": "101240901",
        "抚州": "101241001", "fuzhou_jx": "101241001", "Fuzhou_JX": "101241001",
        "上饶": "101241101", "shangrao": "101241101", "Shangrao": "101241101",
        
        # 山东省
        "济南": "101120101", "jinan": "101120101", "Jinan": "101120101",
        "青岛": "101120201", "qingdao": "101120201", "Qingdao": "101120201",
        "淄博": "101120301", "zibo": "101120301", "Zibo": "101120301",
        "枣庄": "101120401", "zaozhuang": "101120401", "Zaozhuang": "101120401",
        "东营": "101120501", "dongying": "101120501", "Dongying": "101120501",
        "烟台": "101120601", "yantai": "101120601", "Yantai": "101120601",
        "潍坊": "101120701", "weifang": "101120701", "Weifang": "101120701",
        "济宁": "101120801", "jining": "101120801", "Jining": "101120801",
        "泰安": "101120901", "taian": "101120901", "Taian": "101120901",
        "威海": "101121001", "weihai": "101121001", "Weihai": "101121001",
        "日照": "101121101", "rizhao": "101121101", "Rizhao": "101121101",
        "莱芜": "101121201", "laiwu": "101121201", "Laiwu": "101121201",
        "临沂": "101121301", "linyi": "101121301", "Linyi": "101121301",
        "德州": "101121401", "dezhou": "101121401", "Dezhou": "101121401",
        "聊城": "101121501", "liaocheng": "101121501", "Liaocheng": "101121501",
        "滨州": "101121601", "binzhou": "101121601", "Binzhou": "101121601",
        "菏泽": "101121701", "heze": "101121701", "Heze": "101121701",
        
        # 河南省
        "郑州": "101180101", "zhengzhou": "101180101", "Zhengzhou": "101180101",
        "开封": "101181001", "kaifeng": "101181001", "Kaifeng": "101181001",
        "洛阳": "101180801", "luoyang": "101180801", "Luoyang": "101180801",
        "平顶山": "101180901", "pingdingshan": "101180901", "Pingdingshan": "101180901",
        "安阳": "101180301", "anyang": "101180301", "Anyang": "101180301",
        "鹤壁": "101180401", "hebi": "101180401", "Hebi": "101180401",
        "新乡": "101180501", "xinxiang": "101180501", "Xinxiang": "101180501",
        "焦作": "101180601", "jiaozuo": "101180601", "Jiaozuo": "101180601",
        "濮阳": "101180701", "puyang": "101180701", "Puyang": "101180701",
        "许昌": "101181101", "xuchang": "101181101", "Xuchang": "101181101",
        "漯河": "101181201", "luohe": "101181201", "Luohe": "101181201",
        "三门峡": "101181301", "sanmenxia": "101181301", "Sanmenxia": "101181301",
        "南阳": "101181401", "nanyang": "101181401", "Nanyang": "101181401",
        "商丘": "101181501", "shangqiu": "101181501", "Shangqiu": "101181501",
        "信阳": "101181601", "xinyang": "101181601", "Xinyang": "101181601",
        "周口": "101181701", "zhoukou": "101181701", "Zhoukou": "101181701",
        "驻马店": "101181801", "zhumadian": "101181801", "Zhumadian": "101181801",
        
        # 湖北省
        "武汉": "101200101", "wuhan": "101200101", "Wuhan": "101200101",
        "黄石": "101200201", "huangshi": "101200201", "Huangshi": "101200201",
        "十堰": "101200301", "shiyan": "101200301", "Shiyan": "101200301",
        "宜昌": "101200401", "yichang": "101200401", "Yichang": "101200401",
        "襄阳": "101200501", "xiangyang": "101200501", "Xiangyang": "101200501",
        "鄂州": "101200601", "ezhou": "101200601", "Ezhou": "101200601",
        "荆门": "101200701", "jingmen": "101200701", "Jingmen": "101200701",
        "孝感": "101200801", "xiaogan": "101200801", "Xiaogan": "101200801",
        "荆州": "101200901", "jingzhou": "101200901", "Jingzhou": "101200901",
        "黄冈": "101201001", "huanggang": "101201001", "Huanggang": "101201001",
        "咸宁": "101201101", "xianning": "101201101", "Xianning": "101201101",
        "随州": "101201201", "suizhou": "101201201", "Suizhou": "101201201",
        
        # 湖南省
        "长沙": "101250101", "changsha": "101250101", "Changsha": "101250101",
        "株洲": "101250201", "zhuzhou": "101250201", "Zhuzhou": "101250201",
        "湘潭": "101250301", "xiangtan": "101250301", "Xiangtan": "101250301",
        "衡阳": "101250401", "hengyang": "101250401", "Hengyang": "101250401",
        "邵阳": "101250501", "shaoyang": "101250501", "Shaoyang": "101250501",
        "岳阳": "101250601", "yueyang": "101250601", "Yueyang": "101250601",
        "常德": "101250701", "changde": "101250701", "Changde": "101250701",
        "张家界": "101250801", "zhangjiajie": "101250801", "Zhangjiajie": "101250801",
        "益阳": "101250901", "yiyang": "101250901", "Yiyang": "101250901",
        "郴州": "101251001", "chenzhou": "101251001", "Chenzhou": "101251001",
        "永州": "101251101", "yongzhou": "101251101", "Yongzhou": "101251101",
        "怀化": "101251201", "huaihua": "101251201", "Huaihua": "101251201",
        "娄底": "101251301", "loudi": "101251301", "Loudi": "101251301",
        
        # 广东省
        "广州": "101280101", "guangzhou": "101280101", "Guangzhou": "101280101",
        "韶关": "101280201", "shaoguan": "101280201", "Shaoguan": "101280201",
        "深圳": "101280601", "shenzhen": "101280601", "Shenzhen": "101280601",
        "珠海": "101280701", "zhuhai": "101280701", "Zhuhai": "101280701",
        "汕头": "101280501", "shantou": "101280501", "Shantou": "101280501",
        "佛山": "101280800", "foshan": "101280800", "Foshan": "101280800",
        "江门": "101281001", "jiangmen": "101281001", "Jiangmen": "101281001",
        "湛江": "101281401", "zhanjiang": "101281401", "Zhanjiang": "101281401",
        "茂名": "101281501", "maoming": "101281501", "Maoming": "101281501",
        "肇庆": "101280901", "zhaoqing": "101280901", "Zhaoqing": "101280901",
        "惠州": "101281101", "huizhou": "101281101", "Huizhou": "101281101",
        "梅州": "101281201", "meizhou": "101281201", "Meizhou": "101281201",
        "汕尾": "101281301", "shanwei": "101281301", "Shanwei": "101281301",
        "河源": "101281801", "heyuan": "101281801", "Heyuan": "101281801",
        "阳江": "101281901", "yangjiang": "101281901", "Yangjiang": "101281901",
        "清远": "101282001", "qingyuan": "101282001", "Qingyuan": "101282001",
        "东莞": "101281601", "dongguan": "101281601", "Dongguan": "101281601",
        "中山": "101281701", "zhongshan": "101281701", "Zhongshan": "101281701",
        "潮州": "101282101", "chaozhou": "101282101", "Chaozhou": "101282101",
        "揭阳": "101282201", "jieyang": "101282201", "Jieyang": "101282201",
        "云浮": "101282301", "yunfu": "101282301", "Yunfu": "101282301",
        
        # 广西壮族自治区
        "南宁": "101300101", "nanning": "101300101", "Nanning": "101300101",
        "柳州": "101300201", "liuzhou": "101300201", "Liuzhou": "101300201",
        "桂林": "101300501", "guilin": "101300501", "Guilin": "101300501",
        "梧州": "101300401", "wuzhou": "101300401", "Wuzhou": "101300401",
        "北海": "101301401", "beihai": "101301401", "Beihai": "101301401",
        "防城港": "101301501", "fangchenggang": "101301501", "Fangchenggang": "101301501",
        "钦州": "101301201", "qinzhou": "101301201", "Qinzhou": "101301201",
        "贵港": "101300301", "guigang": "101300301", "Guigang": "101300301",
        "玉林": "101300601", "yulin_gx": "101300601", "Yulin_GX": "101300601",
        "百色": "101300701", "baise": "101300701", "Baise": "101300701",
        "贺州": "101300801", "hezhou": "101300801", "Hezhou": "101300801",
        "河池": "101300901", "hechi": "101300901", "Hechi": "101300901",
        "来宾": "101301001", "laibin": "101301001", "Laibin": "101301001",
        "崇左": "101301101", "chongzuo": "101301101", "Chongzuo": "101301101",
        
        # 海南省
        "海口": "101310101", "haikou": "101310101", "Haikou": "101310101",
        "三亚": "101310201", "sanya": "101310201", "Sanya": "101310201",
        "三沙": "101310301", "sansha": "101310301", "Sansha": "101310301",
        "儋州": "101310401", "danzhou": "101310401", "Danzhou": "101310401",
        
        # 四川省
        "成都": "101270101", "chengdu": "101270101", "Chengdu": "101270101",
        "自贡": "101270201", "zigong": "101270201", "Zigong": "101270201",
        "攀枝花": "101270301", "panzhihua": "101270301", "Panzhihua": "101270301",
        "泸州": "101270401", "luzhou": "101270401", "Luzhou": "101270401",
        "德阳": "101270501", "deyang": "101270501", "Deyang": "101270501",
        "绵阳": "101270601", "mianyang": "101270601", "Mianyang": "101270601",
        "广元": "101270701", "guangyuan": "101270701", "Guangyuan": "101270701",
        "遂宁": "101270801", "suining": "101270801", "Suining": "101270801",
        "内江": "101270901", "neijiang": "101270901", "Neijiang": "101270901",
        "乐山": "101271001", "leshan": "101271001", "Leshan": "101271001",
        "南充": "101271101", "nanchong": "101271101", "Nanchong": "101271101",
        "眉山": "101271201", "meishan": "101271201", "Meishan": "101271201",
        "宜宾": "101271301", "yibin": "101271301", "Yibin": "101271301",
        "广安": "101271401", "guangan": "101271401", "Guangan": "101271401",
        "达州": "101271501", "dazhou": "101271501", "Dazhou": "101271501",
        "雅安": "101271601", "yaan": "101271601", "Yaan": "101271601",
        "巴中": "101271701", "bazhong": "101271701", "Bazhong": "101271701",
        "资阳": "101271801", "ziyang": "101271801", "Ziyang": "101271801",
        
        # 贵州省
        "贵阳": "101260101", "guiyang": "101260101", "Guiyang": "101260101",
        "六盘水": "101260201", "liupanshui": "101260201", "Liupanshui": "101260201",
        "遵义": "101260301", "zunyi": "101260301", "Zunyi": "101260301",
        "安顺": "101260401", "anshun": "101260401", "Anshun": "101260401",
        "毕节": "101260501", "bijie": "101260501", "Bijie": "101260501",
        "铜仁": "101260601", "tongren": "101260601", "Tongren": "101260601",
        
        # 云南省
        "昆明": "101290101", "kunming": "101290101", "Kunming": "101290101",
        "曲靖": "101290201", "qujing": "101290201", "Qujing": "101290201",
        "玉溪": "101290301", "yuxi": "101290301", "Yuxi": "101290301",
        "保山": "101290401", "baoshan": "101290401", "Baoshan": "101290401",
        "昭通": "101290501", "zhaotong": "101290501", "Zhaotong": "101290501",
        "丽江": "101290601", "lijiang": "101290601", "Lijiang": "101290601",
        "普洱": "101290701", "puer": "101290701", "Puer": "101290701",
        "临沧": "101290801", "lincang": "101290801", "Lincang": "101290801",
        
        # 西藏自治区
        "拉萨": "101140101", "lhasa": "101140101", "Lhasa": "101140101",
        "昌都": "101140201", "changdu": "101140201", "Changdu": "101140201",
        "山南": "101140301", "shannan": "101140301", "Shannan": "101140301",
        "日喀则": "101140401", "rikaze": "101140401", "Rikaze": "101140401",
        "那曲": "101140501", "naqu": "101140501", "Naqu": "101140501",
        "阿里": "101140601", "ali": "101140601", "Ali": "101140601",
        "林芝": "101140701", "linzhi": "101140701", "Linzhi": "101140701",
        
        # 陕西省
        "西安": "101110101", "xian": "101110101", "Xian": "101110101",
        "铜川": "101110201", "tongchuan": "101110201", "Tongchuan": "101110201",
        "宝鸡": "101110301", "baoji": "101110301", "Baoji": "101110301",
        "咸阳": "101110401", "xianyang": "101110401", "Xianyang": "101110401",
        "渭南": "101110501", "weinan": "101110501", "Weinan": "101110501",
        "延安": "101110601", "yanan": "101110601", "Yanan": "101110601",
        "汉中": "101110701", "hanzhong": "101110701", "Hanzhong": "101110701",
        "榆林": "101110801", "yulin_sx": "101110801", "Yulin_SX": "101110801",
        "安康": "101110901", "ankang": "101110901", "Ankang": "101110901",
        "商洛": "101111001", "shangluo": "101111001", "Shangluo": "101111001",
        
        # 甘肃省
        "兰州": "101160101", "lanzhou": "101160101", "Lanzhou": "101160101",
        "嘉峪关": "101160201", "jiayuguan": "101160201", "Jiayuguan": "101160201",
        "金昌": "101160301", "jinchang": "101160301", "Jinchang": "101160301",
        "白银": "101160401", "baiyin": "101160401", "Baiyin": "101160401",
        "天水": "101160501", "tianshui": "101160501", "Tianshui": "101160501",
        "武威": "101160601", "wuwei": "101160601", "Wuwei": "101160601",
        "张掖": "101160701", "zhangye": "101160701", "Zhangye": "101160701",
        "平凉": "101160801", "pingliang": "101160801", "Pingliang": "101160801",
        "酒泉": "101160901", "jiuquan": "101160901", "Jiuquan": "101160901",
        "庆阳": "101161001", "qingyang": "101161001", "Qingyang": "101161001",
        "定西": "101161101", "dingxi": "101161101", "Dingxi": "101161101",
        "陇南": "101161201", "longnan": "101161201", "Longnan": "101161201",
        
        # 青海省
        "西宁": "101150101", "xining": "101150101", "Xining": "101150101",
        "海东": "101150201", "haidong": "101150201", "Haidong": "101150201",
        
        # 宁夏回族自治区
        "银川": "101170101", "yinchuan": "101170101", "Yinchuan": "101170101",
        "石嘴山": "101170201", "shizuishan": "101170201", "Shizuishan": "101170201",
        "吴忠": "101170301", "wuzhong": "101170301", "Wuzhong": "101170301",
        "固原": "101170401", "guyuan": "101170401", "Guyuan": "101170401",
        "中卫": "101170501", "zhongwei": "101170501", "Zhongwei": "101170501",
        
        # 新疆维吾尔自治区
        "乌鲁木齐": "101130101", "urumqi": "101130101", "Urumqi": "101130101",
        "克拉玛依": "101130201", "kelamayi": "101130201", "Kelamayi": "101130201",
        "吐鲁番": "101130301", "turpan": "101130301", "Turpan": "101130301",
        "哈密": "101130401", "hami": "101130401", "Hami": "101130401",
        "昌吉": "101130501", "changji": "101130501", "Changji": "101130501",
        "博尔塔拉": "101130601", "boertala": "101130601", "Boertala": "101130601",
        "巴音郭楞": "101130701", "bayinguoleng": "101130701", "Bayinguoleng": "101130701",
        "阿克苏": "101130801", "akesu": "101130801", "Akesu": "101130801",
        "克孜勒苏": "101130901", "kezilesu": "101130901", "Kezilesu": "101130901",
        "喀什": "101131001", "kashi": "101131001", "Kashi": "101131001",
        "和田": "101131101", "hetian": "101131101", "Hetian": "101131101",
        "伊犁": "101131201", "yili": "101131201", "Yili": "101131201",
        "塔城": "101131301", "tacheng": "101131301", "Tacheng": "101131301",
        "阿勒泰": "101131401", "aletai": "101131401", "Aletai": "101131401",
        
        # 特别行政区
        "香港": "101320101", "hongkong": "101320101", "HongKong": "101320101",
        "澳门": "101330101", "macao": "101330101", "Macao": "101330101",
        
        # 台湾省（如果支持）
        "台北": "101340101", "taipei": "101340101", "Taipei": "101340101",
        "高雄": "101340201", "kaohsiung": "101340201", "Kaohsiung": "101340201",
        "台中": "101340301", "taichung": "101340301", "Taichung": "101340301",
        "台南": "101340401", "tainan": "101340401", "Tainan": "101340401",
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
                        'wind_direction': now.get('windDir', '未知'),
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

    def validate_config(self) -> Dict[str, Any]:
        issues = []
        
        if not self.api_key:
            issues.append("API密钥未设置")
        elif len(self.api_key) < 10:
            issues.append("API密钥格式可能不正确")
            
        if not self.api_host:
            issues.append("API Host未设置")
        elif not self.api_host.startswith('http'):
            issues.append("API Host格式不正确")
            
        if not self.default_city:
            issues.append("默认城市未设置")
            
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'config': self.get_config()
        }

    def clear_cache(self, city: str = None):
        if city:
            cache_key = f"weather_{city}"
            if cache_key in self.cache:
                del self.cache[cache_key]
        else:
            self.cache.clear()

WeatherAPI = QWeatherAPI