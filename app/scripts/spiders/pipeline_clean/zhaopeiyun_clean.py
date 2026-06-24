# -*- coding:utf-8 -*-
# @Time    : 2026/6/22
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : zhaopeiyun_clean.py
# @Software : PyCharm

import json
from datetime import datetime


def format_date(date_str):
    """
    将ISO格式日期字符串转换为标准格式

    将 "2026-06-22T10:49:39" 格式转换为 "2026-06-22 10:49:39"

    :param date_str: 原始日期字符串
    :return: 格式化后的日期字符串，如果转换失败则返回原始字符串
    """
    if not date_str:
        return date_str

    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return date_str


# 城市名 -> 数据库 warehouse_ 字段名的映射
CITY_TO_DB_FIELD = {
    '北京': '库房-北京',
    '上海': '库房-上海',
    '佛山': '库房-佛山',
    '成都': '库房-成都',
    '沈阳': '库房-沈阳',
    '合肥': '库房-合肥',
    '宁波': '库房-宁波',
}


def _parse_stock_infos_string(stock_infos_str):
    """
    解析 partInfo.stockInfos 字符串（内部是 JSON 数组）

    :param stock_infos_str: 如 "[{\"warehouse\":\"库房  SY01\",\"stock\":\"13\",\"city\":\"北京\",...}]"
    :return: {city: stock} 字典
    """
    if not stock_infos_str:
        return {}

    try:
        stock_list = json.loads(stock_infos_str)
    except (json.JSONDecodeError, TypeError):
        return {}

    city_stock = {}
    for item in stock_list:
        city = item.get('city', '')
        stock = item.get('stock', '')
        if city and stock:
            city_stock[city] = stock

    return city_stock


def clean_stock_infos(data_dict):
    """
    清洗找配云零件库存数据

    解析 data.partInfo：提取零件基本字段 + 解析 stockInfos 字符串（城市-库存映射）
    结果字段直接对应 car_parts_library_zhaopeiyun_stock 表结构

    :param data_dict: 接口返回的完整 data 字典
    :return: 清洗后的字典（可直接入库）
    """
    if not data_dict:
        return {}

    part_info = data_dict.get('partInfo', {})

    # 1. 解析 stockInfos 字符串 → {city: stock}
    stock_infos_str = part_info.get('stockInfos', '')
    city_stock_map = _parse_stock_infos_string(stock_infos_str)

    # 2. 构建数据库字段映射：将城市库存填入 warehouse_xxx
    warehouse_fields = {}
    for city, db_field in CITY_TO_DB_FIELD.items():
        warehouse_fields[db_field] = city_stock_map.get(city, None)

    # 3. 合并：零件基本信息 + 各仓库库存
    clean_data = {
        # ===== 零件基础信息 =====
        'oe': part_info.get('partCode', '').replace(' ', ''),
        '零件名': part_info.get('partName', ''),
        '零售价':round(float(part_info.get('price'))/1.13,4),# 4S含税售价 
        '销售单位': str(part_info.get('ppq', '')) if part_info.get('ppq') is not None else '',

        # ===== 各仓库库存字段 (warehouse_xxx) =====
        **warehouse_fields,

        # ===== 其他信息 =====
        '采集时间': format_date(part_info.get('priceUpdatedAt', '')),
        '数据来源': 'zhaopeiyun.com',
    }

    return clean_data


def clean_part_info(data_dict):
    """
    清洗找配云零件基本信息数据

    从接口返回的 data.partInfo 中提取零件核心字段

    :param data_dict: 接口返回的完整 data 字典
    :return: 清洗后的零件信息字典
    """
    part_info = data_dict.get('partInfo', {}) if data_dict else {}

    clean_data = {

        # 基本信息
        'oe': part_info.get('partCode', '').replace(' ', ''),#零件编号
        '零件名': part_info.get('partName', ''),#零件名称
        '经销商净值(Stock)': round(float(part_info.get('cost'))/1.13,4),  # 4S含税进价  # pyright: ignore[reportArgumentType]
        '零售价': round(float(part_info.get('price'))/1.13,4),  # 4S含税售价  # pyright: ignore[reportArgumentType]
        '可用库存': part_info.get('stockInt'),#库存数量
        '族组': part_info.get('familyCode', ''),#族组
        '采集时间': format_date(part_info.get('priceUpdatedAt', '')),#价格更新时间
        '数据来源': 'zhaopeiyun.com', #数据来源
        
        
    }

    return clean_data


def clean_all(data_dict):
    """
    清洗找配云接口返回的数据

    :param data_dict: 接口返回的完整 data 字典
    :return: clean_part_info 的结果（可直接入库）
    """
    return {
        'detail': clean_part_info(data_dict),
        'stock': clean_stock_infos(data_dict),
        'is_zpy': True,
    }



