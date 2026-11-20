#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
东方玄学宗师 · 毫秒级真太阳时万年历与四大术数排盘引擎 (xuanxue_engine.py)
支持：
1. bazi      : 子平八字 + 盲派宾主做功 + 《穷通宝鉴》调候用神 + 真太阳时校正 + 大运流年
2. xiaoliuren: 道家小六壬（《玉匣记》马前课三宫掌诀 + 体用生克 + 日加时古诀）
3. meihua    : 《周易》六十四卦 + 梅花易数（本卦/互卦/变卦/动爻/体用生克）
4. ziwei     : 紫微斗数（命宫/身宫/五行局/十四主星安星/生年四化）
"""

import sys
import os
import math
import json
import argparse
from datetime import datetime, timedelta

LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from lunar_python import Solar, Lunar

# ==============================================================================
# 1. 中国主要城市经度表（用于真太阳时校正）
# ==============================================================================
CITY_LONGITUDE = {
    # 直辖市与港澳台
    "北京": 116.40, "上海": 121.47, "天津": 117.20, "重庆": 106.55,
    "香港": 114.17, "澳门": 113.54, "台北": 121.56, "高雄": 120.31, "台中": 120.67, "台南": 120.20,
    # 辽宁
    "沈阳": 123.43, "大连": 121.62, "鞍山": 122.99, "抚顺": 123.96, "本溪": 123.77, "丹东": 124.38,
    "锦州": 121.13, "营口": 122.23, "阜新": 121.67, "辽阳": 123.17, "盘锦": 122.07, "铁岭": 123.84,
    "朝阳": 120.45, "葫芦岛": 120.84,
    # 吉林
    "长春": 125.32, "吉林": 126.55, "四平": 124.35, "辽源": 125.14, "通化": 125.94, "白山": 126.42,
    "松原": 124.82, "白城": 122.84, "延吉": 129.51, "延边": 129.51,
    # 黑龙江
    "哈尔滨": 126.53, "齐齐哈尔": 123.92, "鸡西": 130.97, "鹤岗": 130.28, "双鸭山": 131.16,
    "大庆": 125.10, "伊春": 128.90, "佳木斯": 130.32, "七台河": 131.00, "牡丹江": 129.63,
    "黑河": 127.53, "绥化": 126.97, "大兴安岭": 124.12,
    # 河北
    "石家庄": 114.51, "唐山": 118.18, "秦皇岛": 119.60, "邯郸": 114.49, "邢台": 114.50,
    "保定": 115.46, "张家口": 114.88, "承德": 117.96, "沧州": 116.84, "廊坊": 116.68, "衡水": 115.67,
    # 山西
    "太原": 112.55, "大同": 113.30, "阳泉": 113.58, "长治": 113.12, "晋城": 112.85, "朔州": 112.43,
    "晋中": 112.75, "运城": 111.01, "忻州": 112.73, "临汾": 111.52, "吕梁": 111.14,
    # 内蒙古
    "呼和浩特": 111.75, "包头": 109.84, "乌海": 106.79, "赤峰": 118.89, "通辽": 122.24,
    "鄂尔多斯": 109.78, "呼伦贝尔": 119.77, "巴彦淖尔": 107.39, "乌兰察布": 113.13,
    # 山东
    "济南": 117.12, "青岛": 120.38, "淄博": 118.05, "枣庄": 117.32, "东营": 118.67, "烟台": 121.44,
    "潍坊": 119.16, "济宁": 116.59, "泰安": 117.09, "威海": 122.12, "日照": 119.53, "临沂": 118.36,
    "德州": 116.36, "聊城": 115.99, "滨州": 117.97, "菏泽": 115.48,
    # 江苏
    "南京": 118.79, "无锡": 120.31, "徐州": 117.28, "常州": 119.97, "苏州": 120.58, "南通": 120.89,
    "连云港": 119.22, "淮安": 119.02, "盐城": 120.16, "扬州": 119.41, "镇江": 119.43, "泰州": 119.92,
    "宿迁": 118.28, "昆山": 120.98, "江阴": 120.28,
    # 浙江
    "杭州": 120.15, "宁波": 121.55, "温州": 120.70, "嘉兴": 120.76, "湖州": 120.09, "绍兴": 120.58,
    "金华": 119.65, "义乌": 120.07, "衢州": 118.86, "舟山": 122.21, "台州": 121.42, "丽水": 119.92,
    # 安徽
    "合肥": 117.22, "芜湖": 118.43, "蚌埠": 117.39, "淮南": 116.99, "马鞍山": 118.51, "淮北": 116.80,
    "铜陵": 117.81, "安庆": 117.06, "黄山": 118.34, "滁州": 118.32, "阜阳": 115.81, "宿州": 116.96,
    "六安": 116.52, "亳州": 115.78, "池州": 117.49, "宣城": 118.76,
    # 福建
    "福州": 119.30, "厦门": 118.08, "莆田": 119.01, "三明": 117.64, "泉州": 118.67, "漳州": 117.65,
    "南平": 118.18, "龙岩": 117.02, "宁德": 119.55,
    # 江西
    "南昌": 115.85, "景德镇": 117.18, "萍乡": 113.85, "九江": 116.00, "新余": 114.92, "鹰潭": 117.07,
    "赣州": 114.93, "吉安": 114.99, "宜春": 114.42, "抚州": 116.36, "上饶": 117.94,
    # 河南
    "郑州": 113.62, "开封": 114.31, "洛阳": 112.45, "平顶山": 113.19, "安阳": 114.39, "鹤壁": 114.30,
    "新乡": 113.93, "焦作": 113.24, "濮阳": 115.03, "许昌": 113.85, "漯河": 114.02, "三门峡": 111.20,
    "南阳": 112.53, "商丘": 115.66, "信阳": 114.09, "周口": 114.70, "驻马店": 114.02,
    # 湖北
    "武汉": 114.30, "黄石": 115.04, "十堰": 110.80, "宜昌": 111.29, "襄阳": 112.12, "鄂州": 114.89,
    "荆门": 112.20, "孝感": 113.92, "荆州": 112.24, "黄冈": 114.87, "咸宁": 114.32, "随州": 113.38,
    "恩施": 109.49,
    # 湖南
    "长沙": 112.93, "株洲": 113.13, "湘潭": 112.94, "衡阳": 112.57, "邵阳": 111.47, "岳阳": 113.13,
    "常德": 111.70, "张家界": 110.48, "益阳": 112.36, "郴州": 113.01, "永州": 111.61, "怀化": 110.00,
    "娄底": 112.00, "湘西": 109.74,
    # 广东
    "广州": 113.26, "深圳": 114.06, "珠海": 113.57, "汕头": 116.68, "佛山": 113.12, "韶关": 113.60,
    "湛江": 110.36, "肇庆": 112.47, "江门": 113.08, "茂名": 110.93, "惠州": 114.42, "梅州": 116.12,
    "汕尾": 115.38, "河源": 114.70, "阳江": 111.98, "清远": 113.06, "东莞": 113.75, "中山": 113.39,
    "潮州": 116.62, "揭阳": 116.37, "云浮": 112.04,
    # 广西
    "南宁": 108.36, "柳州": 109.41, "桂林": 110.29, "梧州": 111.28, "北海": 109.12, "防城港": 108.35,
    "钦州": 108.65, "贵港": 109.60, "玉林": 110.18, "百色": 106.62, "贺州": 111.57, "河池": 108.09,
    # 海南
    "海口": 110.32, "三亚": 109.51, "儋州": 109.58,
    # 四川
    "成都": 104.06, "自贡": 104.77, "攀枝花": 101.72, "泸州": 105.44, "德阳": 104.40, "绵阳": 104.68,
    "广元": 105.84, "遂宁": 105.59, "内江": 105.06, "乐山": 103.77, "南充": 106.11, "眉山": 103.85,
    "宜宾": 104.64, "广安": 106.63, "达州": 107.47, "雅安": 103.04, "巴中": 106.74, "资阳": 104.63,
    "凉山": 102.27, "西昌": 102.26,
    # 贵州
    "贵阳": 106.63, "六盘水": 104.83, "遵义": 106.93, "安顺": 105.95, "毕节": 105.29, "铜仁": 109.19,
    # 云南
    "昆明": 102.83, "曲靖": 103.80, "玉溪": 102.55, "保山": 100.16, "昭通": 103.72, "丽江": 100.23,
    "普洱": 100.97, "临沧": 100.09, "大理": 100.27, "西双版纳": 100.80,
    # 西藏
    "拉萨": 91.11, "日喀则": 88.88, "昌都": 97.17, "林芝": 94.36,
    # 陕西
    "西安": 108.94, "铜川": 108.95, "宝鸡": 107.24, "咸阳": 108.71, "渭南": 109.51, "延安": 109.49,
    "汉中": 107.02, "榆林": 109.73, "安康": 109.03, "商洛": 109.94,
    # 甘肃
    "兰州": 103.83, "嘉峪关": 98.29, "金昌": 102.19, "白银": 104.14, "天水": 105.72, "武威": 102.64,
    "张掖": 100.45, "平凉": 106.66, "酒泉": 98.49, "庆阳": 107.64,
    # 青海、宁夏、新疆
    "西宁": 101.77, "海东": 102.10, "格尔木": 94.90,
    "银川": 106.23, "石嘴山": 106.38, "吴忠": 106.20, "固原": 106.24, "中卫": 105.20,
    "乌鲁木齐": 87.61, "克拉玛依": 84.89, "吐鲁番": 89.19, "哈密": 93.51, "昌吉": 87.31,
    "伊犁": 81.32, "伊宁": 81.32, "喀什": 75.99, "阿克苏": 80.26, "库尔勒": 86.17, "石河子": 86.08,
}

def resolve_city_longitude(city_str: str):
    if not city_str:
        return 120.0, "标准东八区(120°E)"
    if city_str in CITY_LONGITUDE:
        return CITY_LONGITUDE[city_str], city_str
    for k, v in CITY_LONGITUDE.items():
        if k in city_str or city_str in k:
            return v, f"{city_str}(匹配:{k})"
    return 120.0, f"{city_str}(默认东八区120°E)"

# ==============================================================================
# 2. 五行与干支基础数据库
# ==============================================================================
GAN_LIST = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
ZHI_LIST = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

GAN_WUXING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"
}
GAN_YINYANG = {
    "甲": "阳", "乙": "阴", "丙": "阳", "丁": "阴", "戊": "阳",
    "己": "阴", "庚": "阳", "辛": "阴", "壬": "阳", "癸": "阴"
}
ZHI_WUXING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"
}

# 《穷通宝鉴》十干十二月调候用神权威速查表
QIONGTONG_TIAOHOU = {
    "甲": {
        "寅": "丙癸（初春尚有余寒，先用丙火暖局，癸水滋润）",
        "卯": "庚丙丁（阳刃驾杀，庚金劈甲引丁，水作辅助）",
        "辰": "庚丁壬（春深木老，用庚金裁抑以引丁火，壬水润局）",
        "巳": "癸丁庚（初夏火旺木焦，首急癸水润根，次用庚丁）",
        "午": "癸庚丁（仲夏木性虚焦，无癸不发，庚金生水劈甲）",
        "未": "癸庚丁（小暑燥土，上半月同午月用癸，下半月用庚丁）",
        "申": "庚丁壬（孟秋金旺，死木用庚劈甲引丁，活木忌金喜水）",
        "酉": "丁庚丙（仲秋金锐，用丁火制杀，丙火调候）",
        "戌": "庚甲丁壬癸（燥土藏火，劈甲引丁，壬癸润燥）",
        "亥": "庚丁丙戊（冬水汪洋，戊土止水，丙火暖局，庚丁劈甲）",
        "子": "丁庚丙（仲冬水寒木冻，首取丙丁火融冰，庚金劈甲引火）",
        "丑": "丁庚丙（隆冬严寒，非丙不暖，非丁不发，庚金助燃）",
    },
    "乙": {
        "寅": "丙癸（春寒花木，最喜丙火太阳照暖，癸水雨露滋润，忌水多困丙）",
        "卯": "丙癸（藤萝繁茂，专用丙火泄秀、癸水润根）",
        "辰": "癸丙戊（暮春土旺，先用癸水滋木，次用丙火晒暖）",
        "巳": "癸（初夏火炎叶枯，专取癸水雨露救燥）",
        "午": "癸丙（仲夏烈日禾稼干枯，首用癸水，丙火配合）",
        "未": "癸丙（三伏生寒，润土滋木全赖癸水）",
        "申": "丙癸己（秋金秉令，乙木柔弱，己土培根，丙火制金，癸水化杀）",
        "酉": "癸丙丁（仲秋桂花，上半月用癸水滋根，下半月用丙火暖局）",
        "戌": "癸辛（秋燥土厚，用癸水润泽，若甲木藤萝系甲则吉）",
        "亥": "丙戊（初冬水旺木浮，专取丙火向阳，戊土制水培木）",
        "子": "丙（寒冬花木冻结，唯一急需丙火太阳解冻，忌癸水冻木）",
        "丑": "丙（腊月寒谷回春，全赖一轮丙火暖局）",
    },
    "丙": {
        "寅": "壬庚（初春火相木旺，用壬水既济映照，庚金发水源）",
        "卯": "壬己（木旺火塞，专用壬水淘洗，己土混水则用甲）",
        "辰": "壬甲（春末土重晦火，用甲木疏土，壬水映日）",
        "巳": "壬庚癸（建禄炎炎，首取壬水七杀制衡，庚金发水源）",
        "午": "壬庚（帝旺烈火，无壬水不贵，无庚金则壬水无源）",
        "未": "壬庚（三伏火退土燥，仍赖壬庚生水润局）",
        "申": "壬戊（秋阳西下，壬水映照，若水太旺则用戊土制水）",
        "酉": "壬癸（日近西山，四柱多丙则用壬，一丙孤立则喜甲木助火）",
        "戌": "甲壬（墓库燥土晦火，最忌土重，先用甲木破土，次取壬水）",
        "亥": "甲戊庚壬（冬月七杀当权，用甲木化杀生身，戊土制水护火）",
        "子": "壬戊己（冬至一阳生，水旺用戊土制水、甲木扶身，火旺仍喜壬）",
        "丑": "壬甲（雪后阳光，土冻晦火，喜甲木疏土生丙，壬水清局）",
    },
    "丁": {
        "寅": "甲庚（初春湿木不燃，用庚金劈甲木，方能引燃丁火）",
        "卯": "庚甲（乙木湿草塞火，以庚去乙、以甲引丁，名劈甲引丁）",
        "辰": "甲庚（伤官当令，木老用庚劈甲助丁）",
        "巳": "甲庚（劫财秉令，火旺仍喜甲庚配合，或壬癸济火）",
        "午": "壬庚癸（建禄火炎，用壬癸水济火，庚金生水，忌火太燥）",
        "未": "甲壬庚（燥土退气，劈甲引丁，兼用壬水润局）",
        "申": "甲庚丙（秋金当权，专取庚金劈甲引丁，灯火辉煌）",
        "酉": "甲庚丙（长生财旺，劈甲引丁为第一要务）",
        "戌": "甲戊庚（伤官墓库，防戌土晦火，必用甲木疏土、庚金劈甲）",
        "亥": "甲庚（冬夜寒灯，官星当令，全赖甲木正印化杀生身、庚金劈甲）",
        "子": "甲庚（七杀寒水，无甲木不能存身，无庚金不能劈甲）",
        "丑": "甲庚（寒冬湿泥晦火，唯赖甲庚劈木引火）",
    },
    "戊": {
        "寅": "丙甲癸（春土虚寒，无丙不暖，无甲不灵，无癸不润，三者俱全大贵）",
        "卯": "丙甲癸（正官当令，先用丙火化官暖土，次用癸水滋润）",
        "辰": "甲丙癸（建禄土厚，首用甲木疏劈，次用丙火暖照、癸水润泽）",
        "巳": "甲丙癸（火炎土燥，先用甲木疏土，急需癸水润燥，丙火酌用）",
        "午": "壬甲丙（仲夏火旺土焦，滴水千金，首取壬水调候，甲木辅佐）",
        "未": "癸丙甲（三伏燥土，急需癸水雨露滋润，甲木疏劈）",
        "申": "丙癸甲（秋气渐凉，食神泄气，用丙火暖局生土，癸水润金）",
        "酉": "丙癸（伤官泄秀，土气虚寒，赖丙火照暖，癸水滋润）",
        "戌": "甲丙癸（九月土旺而燥，首用甲木疏土，次取癸水润燥，忌金多）",
        "亥": "甲丙（冬水寒冻，非甲不灵，非丙不暖，丙甲两透大富贵）",
        "子": "丙甲（严冬冰冻之土，第一急务为丙火解冻，甲木辅丙）",
        "丑": "丙甲（腊月冻土，丙火太阳照暖则万物发生，甲木助火疏土）",
    },
    "己": {
        "寅": "丙庚甲（初春田园余寒，首取丙火暖土，癸水润泽，忌甲木太重）",
        "卯": "甲癸丙（七杀当权，用丙火化杀生身，癸水润土培木）",
        "辰": "丙癸甲（春耕之时，先用丙火阳光，次用癸水雨露，再植甲木禾苗）",
        "巳": "癸丙（初夏田园干涸，首取癸水灌溉，丙火相济）",
        "午": "癸丙（仲夏烈日焦土，无癸水则禾稼枯死，壬癸为急）",
        "未": "癸丙（小暑燥土，急需癸水透干润泽）",
        "申": "丙癸（秋金泄土，用丙火温土制金，癸水润局）",
        "酉": "丙癸（长生食神，用丙火暖局，癸水生财）",
        "戌": "甲丙癸（九月土盛，用甲木疏辟，癸水灌溉，丙火照暖）",
        "亥": "丙甲戊（冬水漫田，用戊土筑堤制水，丙火暖土，甲木疏导）",
        "子": "丙甲戊（严冬冰冻田园，唯赖丙火太阳融冰，戊土帮身制水）",
        "丑": "丙甲戊（湿寒冻泥，全仗丙火暄暖，甲木助火）",
    },
    "庚": {
        "寅": "戊甲壬丙癸（初春木旺金绝，用戊土生身，丙火暖金，丁火锻炼）",
        "卯": "丁甲庚丙（仲春财旺，顽金专喜丁火炉冶锻炼，甲木引丁）",
        "辰": "甲丁壬癸（暮春土旺埋金，首用甲木疏土，次用丁火炼金）",
        "巳": "壬戊丙丁（长生火旺，火炎炼金太过，首取壬水调候制火）",
        "午": "壬癸（仲夏烈火熔金，急需壬癸水救护调候，戊己晦火生金）",
        "未": "丁甲（三伏土旺退火，用丁火锻炼，甲木疏土引丁）",
        "申": "丁甲（建禄顽金当令，古诀“秋金锐锐最为奇，壬癸相逢总不宜”，专取丁火锻炼、甲木引火）",
        "酉": "丁甲丙（羊刃刚金，唯喜丁火炉火锻炼成器，甲木助燃，丙火调候）",
        "戌": "甲壬（燥土厚重恐埋金，先用甲木疏土，次用壬水淘洗）",
        "亥": "丁丙（冬水沉寒，金水伤官喜见官，首取丁火制炼，丙火暖局）",
        "子": "丁甲丙（仲冬水冷金寒，非丁火不造，非丙火不暖，甲木引火）",
        "丑": "丙丁甲（寒泥墓库冻金，先用丙火解冻，次用丁甲锻炼）",
    },
    "辛": {
        "寅": "己壬庚（春月财旺身弱，用己土生金、壬水淘洗珠玉）",
        "卯": "壬甲（二月辛金，最喜壬水淘洗光芒，忌土厚埋金、火旺熔金）",
        "辰": "壬甲（戊土司令恐埋金，先用壬水洗金，甲木疏土）",
        "巳": "壬甲癸（初夏火燥，珠玉最怕炉火烘烤，急用壬癸水降温淘洗）",
        "午": "壬己癸（仲夏火旺熔金，用壬癸水救护，己土湿泥护金生身）",
        "未": "壬庚甲（燥土脆金，先用壬水润土洗金，甲木疏土）",
        "申": "壬甲戊（秋金秉令，金多水浊则用壬水泄秀淘洗，水多则用戊土）",
        "酉": "壬甲（建禄辛金，专取壬水伤官淘洗，光芒万丈，最忌戊己土埋金）",
        "戌": "壬甲（九月燥土厚重，第一用壬水洗土，第二用甲木疏土）",
        "亥": "壬丙（冬月伤官当令，金水清澈，首取丙火照暖，所谓金水伤官喜见官）",
        "子": "丙戊壬甲（冬月寒水冷金，必有丙火暖局，戊土止水，方显富贵）",
        "丑": "丙壬戊己（腊月寒冻湿泥，首取丙火解冻暖局，壬水洗金）",
    },
    "壬": {
        "寅": "庚丙戊（初春水散，用庚金发水源，戊土筑堤，丙火暖照）",
        "卯": "戊辛庚（仲春水泄于木，用戊土止水定向，庚辛金发水源）",
        "辰": "甲庚（七杀墓库土旺，用甲木疏土制杀，庚金发水源）",
        "巳": "壬辛庚癸（初夏水绝财旺，急用庚辛金发水源，壬癸比劫帮身）",
        "午": "癸庚辛（仲夏财官太旺，水弱极，专取庚辛生水、癸水帮身）",
        "未": "辛甲（三伏燥土克水，用辛金发水源，甲木疏土制杀）",
        "申": "戊丁（长生水旺，江河奔流，急需戊土七杀筑堤防洪，丁火合壬化木或财星养杀）",
        "酉": "甲庚（败地清澈，金白水清，用甲木食神泄秀）",
        "戌": "甲丙（九月戊土当权，水入冠带，用甲木制戌土，丙火照暖）",
        "亥": "戊丙庚（建禄汪洋，首取戊土七杀筑堤，丙火太阳照水）",
        "子": "戊丙（羊刃决堤且寒冰冻结，必用丙火解冻、戊土止水，水火既济）",
        "丑": "丙甲丁（腊月冰封，首取丙火融冰解冻，甲木泄秀疏土）",
    },
    "癸": {
        "寅": "辛丙（初春雨露生木泄气，用辛金偏印发水源，丙火暖照）",
        "卯": "庚辛（仲春食神泄秀太过，专取庚辛金生身护源）",
        "辰": "丙辛甲（暮春要防土浊水，用丙火暖局，辛金发源，甲木疏土）",
        "巳": "辛（初夏财官秉令，雨露易干，急用辛金偏印发水源，忌丁火破辛）",
        "午": "庚辛壬癸（仲夏火旺水干，唯赖庚辛金发水源，比劫帮身）",
        "未": "庚辛壬癸（小暑燥土，上半月金神伏火用庚辛壬癸，下半月稍轻）",
        "申": "丁（孟秋金旺生水，死金用丁火制金暖局，名有火有金方成大器）",
        "酉": "辛丙（仲秋偏印当令，金白水清，用辛金纯粹，丙火暖照）",
        "戌": "辛甲壬癸（燥土克水，用辛金发源，甲木疏土，比劫助身）",
        "亥": "庚辛戊丁（冬水旺极反成泛滥，用庚辛得禄，戊土制水，丙丁暖局）",
        "子": "丙辛（建禄冰冻，雨雪严寒，首取丙火解冻暖局，辛金发源）",
        "丑": "丙丁（腊月冰霜冻结，唯赖丙丁火解冻，水暖财丰）",
    }
}

# ==============================================================================
# 3. 真太阳时计算函数（经度差 + 天文均时差 Equation of Time）
# ==============================================================================
def calc_true_solar_time(dt: datetime, lon: float, std_lon: float = 120.0):
    """
    计算真太阳时：
    1. 地理经度差修正：(当地经度 - 标准时区经度120°E) * 4 分钟/度
    2. 天文均时差修正 (Equation of Time, EoT)：地球公转椭圆轨道与黄赤交角引起的真太阳与平太阳时差
    """
    lon_diff_min = (lon - std_lon) * 4.0
    day_of_year = dt.timetuple().tm_yday
    B = math.radians((360.0 / 365.24) * (day_of_year - 81))
    eot_min = 9.87 * math.sin(2 * B) - 7.53 * math.cos(B) - 1.5 * math.sin(B)
    total_diff_sec = (lon_diff_min + eot_min) * 60.0
    tst_dt = dt + timedelta(seconds=total_diff_sec)
    return tst_dt, round(lon_diff_min, 2), round(eot_min, 2), round(lon_diff_min + eot_min, 2)

# ==============================================================================
# 4. 盲派与子平干支关系扫描（天干合冲 + 地支刑冲合害墓库）
# ==============================================================================
def analyze_ganzhi_interactions(gans, zhis):
    """自动扫描四柱原局的天干五合/四冲、地支六冲/六合/三合/相刑/相害/墓库"""
    pillars = ["年", "月", "日", "时"]
    results = {
        "tiangan_he": [],
        "tiangan_chong": [],
        "dizhi_chong": [],
        "dizhi_he": [],
        "dizhi_sanhe": [],
        "dizhi_xing": [],
        "dizhi_hai": [],
        "muku_info": []
    }
    gan_he_pairs = {
        frozenset(["甲", "己"]): "甲己合化土（中正之合）",
        frozenset(["乙", "庚"]): "乙庚合化金（仁义之合）",
        frozenset(["丙", "辛"]): "丙辛合化水（威制之合）",
        frozenset(["丁", "壬"]): "丁壬合化木（淫匿/多情之合）",
        frozenset(["戊", "癸"]): "戊癸合化火（无情/老少之合）",
    }
    gan_chong_pairs = {
        frozenset(["甲", "庚"]): "甲庚相冲（金木交战）",
        frozenset(["乙", "辛"]): "乙辛相冲（金刃伤木）",
        frozenset(["丙", "壬"]): "丙壬相冲（水火激荡）",
        frozenset(["丁", "癸"]): "丁癸相冲（癸水伤丁）",
    }
    zhi_chong_pairs = {
        frozenset(["子", "午"]): "子午相冲（水火相激，主变动、奔波、心神不宁）",
        frozenset(["丑", "未"]): "丑未相冲（湿燥两墓相冲开库，主房产、亲缘或财务震荡）",
        frozenset(["寅", "申"]): "寅申相冲（驿马相冲，主远行、车马、高强变动）",
        frozenset(["卯", "酉"]): "卯酉相冲（桃花门户相冲，主感情变动、环境转换）",
        frozenset(["辰", "戌"]): "辰戌相冲（天罗地网水火两库相冲开库，主大开大合之变）",
        frozenset(["巳", "亥"]): "巳亥相冲（驿马水火相冲，主思虑多变、走动奔波）",
    }
    zhi_he_pairs = {
        frozenset(["子", "丑"]): "子丑六合化土（闭子水入丑库）",
        frozenset(["寅", "亥"]): "寅亥六合化木（合中带破，亥水生寅木灭丙火）",
        frozenset(["卯", "戌"]): "卯戌六合化火（卯木克合戌土闭火库）",
        frozenset(["辰", "酉"]): "辰酉六合化金（辰土生合酉金铲断乙木根）",
        frozenset(["巳", "申"]): "巳申六合化水（合中带刑克，效率与纠结并存）",
        frozenset(["午", "未"]): "午未六合化火/土（燥热相合闭木库）",
    }
    zhi_hai_pairs = {
        frozenset(["子", "未"]): "子未相害（穿害，脾胃或暗中消耗）",
        frozenset(["丑", "午"]): "丑午相害（湿土晦火之穿，急躁与压抑交织）",
        frozenset(["寅", "巳"]): "寅巳相害/相刑（忙碌消耗、恩中生怨）",
        frozenset(["卯", "辰"]): "卯辰相害（木克湿土之穿，内部摩擦）",
        frozenset(["申", "亥"]): "申亥相害（金水相穿，表面相生实则暗耗）",
        frozenset(["酉", "戌"]): "酉戌相害（脆金之穿，情绪敏感或人际内耗）",
    }
    zhi_xing_pairs = {
        frozenset(["子", "卯"]): "子卯无礼之刑（水木相刑，固执、越界或桃色纠葛）",
        frozenset(["寅", "巳"]): "寅巳无恩之刑",
        frozenset(["巳", "申"]): "巳申相刑",
        frozenset(["丑", "戌"]): "丑戌恃势之刑（刑开墓库）",
        frozenset(["戌", "未"]): "戌未恃势之刑（燥土刑开墓库）",
    }
    for i in range(4):
        for j in range(i + 1, 4):
            gp = frozenset([gans[i], gans[j]])
            if gp in gan_he_pairs:
                results["tiangan_he"].append(f"{pillars[i]}干{gans[i]}与{pillars[j]}干{gans[j]}：{gan_he_pairs[gp]}")
            if gp in gan_chong_pairs:
                results["tiangan_chong"].append(f"{pillars[i]}干{gans[i]}与{pillars[j]}干{gans[j]}：{gan_chong_pairs[gp]}")
            zp = frozenset([zhis[i], zhis[j]])
            if zp in zhi_chong_pairs:
                results["dizhi_chong"].append(f"{pillars[i]}支{zhis[i]}与{pillars[j]}支{zhis[j]}：{zhi_chong_pairs[zp]}")
            if zp in zhi_he_pairs:
                results["dizhi_he"].append(f"{pillars[i]}支{zhis[i]}与{pillars[j]}支{zhis[j]}：{zhi_he_pairs[zp]}")
            if zp in zhi_hai_pairs:
                results["dizhi_hai"].append(f"{pillars[i]}支{zhis[i]}与{pillars[j]}支{zhis[j]}：{zhi_hai_pairs[zp]}")
            if zp in zhi_xing_pairs:
                results["dizhi_xing"].append(f"{pillars[i]}支{zhis[i]}与{pillars[j]}支{zhis[j]}：{zhi_xing_pairs[zp]}")
            if zhis[i] == zhis[j] and zhis[i] in ["辰", "午", "酉", "亥"]:
                results["dizhi_xing"].append(f"{pillars[i]}支{zhis[i]}与{pillars[j]}支{zhis[j]}：{zhis[i]}{zhis[j]}自刑（容易自我纠结、钻牛角尖）")

    # 三合局检测
    zhi_set = set(zhis)
    sanhe_defs = [
        ({"申", "子", "辰"}, "申子辰三合水局"),
        ({"亥", "卯", "未"}, "亥卯未三合木局"),
        ({"寅", "午", "戌"}, "寅午戌三合火局"),
        ({"巳", "酉", "丑"}, "巳酉丑三合金局"),
    ]
    for s, desc in sanhe_defs:
        if s.issubset(zhi_set):
            results["dizhi_sanhe"].append(desc)

    # 盲派四墓库（辰戌丑未）扫描
    muku_desc = {
        "辰": "辰（水土之库/湿土，春末草木余气）",
        "戌": "戌（火库/燥土，藏丁火辛金戊土）",
        "丑": "丑（金库/湿寒之土，藏己土癸水辛金）",
        "未": "未（木库/温燥之土，藏己土丁火乙木）",
    }
    for idx, z in enumerate(zhis):
        if z in muku_desc:
            is_open = any(z in item for item in results["dizhi_chong"] + results["dizhi_xing"])
            status = "【原局已被刑冲打开，库中能量已被激活做功】" if is_open else "【原局闭库待冲，逢大运流年刑冲之时突发大象】"
            results["muku_info"].append(f"{pillars[idx]}支见{muku_desc[z]} -> {status}")

    return results

# ==============================================================================
# 5. 子平八字 + 盲派 + 穷通宝鉴 排盘主函数
# ==============================================================================
def run_bazi(args):
    if args.date:
        parts = args.date.split("-")
        args.year, args.month, args.day = int(parts[0]), int(parts[1]), int(parts[2])
    if args.time:
        tparts = args.time.split(":")
        args.hour = int(tparts[0])
        args.minute = int(tparts[1]) if len(tparts) > 1 else 0
    if args.year is None or args.month is None or args.day is None:
        raise ValueError("必须提供 --year/--month/--day 或 --date YYYY-MM-DD")

    lon = args.lon
    if lon is None:
        lon, city_name = resolve_city_longitude(args.city)
    else:
        city_name = args.city or f"自定义经度({lon}°E)"

    raw_dt = datetime(args.year, args.month, args.day, args.hour, args.minute, 0)
    if args.lunar:
        lunar_in = Lunar.fromYmdHms(args.year, -args.month if args.leap else args.month, args.day, args.hour, args.minute, 0)
        solar_in = lunar_in.getSolar()
        raw_dt = datetime(solar_in.getYear(), solar_in.getMonth(), solar_in.getDay(), solar_in.getHour(), solar_in.getMinute(), 0)

    tst_dt, lon_diff, eot_diff, total_diff = calc_true_solar_time(raw_dt, lon)
    use_dt = tst_dt if not args.no_tst else raw_dt

    solar = Solar.fromYmdHms(use_dt.year, use_dt.month, use_dt.day, use_dt.hour, use_dt.minute, use_dt.second)
    lunar = solar.getLunar()
    bazi = lunar.getEightChar()
    bazi.setSect(args.sect)  # 2: 晚子时日柱算当天(正统子平推荐); 1: 晚子时日柱算次日

    gans = [bazi.getYearGan(), bazi.getMonthGan(), bazi.getDayGan(), bazi.getTimeGan()]
    zhis = [bazi.getYearZhi(), bazi.getMonthZhi(), bazi.getDayZhi(), bazi.getTimeZhi()]
    day_gan = bazi.getDayGan()
    month_zhi = bazi.getMonthZhi()

    # 五行计数（含天干与地支本气）
    wx_count = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for g in gans:
        wx_count[GAN_WUXING[g]] += 1
    for z in zhis:
        wx_count[ZHI_WUXING[z]] += 1

    # 节气交接信息
    prev_jq = lunar.getPrevJie()
    next_jq = lunar.getNextJie()

    # 大运流年
    gender_code = 1 if args.gender in ["男", "M", "male", "1", "乾造"] else 0
    yun = bazi.getYun(gender_code)
    dayun_list = []
    for dy in yun.getDaYun()[1:9]:
        ln_items = []
        for ln in dy.getLiuNian():
            if 2020 <= ln.getYear() <= 2030:
                ln_items.append(f"{ln.getYear()}({ln.getGanZhi()}/{ln.getAge()}岁)")
        dayun_list.append({
            "step": f"{dy.getStartAge()}-{dy.getEndAge()}岁",
            "start_year": dy.getStartYear(),
            "ganzhi": dy.getGanZhi(),
            "recent_liunian": ln_items
        })

    interactions = analyze_ganzhi_interactions(gans, zhis)
    tiaohou = QIONGTONG_TIAOHOU.get(day_gan, {}).get(month_zhi, "需结合全局寒暖燥湿综合取用")

    output = {
        "meta": {
            "engine": "东方玄学宗师 · 毫秒级天文真太阳时八字引擎 v1.0",
            "gender": "乾造（男）" if gender_code == 1 else "坤造（女）",
            "input_clock_time": raw_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "city": city_name,
            "longitude": lon,
            "true_solar_time": tst_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "time_correction_detail": f"经度差 {lon_diff:+.2f} 分钟 + 均时差(EoT) {eot_diff:+.2f} 分钟 = 总计 {total_diff:+.2f} 分钟",
            "lunar_date": str(lunar),
            "prev_jieqi": f"{prev_jq.getName()} ({prev_jq.getSolar().toYmdHms()})",
            "next_jieqi": f"{next_jq.getName()} ({next_jq.getSolar().toYmdHms()})",
        },
        "four_pillars": {
            "year": {
                "pillar": bazi.getYear(), "gan": gans[0], "zhi": zhis[0],
                "shishen_gan": bazi.getYearShiShenGan(), "hide_gan": bazi.getYearHideGan(),
                "shishen_zhi": bazi.getYearShiShenZhi(), "nayin": bazi.getYearNaYin(),
                "dishi": bazi.getYearDiShi(), "xunkong": bazi.getYearXunKong(),
                "palace_meaning": "年柱（宾位/根基宫：祖上、原生家庭背景、1-18岁早年运势、大环境外缘）"
            },
            "month": {
                "pillar": bazi.getMonth(), "gan": gans[1], "zhi": zhis[1],
                "shishen_gan": bazi.getMonthShiShenGan(), "hide_gan": bazi.getMonthHideGan(),
                "shishen_zhi": bazi.getMonthShiShenZhi(), "nayin": bazi.getMonthNaYin(),
                "dishi": bazi.getMonthDiShi(), "xunkong": bazi.getMonthXunKong(),
                "palace_meaning": "月柱（提纲/父母兄弟/事业宫：社会立足点、19-35岁青年核心赛道、性格外显）"
            },
            "day": {
                "pillar": bazi.getDay(), "gan": gans[2], "zhi": zhis[2],
                "shishen_gan": "日主(日元)", "hide_gan": bazi.getDayHideGan(),
                "shishen_zhi": bazi.getDayShiShenZhi(), "nayin": bazi.getDayNaYin(),
                "dishi": bazi.getDayDiShi(), "xunkong": bazi.getDayXunKong(),
                "palace_meaning": "日柱（主位核心：日干为我，日支为夫妻宫/内心隐秘花园/36-50岁中年根基）"
            },
            "time": {
                "pillar": bazi.getTime(), "gan": gans[3], "zhi": zhis[3],
                "shishen_gan": bazi.getTimeShiShenGan(), "hide_gan": bazi.getTimeHideGan(),
                "shishen_zhi": bazi.getTimeShiShenZhi(), "nayin": bazi.getTimeNaYin(),
                "dishi": bazi.getTimeDiShi(), "xunkong": bazi.getTimeXunKong(),
                "palace_meaning": "时柱（主位门户/子女晚年宫：最终事业归宿、副业投资、50岁后晚年状态）"
            }
        },
        "extra_palaces": {
            "tai_yuan": f"{bazi.getTaiYuan()} ({bazi.getTaiYuanNaYin()})",
            "ming_gong": f"{bazi.getMingGong()} ({bazi.getMingGongNaYin()})",
            "shen_gong": f"{bazi.getShenGong()} ({bazi.getShenGongNaYin()})",
        },
        "wuxing_summary": {
            "day_master": f"{day_gan}{GAN_WUXING[day_gan]}（{GAN_YINYANG[day_gan]}{GAN_WUXING[day_gan]}）",
            "month_command": f"生于{month_zhi}月（{ZHI_WUXING[month_zhi]}当令）",
            "surface_counts": wx_count,
            "qiongtong_tiaohou": f"《穷通宝鉴》{day_gan}日{month_zhi}月调候用神：{tiaohou}"
        },
        "mangpai_interactions": interactions,
        "dayun_info": {
            "qiyun_detail": f"出生后 {yun.getStartYear()} 年 {yun.getStartMonth()} 个月 {yun.getStartDay()} 天起运（公历 {yun.getStartSolar().toYmd()} 交大运）",
            "dayun_list": dayun_list
        }
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

# ==============================================================================
# 6. 道家小六壬（《玉匣记》马前课三宫掌诀）排盘引擎
# ==============================================================================
XIAOLIUREN_PALACES = [
    {
        "name": "大安", "wuxing": "木", "direction": "正东方", "god": "青龙", "numbers": "1、5、7",
        "verse": "大安事事昌，求财在坤方，失物去不远，宅舍保安康；行人身未动，病者主无妨，将军回田野，仔细更推详。",
        "core_meaning": "静止、安稳、缓慢、守成、正职、不吉不凶偏安稳。问事主慢、求稳可得，失物在原地或家中近处，感情稳定但缺乏波澜。"
    },
    {
        "name": "留连", "wuxing": "水（兼湿土暗昧）", "direction": "北方/四方隅", "god": "玄武", "numbers": "2、8、10",
        "verse": "留连事难成，求谋日未明，官事凡宜缓，去者未回程；失物南方见，急讨方心称，更须防口舌，人口且平平。",
        "core_meaning": "拖延、纠缠、暧昧、卡壳、反复拉扯。求财慢且易被压款，感情藕断丝连放不下，工作推进受阻，宜缓不宜急。"
    },
    {
        "name": "速喜", "wuxing": "火", "direction": "正南方", "god": "朱雀", "numbers": "3、6、9",
        "verse": "速喜喜来临，求财向南行，失物申未午，逢人路上寻；官事有福德，病者无祸侵，田宅六畜吉，行人有信音。",
        "core_meaning": "迅速、喜讯、突发转机、文书信息、快钱热度。问消息马上到，感情主热情升温但需防三分钟热度，合作主短期迅速拍板。"
    },
    {
        "name": "赤口", "wuxing": "金", "direction": "正西方", "god": "白虎", "numbers": "4、7、10",
        "verse": "赤口主口舌，官非切宜防，失物速寻觅，行人有惊慌；六畜多作怪，病者出西方，更须防咀咒，诚恐染瘟皇。",
        "core_meaning": "争执、口舌是非、金属利器、急躁冲突、谈判交锋。感情主吵架冷战，合作防合同纠纷，失物急找否则难回。"
    },
    {
        "name": "小吉", "wuxing": "水（活水生木）", "direction": "正北方/西南", "god": "六合", "numbers": "1、5、7",
        "verse": "小吉最吉昌，路上好商量，阴人来报喜，失物在坤方；行人即便至，交关甚是强，凡事皆和合，病者叩穹苍。",
        "core_meaning": "贵人相助（尤指女性贵人）、人脉撮合、交易顺畅、小步快跑之吉。求财得偏财与人脉之利，感情和合融洽，合作大吉。"
    },
    {
        "name": "空亡", "wuxing": "土（燥土归空）", "direction": "中央", "god": "勾陈", "numbers": "3、6、9",
        "verse": "空亡事不祥，阴人多乖张，求财无利益，行人有灾殃；失物寻不见，官事有刑伤，病人逢暗鬼，解禳保安康。",
        "core_meaning": "落空、白忙一场、虚假画饼、无果而终（若问玄学修行/虚拟创意反主灵感）。求财竹篮打水，感情有名无实或心里没底，失物难寻。"
    }
]

def run_xiaoliuren(args):
    if args.nums and len(args.nums) == 3:
        n1, n2, n3 = args.nums
        mode_desc = f"报三数起课：{n1}、{n2}、{n3}"
    else:
        now = datetime.now()
        solar = Solar.fromYmdHms(now.year, now.month, now.day, now.hour, now.minute, now.second)
        lunar = solar.getLunar()
        n1 = abs(lunar.getMonth())
        n2 = lunar.getDay()
        zhi_idx = ZHI_LIST.index(lunar.getTimeZhi()) + 1
        n3 = zhi_idx
        mode_desc = f"农历时间起课：{n1}月 {n2}日 {lunar.getTimeZhi()}时(第{n3}时辰)"

    idx1 = (n1 - 1) % 6
    idx2 = (idx1 + n2 - 1) % 6
    idx3 = (idx2 + n3 - 1) % 6

    p1 = XIAOLIUREN_PALACES[idx1]
    p2 = XIAOLIUREN_PALACES[idx2]
    p3 = XIAOLIUREN_PALACES[idx3]

    output = {
        "meta": {
            "engine": "道家小六壬 · 《玉匣记》三宫掌诀推演引擎 v1.0",
            "mode": mode_desc,
            "question": args.question or "综合吉凶占断"
        },
        "three_palaces": {
            "1_ren_gong_qi_yin": {"stage": "第一宫（人宫/初传：事情起因与你当下的状态）", **p1},
            "2_shi_gong_guo_cheng": {"stage": "第二宫（事宫/中传：事情中段演变、阻碍或助力）", **p2},
            "3_ying_gong_jie_ju": {"stage": "第三宫（应宫/末传：最终结局定音，权重占60%）", **p3},
        },
        "synthesis_trajectory": f"【起承转合全息轨迹】由「{p1['name']}」起步 -> 历经「{p2['name']}」之演变 -> 终落「{p3['name']}」定局。"
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

# ==============================================================================
# 7. 《周易》六十四卦 · 梅花易数起卦装卦引擎
# ==============================================================================
BAGUA = {
    1: {"name": "乾", "symbol": "☰", "nature": "天", "wuxing": "金", "lines": [1, 1, 1], "Trait": "刚健、领导、开创、父亲/上级、西北"},
    2: {"name": "兑", "symbol": "☱", "nature": "泽", "wuxing": "金", "lines": [1, 1, 0], "Trait": "喜悦、口才、缺口、少女/沟通、正西"},
    3: {"name": "离", "symbol": "☲", "nature": "火", "wuxing": "火", "lines": [1, 0, 1], "Trait": "光明、美丽、文书、中女/互联网、正南"},
    4: {"name": "震", "symbol": "☳", "nature": "雷", "wuxing": "木", "lines": [1, 0, 0], "Trait": "震动、迅速、雷厉风行、长男/新启动、正东"},
    5: {"name": "巽", "symbol": "☴", "nature": "风", "wuxing": "木", "lines": [0, 1, 1], "Trait": "渗透、传播、犹豫不决、长女/商贸利市、东南"},
    6: {"name": "坎", "symbol": "☵", "nature": "水", "wuxing": "水", "lines": [0, 1, 0], "Trait": "险陷、智慧、隐伏波折、中男/现金流、正北"},
    7: {"name": "艮", "symbol": "☶", "nature": "山", "wuxing": "土", "lines": [0, 0, 1], "Trait": "静止、阻隔、稳重守成、少男/不动产、东北"},
    8: {"name": "坤", "symbol": "☷", "nature": "地", "wuxing": "土", "lines": [0, 0, 0], "Trait": "包容、柔顺、厚载慢热、母亲/大众市场、西南"},
}

LINES_TO_GUA = {tuple(v["lines"]): k for k, v in BAGUA.items()}

HEXAGRAM_64_NAMES = {
    (1,1):"乾为天",(1,2):"天泽履",(1,3):"天火同人",(1,4):"天雷无妄",(1,5):"天风姤",(1,6):"天水讼",(1,7):"天山遁",(1,8):"天地否",
    (2,1):"泽天夬",(2,2):"兑为泽",(2,3):"泽火革",(2,4):"泽雷随",(2,5):"泽风大过",(2,6):"泽水困",(2,7):"泽山咸",(2,8):"泽地萃",
    (3,1):"火天大有",(3,2):"火泽睽",(3,3):"离为火",(3,4):"火雷噬嗑",(3,5):"火风鼎",(3,6):"火水未济",(3,7):"火山旅",(3,8):"火地晋",
    (4,1):"雷天大壮",(4,2):"雷泽归妹",(4,3):"雷火丰",(4,4):"震为雷",(4,5):"雷风恒",(4,6):"雷水解",(4,7):"雷山小过",(4,8):"雷地豫",
    (5,1):"风天小畜",(5,2):"风泽中孚",(5,3):"风火家人",(5,4):"风雷益",(5,5):"巽为风",(5,6):"风水涣",(5,7):"风山渐",(5,8):"风地观",
    (6,1):"水天需",(6,2):"水泽节",(6,3):"水火既济",(6,4):"水雷屯",(6,5):"水风井",(6,6):"坎为水",(6,7):"水山蹇",(6,8):"水地比",
    (7,1):"山天大畜",(7,2):"山泽损",(7,3):"山火贲",(7,4):"山雷颐",(7,5):"山风蛊",(7,6):"山水蒙",(7,7):"艮为山",(7,8):"山地剥",
    (8,1):"地天泰",(8,2):"地泽临",(8,3):"地火明夷",(8,4):"地雷复",(8,5):"地风升",(8,6):"地水师",(8,7):"地山谦",(8,8):"坤为地",
}

def judge_tiyong_relation(ti_wx, yong_wx):
    sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    ke = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    if ti_wx == yong_wx:
        return "【体用比和（大吉）】内外同心，顺水推舟，合作、求财、感情皆易达成共识。"
    elif sheng[yong_wx] == ti_wx:
        return f"【用生体（大吉：{yong_wx}生{ti_wx}）】外境主动滋养于你，事半功倍，有贵人或资源送上门。"
    elif ke[ti_wx] == yong_wx:
        return f"【体克用（中吉：{ti_wx}克{yong_wx}）】你完全能掌控局面，但需主动出击、费一番心力方能拿下结果。"
    elif sheng[ti_wx] == yong_wx:
        return f"【体生用（泄气小凶：{ti_wx}生{yong_wx}）】你对这件事或这个人付出过多、精力与钱财外泄，回报慢，防内耗。"
    else:
        return f"【用克体（大凶受制：{yong_wx}克{ti_wx}）】外界阻力极大，环境或对方压制于你，强行推进易碰壁受损，宜守不宜攻。"

def run_meihua(args):
    now = datetime.now()
    solar = Solar.fromYmdHms(now.year, now.month, now.day, now.hour, now.minute, now.second)
    lunar = solar.getLunar()
    zhi_idx = ZHI_LIST.index(lunar.getTimeZhi()) + 1

    if args.nums and len(args.nums) >= 2:
        n1, n2 = args.nums[0], args.nums[1]
        n3 = args.nums[2] if len(args.nums) >= 3 else (n1 + n2 + zhi_idx)
        mode_desc = f"报数起卦：上卦数={n1}，下卦数={n2}，动爻基数={n3}"
    else:
        y_idx = ZHI_LIST.index(lunar.getYearZhi()) + 1
        m_num = abs(lunar.getMonth())
        d_num = lunar.getDay()
        n1 = y_idx + m_num + d_num
        n2 = n1 + zhi_idx
        n3 = n2
        mode_desc = f"年月日时起卦：{lunar.getYearZhi()}年({y_idx}) + {m_num}月 + {d_num}日 + {lunar.getTimeZhi()}时({zhi_idx})"

    up_idx = n1 % 8 or 8
    down_idx = n2 % 8 or 8
    dong_yao = n3 % 6 or 6  # 1..6 (自下而上：初爻为1，上爻为6)

    up_gua = BAGUA[up_idx]
    down_gua = BAGUA[down_idx]
    six_lines = down_gua["lines"] + up_gua["lines"]  # index 0..5 corresponds to 爻 1..6

    # 互卦（2,3,4爻为下互；3,4,5爻为上互）
    hu_down_idx = LINES_TO_GUA[tuple(six_lines[1:4])]
    hu_up_idx = LINES_TO_GUA[tuple(six_lines[2:5])]

    # 变卦（翻转第 dong_yao 爻）
    bian_lines = list(six_lines)
    bian_lines[dong_yao - 1] = 1 - bian_lines[dong_yao - 1]
    bian_down_idx = LINES_TO_GUA[tuple(bian_lines[0:3])]
    bian_up_idx = LINES_TO_GUA[tuple(bian_lines[3:6])]

    # 体用划分：动爻在下卦(1-3)，则上卦为体、下卦为用；动爻在上卦(4-6)，则下卦为体、上卦为用
    if dong_yao <= 3:
        ti_gua, yong_gua, bian_yong_gua = up_gua, down_gua, BAGUA[bian_down_idx]
        ti_pos = "上卦为体（自己），下卦为用（所问之事/外境）"
    else:
        ti_gua, yong_gua, bian_yong_gua = down_gua, up_gua, BAGUA[bian_up_idx]
        ti_pos = "下卦为体（自己），上卦为用（所问之事/外境）"

    output = {
        "meta": {
            "engine": "《周易》六十四卦 · 梅花易数体用推演引擎 v1.0",
            "mode": mode_desc,
            "question": args.question or "《周易》占事决疑"
        },
        "hexagrams": {
            "ben_gua": {
                "name": HEXAGRAM_64_NAMES[(up_idx, down_idx)],
                "upper": f"{up_gua['name']}({up_gua['nature']}/{up_gua['wuxing']})",
                "lower": f"{down_gua['name']}({down_gua['nature']}/{down_gua['wuxing']})",
                "meaning": "【本卦·当下现状】反映事情起始的真实底牌与当前处境"
            },
            "hu_gua": {
                "name": HEXAGRAM_64_NAMES[(hu_up_idx, hu_down_idx)],
                "upper": f"{BAGUA[hu_up_idx]['name']}({BAGUA[hu_up_idx]['wuxing']})",
                "lower": f"{BAGUA[hu_down_idx]['name']}({BAGUA[hu_down_idx]['wuxing']})",
                "meaning": "【互卦·中间暗流】反映事情推进过程中的隐秘变量与内部纠葛"
            },
            "bian_gua": {
                "name": HEXAGRAM_64_NAMES[(bian_up_idx, bian_down_idx)],
                "upper": f"{BAGUA[bian_up_idx]['name']}({BAGUA[bian_up_idx]['wuxing']})",
                "lower": f"{BAGUA[bian_down_idx]['name']}({BAGUA[bian_down_idx]['wuxing']})",
                "meaning": "【变卦·最终结局】动爻触发后的事态最终走向"
            },
            "dong_yao": f"第 {dong_yao} 爻发动"
        },
        "ti_yong_analysis": {
            "position": ti_pos,
            "ti_gua": f"体卦：{ti_gua['name']}卦（五行属{ti_gua['wuxing']}，象义：{ti_gua['Trait']}）",
            "yong_gua": f"用卦：{yong_gua['name']}卦（五行属{yong_gua['wuxing']}，象义：{yong_gua['Trait']}）",
            "initial_relation": judge_tiyong_relation(ti_gua["wuxing"], yong_gua["wuxing"]),
            "final_relation": judge_tiyong_relation(ti_gua["wuxing"], bian_yong_gua["wuxing"])
        }
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

# ==============================================================================
# 8. 紫微斗数十二宫与十四主星/生年四化核心排盘引擎
# ==============================================================================
SIHUA_TABLE = {
    "甲": {"禄": "廉贞", "权": "破军", "科": "武曲", "忌": "太阳"},
    "乙": {"禄": "天机", "权": "天梁", "科": "紫微", "忌": "太阴"},
    "丙": {"禄": "天同", "权": "天机", "科": "文昌", "忌": "廉贞"},
    "丁": {"禄": "太阴", "权": "天同", "科": "天机", "忌": "巨门"},
    "戊": {"禄": "贪狼", "权": "太阴", "科": "右弼", "忌": "天机"},
    "己": {"禄": "武曲", "权": "贪狼", "科": "天梁", "忌": "文曲"},
    "庚": {"禄": "太阳", "权": "武曲", "科": "太阴", "忌": "天同"},
    "辛": {"禄": "巨门", "权": "太阳", "科": "文曲", "忌": "文昌"},
    "壬": {"禄": "天梁", "权": "紫微", "科": "左辅", "忌": "武曲"},
    "癸": {"禄": "破军", "权": "巨门", "科": "太阴", "忌": "贪狼"},
}

PALACE_12_NAMES = ["命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫", "迁移宫", "交友(仆役)宫", "官禄(事业)宫", "田宅宫", "福德宫", "父母宫"]

def run_ziwei(args):
    if getattr(args, "date", None):
        parts = args.date.split("-")
        args.year, args.month, args.day = int(parts[0]), int(parts[1]), int(parts[2])
    if getattr(args, "time", None):
        tparts = args.time.split(":")
        args.hour = int(tparts[0])
        args.minute = int(tparts[1]) if len(tparts) > 1 else 0
    solar = Solar.fromYmdHms(args.year, args.month, args.day, args.hour, args.minute, 0)
    lunar = solar.getLunar()
    if args.lunar:
        lunar = Lunar.fromYmdHms(args.year, args.month, args.day, args.hour, args.minute, 0)
    m_num = abs(lunar.getMonth())
    d_num = lunar.getDay()
    time_zhi = lunar.getTimeZhi()
    t_idx = ZHI_LIST.index(time_zhi)  # 子=0 .. 亥=11
    year_gan = lunar.getYearGan()

    # 寅宫为2: 命宫自寅宫起正月顺数至生月，再逆数生时；身宫自寅宫起正月顺数至生月，再顺数生时
    ming_zhi_idx = (2 + (m_num - 1) - t_idx) % 12
    shen_zhi_idx = (2 + (m_num - 1) + t_idx) % 12

    # 五虎遁定十二宫天干（寅宫起干）
    wuhu_start = {"甲": 2, "己": 2, "乙": 4, "庚": 4, "丙": 6, "辛": 6, "丁": 8, "壬": 8, "戊": 0, "癸": 0}[year_gan]
    palace_ganzhi = {}
    for z_i in range(12):
        offset_from_yin = (z_i - 2) % 12
        g_i = (wuhu_start + offset_from_yin) % 10
        palace_ganzhi[z_i] = GAN_LIST[g_i] + ZHI_LIST[z_i]

    # 命宫纳音定五行局
    ming_gz = palace_ganzhi[ming_zhi_idx]
    nayin_wx_map = {
        "水": ("水二局", 2), "木": ("木三局", 3), "金": ("金四局", 4), "土": ("土五局", 5), "火": ("火六局", 6)
    }
    # 利用 lunar_python 的纳音表或简明甲子纳音五行法则计算命宫五行局
    jiazi_60 = [GAN_LIST[i % 10] + ZHI_LIST[i % 12] for i in range(60)]
    nayin_wx_cycle = ["金", "火", "木", "土", "金", "火", "水", "土", "金", "木", "水", "土", "火", "木", "水",
                      "金", "火", "木", "土", "金", "火", "水", "土", "金", "木", "水", "土", "火", "木", "水"]
    ny_wx = nayin_wx_cycle[jiazi_60.index(ming_gz) // 2]
    ju_name, ju_num = nayin_wx_map[ny_wx]

    # 起紫微星诀（三合派正统安紫微星法）
    q, r = divmod(d_num, ju_num)
    if r == 0:
        zw_offset = q - 1
    else:
        add_x = ju_num - r
        new_q = (d_num + add_x) // ju_num
        if add_x % 2 == 1:
            zw_offset = new_q - 1 - add_x
        else:
            zw_offset = new_q - 1 + add_x
    ziwei_zhi_idx = (2 + zw_offset) % 12
    tianfu_zhi_idx = (4 - ziwei_zhi_idx) % 12  # 寅申斜对安天府

    stars_in_zhi = {i: [] for i in range(12)}
    # 紫微星系逆行：紫微(0)、天机(-1)、空(-2)、太阳(-3)、武曲(-4)、天同(-5)、空(-6,-7)、廉贞(-8)
    zw_series = [(0, "紫微"), (-1, "天机"), (-3, "太阳"), (-4, "武曲"), (-5, "天同"), (-8, "廉贞")]
    for off, sname in zw_series:
        stars_in_zhi[(ziwei_zhi_idx + off) % 12].append(sname)

    # 天府星系顺行：天府(0)、太阴(+1)、贪狼(+2)、巨门(+3)、天相(+4)、天梁(+5)、七杀(+6)、破军(+10)
    tf_series = [(0, "天府"), (1, "太阴"), (2, "贪狼"), (3, "巨门"), (4, "天相"), (5, "天梁"), (6, "七杀"), (10, "破军")]
    for off, sname in tf_series:
        stars_in_zhi[(tianfu_zhi_idx + off) % 12].append(sname)

    # 辅星安星（六吉星、六煞星、禄存、天马、红鸾、天喜）
    minor_in_zhi = {i: [] for i in range(12)}
    # 1. 左辅(辰宫4顺数生月)、右弼(戌宫10逆数生月)
    minor_in_zhi[(4 + (m_num - 1)) % 12].append("左辅")
    minor_in_zhi[(10 - (m_num - 1)) % 12].append("右弼")
    # 2. 文昌(戌宫10逆数生时)、文曲(辰宫4顺数生时)
    minor_in_zhi[(10 - t_idx) % 12].append("文昌")
    minor_in_zhi[(4 + t_idx) % 12].append("文曲")
    # 3. 天魁、天钺（依生年天干）
    kui_yue_map = {
        "甲": (1, 7), "戊": (1, 7), "庚": (1, 7),
        "乙": (0, 8), "己": (0, 8),
        "丙": (11, 9), "丁": (11, 9),
        "壬": (3, 5), "癸": (3, 5),
        "辛": (6, 2)
    }
    kui_z, yue_z = kui_yue_map[year_gan]
    minor_in_zhi[kui_z].append("天魁")
    minor_in_zhi[yue_z].append("天钺")
    # 4. 禄存、擎羊、陀罗（依生年天干）
    lucun_map = {"甲": 2, "乙": 3, "丙": 5, "戊": 5, "丁": 6, "己": 6, "庚": 8, "辛": 9, "壬": 11, "癸": 0}
    lc_z = lucun_map[year_gan]
    minor_in_zhi[lc_z].append("禄存")
    minor_in_zhi[(lc_z + 1) % 12].append("擎羊")
    minor_in_zhi[(lc_z - 1) % 12].append("陀罗")
    # 5. 地空(亥11逆数生时)、地劫(亥11顺数生时)
    minor_in_zhi[(11 - t_idx) % 12].append("地空")
    minor_in_zhi[(11 + t_idx) % 12].append("地劫")
    # 6. 火星、铃星（依生年地支与生时）
    year_zhi = lunar.getYearZhi()
    yz_idx = ZHI_LIST.index(year_zhi)
    if year_zhi in ("寅", "午", "戌"):
        huo_start, ling_start = 1, 3
    elif year_zhi in ("申", "子", "辰"):
        huo_start, ling_start = 2, 10
    elif year_zhi in ("巳", "酉", "丑"):
        huo_start, ling_start = 3, 10
    else:
        huo_start, ling_start = 9, 10
    minor_in_zhi[(huo_start + t_idx) % 12].append("火星")
    minor_in_zhi[(ling_start + t_idx) % 12].append("铃星")
    # 7. 红鸾(卯3逆数生年支)、天喜(红鸾对宫)、天马
    hongluan_z = (3 - yz_idx) % 12
    tianxi_z = (hongluan_z + 6) % 12
    minor_in_zhi[hongluan_z].append("红鸾(正缘桃花)")
    minor_in_zhi[tianxi_z].append("天喜(喜庆桃花)")
    tianma_map = {"寅": 8, "午": 8, "戌": 8, "申": 2, "子": 2, "辰": 2, "巳": 11, "酉": 11, "丑": 11, "亥": 5, "卯": 5, "未": 5}
    minor_in_zhi[tianma_map[year_zhi]].append("天马")

    sihua = SIHUA_TABLE[year_gan]
    inv_sihua = {v: k for k, v in sihua.items()}

    # 十年大限顺逆：阳男阴女顺行，阴男阳女逆行
    is_yang_year = (GAN_YINYANG[year_gan] == "阳")
    is_male = (getattr(args, "gender", "女") in ("男", "M", "male", "1", "乾造"))
    daxian_forward = (is_yang_year and is_male) or ((not is_yang_year) and (not is_male))

    palaces_out = {}
    for p_i, pname in enumerate(PALACE_12_NAMES):
        z_i = (ming_zhi_idx - p_i) % 12
        st_list = []
        for s in stars_in_zhi[z_i]:
            if s in inv_sihua:
                st_list.append(f"{s}[生年化{inv_sihua[s]}]")
            else:
                st_list.append(s)
        m_list = []
        for ms in minor_in_zhi[z_i]:
            base_ms = ms.split("(")[0]
            if base_ms in inv_sihua:
                m_list.append(f"{ms}[生年化{inv_sihua[base_ms]}]")
            else:
                m_list.append(ms)
        # 计算该宫位对应的十年大限年龄区间
        dx_step = (-p_i) % 12 if daxian_forward else p_i % 12
        dx_start = ju_num + dx_step * 10
        dx_end = dx_start + 9
        tag = "（★身宫同宫）" if z_i == shen_zhi_idx else ""
        palaces_out[pname] = {
            "ganzhi": palace_ganzhi[z_i],
            "daxian_age": f"{dx_start}-{dx_end}岁大限",
            "major_stars": st_list if st_list else ["（命无主星，借对宫主星参看）"],
            "minor_stars": m_list,
            "note": tag
        }

    output = {
        "meta": {
            "engine": "紫微斗数 · 三合四化十二宫安星引擎 v2.0（含六吉六煞桃花与十年大限）",
            "lunar_birth": str(lunar),
            "year_gan": year_gan,
            "wuxing_ju": ju_name,
            "ming_gong_zhi": ZHI_LIST[ming_zhi_idx],
            "shen_gong_zhi": ZHI_LIST[shen_zhi_idx],
            "sheng_nian_si_hua": sihua
        },
        "twelve_palaces": palaces_out
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

# ==============================================================================
# 9. 双人八字合盘引擎（婚恋正缘 / 前任纠缠 / 事业合伙交叉比对）
# ==============================================================================
def _quick_bazi_pillars(date_str: str, time_str: str, city_str: str, no_time: bool = False):
    y, m, d = [int(x) for x in date_str.split("-")]
    tp = time_str.split(":")
    hh, mm = int(tp[0]), (int(tp[1]) if len(tp) > 1 else 0)
    lon, cname = resolve_city_longitude(city_str)
    raw_dt = datetime(y, m, d, hh, mm, 0)
    tst_dt, _, _, total_diff = calc_true_solar_time(raw_dt, lon)
    solar = Solar.fromYmdHms(tst_dt.year, tst_dt.month, tst_dt.day, tst_dt.hour, tst_dt.minute, tst_dt.second)
    lunar = solar.getLunar()
    bz = lunar.getEightChar()
    bz.setSect(2)
    pillars = [bz.getYear(), bz.getMonth(), bz.getDay()]
    gans = [bz.getYearGan(), bz.getMonthGan(), bz.getDayGan()]
    zhis = [bz.getYearZhi(), bz.getMonthZhi(), bz.getDayZhi()]
    if not no_time:
        pillars.append(bz.getTime())
        gans.append(bz.getTimeGan())
        zhis.append(bz.getTimeZhi())
    wx = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for g in gans:
        wx[GAN_WUXING[g]] += 1
    for z in zhis:
        wx[ZHI_WUXING[z]] += 1
    day_gan = bz.getDayGan()
    month_zhi = bz.getMonthZhi()
    tiaohou = QIONGTONG_TIAOHOU.get(day_gan, {}).get(month_zhi, "")
    return {
        "city": cname,
        "tst_correction_min": total_diff,
        "pillars": pillars,
        "gans": gans,
        "zhis": zhis,
        "day_pillar": bz.getDay(),
        "day_gan": day_gan,
        "day_zhi": bz.getDayZhi(),
        "wx_counts": wx,
        "tiaohou": tiaohou
    }

def run_hepan(args):
    p1 = _quick_bazi_pillars(args.date1, args.time1, args.city1, no_time=False)
    p2 = _quick_bazi_pillars(args.date2, args.time2, args.city2, no_time=args.no_time2)

    # 1. 宿命吸引力与干支互换/重叠扫描
    karmic_links = []
    if p1["day_pillar"] in p2["pillars"]:
        karmic_links.append(f"【干支同柱强宿命连接】甲方的日柱「{p1['day_pillar']}」直接出现在乙方的四柱中（代表一眼万年、极强的宿命熟悉感与磁场吸附力）")
    if p2["day_pillar"] in p1["pillars"]:
        karmic_links.append(f"【干支同柱强宿命连接】乙方的日柱「{p2['day_pillar']}」直接出现在甲方的四柱中（代表乙方天然容易走进甲方的内心领地）")
    if p1["day_gan"] == p2["day_gan"]:
        karmic_links.append(f"【同日元镜像共鸣】双方同为「{p1['day_gan']}」日主，底层思维逻辑高度一致，但也容易犯同样的倔脾气。")

    gan_he_map = {
        frozenset(["甲", "己"]): "甲己中正之合（重信守诺、极具家庭与现实归属感）",
        frozenset(["乙", "庚"]): "乙庚仁义之合（刚柔相济、强慕强与保护欲连接）",
        frozenset(["丙", "辛"]): "丙辛威制之合（颜值与气场吸引、欢喜冤家）",
        frozenset(["丁", "壬"]): "丁壬多情之合（精神与荷尔蒙双重高浓度吸引，极具浪漫纠缠感）",
        frozenset(["戊", "癸"]): "戊癸老少/互补之合（现实兜底与灵动才华的深度绑定）"
    }
    dg_pair = frozenset([p1["day_gan"], p2["day_gan"]])
    if dg_pair in gan_he_map:
        karmic_links.append(f"【日干天作之合】甲方日主「{p1['day_gan']}」与乙方日主「{p2['day_gan']}」构成：{gan_he_map[dg_pair]}")

    # 2. 婚姻宫（日支）碰撞雷达
    dz1, dz2 = p1["day_zhi"], p2["day_zhi"]
    dz_pair = frozenset([dz1, dz2])
    marriage_palace_verdict = []
    zhi_he_map = {
        frozenset(["子", "丑"]): "子丑六合（沉默务实的深度绑定）",
        frozenset(["寅", "亥"]): "寅亥六合（互相成全与滋养）",
        frozenset(["卯", "戌"]): "卯戌六合（干柴烈火的激情锁定）",
        frozenset(["辰", "酉"]): "辰酉六合（审美与物质高度契合）",
        frozenset(["巳", "申"]): "巳申六合（合中带刑，又爱又磨的智性恋）",
        frozenset(["午", "未"]): "午未六合（温暖燥热、双向奔赴）"
    }
    zhi_chong_map = {
        frozenset(["子", "午"]): "子午正冲（水火极性相冲：异地或聚少离多时极其思念，一旦朝夕相处则脾气、作息与安全感表达方式极易正面顶牛）",
        frozenset(["丑", "未"]): "丑未相冲（两库相冲：现实金钱观、家庭边界与闷葫芦冷战模式的碰撞）",
        frozenset(["寅", "申"]): "寅申相冲（驿马对冲：双方都忙、节奏极快，容易聚少离多或硬碰硬）",
        frozenset(["卯", "酉"]): "卯酉正冲（桃花门户对冲：感情洁癖与异性边界感极易触发信任危机）",
        frozenset(["辰", "戌"]): "辰戌相冲（水火天罗地网相冲：自尊心极强，吵架容易翻旧账）",
        frozenset(["巳", "亥"]): "巳亥相冲（驿马水火相冲：想法多变，需防沟通错频）"
    }
    zhi_hai_map = {
        frozenset(["子", "未"]): "子未相害（暗中挑剔与情绪内耗）",
        frozenset(["丑", "午"]): "丑午相害（一方热烈急躁、一方闷着冷处理，最怕冷暴力晦火）",
        frozenset(["寅", "巳"]): "寅巳相害（越在乎越容易说话带刺）",
        frozenset(["卯", "辰"]): "卯辰相害（细节控与安全感拉扯）",
        frozenset(["申", "亥"]): "申亥相害（表面迁就实则心里记账）",
        frozenset(["酉", "戌"]): "酉戌相害（敏感多疑与面子拉扯）"
    }
    if dz_pair in zhi_he_map:
        marriage_palace_verdict.append(f"【夫妻宫六合大吉】双方日支「{dz1}」与「{dz2}」构成{zhi_he_map[dz_pair]}，同居与现实磨合顺畅，床头吵架床尾和。")
    elif dz_pair in zhi_chong_map:
        marriage_palace_verdict.append(f"【夫妻宫六冲预警】双方日支「{dz1}」与「{dz2}」构成{zhi_chong_map[dz_pair]}。破局关键：保持独立空间或聚少离多小别胜新婚，切忌在气头上硬逼表态。")
    elif dz_pair in zhi_hai_map:
        marriage_palace_verdict.append(f"【夫妻宫相害提醒】双方日支「{dz1}」与「{dz2}」构成{zhi_hai_map[dz_pair]}。破局关键：有话直说，严禁冷战与阴阳怪气。")
    elif dz1 == dz2:
        marriage_palace_verdict.append(f"【夫妻宫同支共振】双方日支同为「{dz1}」，生活习惯与痛点如照镜子（若为辰午酉亥则需防同步钻牛角尖自刑）。")
    else:
        marriage_palace_verdict.append(f"【夫妻宫平和相交】甲方日支「{dz1}」({ZHI_WUXING[dz1]}) 与乙方日支「{dz2}」({ZHI_WUXING[dz2]}) 无剧烈刑冲，相处重在日常磨合。")

    # 3. 桃花密度与异性边界感扫描
    taohua_set = {"子", "午", "卯", "酉"}
    p1_th = [z for z in p1["zhis"] if z in taohua_set]
    p2_th = [z for z in p2["zhis"] if z in taohua_set]

    output = {
        "meta": {
            "engine": "东方玄学宗师 · 双人八字合盘与宿命纠缠引擎 v2.0",
            "person1": f"甲方({args.gender1}) 四柱：{' '.join(p1['pillars'])}（日主：{p1['day_gan']}，夫妻宫：{p1['day_zhi']}，真太阳时修正 {p1['tst_correction_min']:+.2f} 分钟）",
            "person2": f"乙方({args.gender2}) {'前三柱' if args.no_time2 else '四柱'}：{' '.join(p2['pillars'])}（日主：{p2['day_gan']}，夫妻宫：{p2['day_zhi']}，真太阳时修正 {p2['tst_correction_min']:+.2f} 分钟）"
        },
        "karmic_attraction": karmic_links if karmic_links else ["双方靠后天大运流年交集与五行互补建立连接"],
        "marriage_palace_collision": marriage_palace_verdict,
        "wuxing_supply_chain": {
            "person1_tiaohou_need": p1["tiaohou"],
            "person1_wuxing_counts": p1["wx_counts"],
            "person2_tiaohou_need": p2["tiaohou"],
            "person2_wuxing_counts": p2["wx_counts"],
        },
        "taohua_boundary_scan": {
            "person1_taohua_branches": f"地支四正桃花({len(p1_th)}朵)：{p1_th}",
            "person2_taohua_branches": f"地支四正桃花({len(p2_th)}朵)：{p2_th} {'【桃花极旺，人缘好但需重点立好异性边界感】' if len(p2_th) >= 2 else ''}"
        }
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

# ==============================================================================
# CLI 入口
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="东方玄学宗师 · 四大术数毫秒级排盘引擎")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    # 1. bazi
    p_bazi = subparsers.add_parser("bazi", help="子平八字 + 盲派 + 穷通宝鉴 + 真太阳时排盘")
    p_bazi.add_argument("--year", type=int, required=False)
    p_bazi.add_argument("--month", type=int, required=False)
    p_bazi.add_argument("--day", type=int, required=False)
    p_bazi.add_argument("--date", type=str, required=False, help="YYYY-MM-DD")
    p_bazi.add_argument("--time", type=str, required=False, help="HH:MM")
    p_bazi.add_argument("--hour", type=int, default=12)
    p_bazi.add_argument("--minute", type=int, default=0)
    p_bazi.add_argument("--gender", type=str, default="男", help="男/女")
    p_bazi.add_argument("--city", type=str, default=None, help="出生城市名，如：北京、上海、成都、乌鲁木齐")
    p_bazi.add_argument("--lon", type=float, default=None, help="自定义出生地经度，如 114.06")
    p_bazi.add_argument("--lunar", action="store_true", help="输入是否为农历")
    p_bazi.add_argument("--leap", action="store_true", help="农历是否为闰月")
    p_bazi.add_argument("--no-tst", action="store_true", help="禁用真太阳时校正")
    p_bazi.add_argument("--sect", type=int, default=2, help="晚子时流派：2=日柱算当天(默认)，1=日柱算次日")

    # 2. xiaoliuren
    p_xlr = subparsers.add_parser("xiaoliuren", help="道家小六壬三宫掌诀起课")
    p_xlr.add_argument("--nums", type=int, nargs=3, help="报三个正整数起课，如 --nums 3 15 28")
    p_xlr.add_argument("--question", type=str, default="", help="所问何事")

    # 3. meihua
    p_mh = subparsers.add_parser("meihua", help="《周易》梅花易数起卦装卦")
    p_mh.add_argument("--nums", type=int, nargs="+", help="报2或3个正整数起卦，如 --nums 5 8 12")
    p_mh.add_argument("--question", type=str, default="", help="所问何事")

    # 4. ziwei
    p_zw = subparsers.add_parser("ziwei", help="紫微斗数十二宫与十四主星/六吉六煞桃花/十年大限/四化安星")
    p_zw.add_argument("--year", type=int, required=False)
    p_zw.add_argument("--month", type=int, required=False)
    p_zw.add_argument("--day", type=int, required=False)
    p_zw.add_argument("--date", type=str, required=False, help="YYYY-MM-DD")
    p_zw.add_argument("--time", type=str, required=False, help="HH:MM")
    p_zw.add_argument("--hour", type=int, default=12)
    p_zw.add_argument("--minute", type=int, default=0)
    p_zw.add_argument("--gender", type=str, default="女", help="男/女（用于推算十年大限顺逆）")
    p_zw.add_argument("--lunar", action="store_true", help="输入是否为农历")

    # 5. hepan
    p_hp = subparsers.add_parser("hepan", help="双人八字合盘（婚恋正缘/前任纠缠/事业合伙交叉推演引擎）")
    p_hp.add_argument("--date1", type=str, required=True, help="甲方公历生日 YYYY-MM-DD")
    p_hp.add_argument("--time1", type=str, default="12:00", help="甲方出生时间 HH:MM（未知默认12:00）")
    p_hp.add_argument("--city1", type=str, default=None, help="甲方出生城市")
    p_hp.add_argument("--gender1", type=str, default="女", help="甲方性别")
    p_hp.add_argument("--date2", type=str, required=True, help="乙方公历生日 YYYY-MM-DD")
    p_hp.add_argument("--time2", type=str, default="12:00", help="乙方出生时间 HH:MM（未知默认12:00）")
    p_hp.add_argument("--city2", type=str, default=None, help="乙方出生城市")
    p_hp.add_argument("--gender2", type=str, default="男", help="乙方性别")
    p_hp.add_argument("--no-time2", action="store_true", help="乙方无具体出生时辰（仅合前三柱）")

    args = parser.parse_args()
    if args.cmd == "bazi":
        run_bazi(args)
    elif args.cmd == "xiaoliuren":
        run_xiaoliuren(args)
    elif args.cmd == "meihua":
        run_meihua(args)
    elif args.cmd == "ziwei":
        run_ziwei(args)
    elif args.cmd == "hepan":
        run_hepan(args)

if __name__ == "__main__":
    main()
