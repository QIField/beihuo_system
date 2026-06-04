# -*- coding:utf-8 -*-
# @Time    : 2026/5/23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : mercedes_dalfsc_clean.py
# @Software: PyCharm
import numpy as np
import pandas as pd
import json


def clean_parts_information(data_dict):
    """
    清洗奔驰零件信息数据
    
    根据 demo.json 和截图中的字段进行清洗和提取
    
    :param data_dict: 原始零件信息字典
    :return: 清洗后的零件信息字典
    """
    # 要保留的字段映射
    clean_data = {
        # 基本信息 - part_number 需要去除所有空格
        'part_number': data_dict.get('partNo', {}).get('number', '').replace(' ', ''),
        # 'descriptions': data_dict.get('partNo', {}).get('description', ''),
        'description_cn': data_dict.get('partNo', {}).get('description', ''),
        'marketing_code': data_dict.get('marketingCode', ''),
        'dealer_discount_group': data_dict.get('discountGroup', ''),
        
        # 价格信息
        'msrp': data_dict.get('currentMarketGuidancePrice', {}).get('value'), #市场指导价
        'purchase_price': data_dict.get('currentSellingPrice', {}).get('value'), #巴博瑞采购价
        'wholesale_price': data_dict.get('currentSellingPrice', {}).get('value'),#批发价
        
        # 基本数据
        'quantity_unit': data_dict.get('baseUnit', ''),
        # 长度、宽度、高度只保存数值，单位固定为 m
        'weight': data_dict.get('weight', {}).get('weightValue'),
        'length': data_dict.get('length', {}).get('lengthValue'),
        'width': data_dict.get('width', {}).get('lengthValue'),
        'height': data_dict.get('height', {}).get('lengthValue'),
        'volume': data_dict.get('volume', {}).get('volumeValue'),
        
        # 其他信息
        'effective_date': data_dict.get('currentValidFromDate', ''),
        'origin_country': data_dict.get('countryManufacture', ''),
        'brand': '奔驰',
        'category': data_dict.get('assortmentClasses', ''),
        'shelf_life': data_dict.get('shelfLife', {}).get('shelfLifeUnit', ''),
        'is_hazmat': '是' if data_dict.get('hazmatIndicator') else '否',
        
        # 零件替代关系信息（JSON格式）
        'part_nr_info_super_session': json.dumps(data_dict.get('partNrInfoSuperSession', {}), ensure_ascii=False),
        
        # 数据来源
        'data_source': 'dalfsc.aftersales.mercedes-benz.com'
    }

    
    return clean_data


def clean_stock_information(data_list):
    """
    清洗奔驰库存信息数据

    根据 demo.json 中的字段进行清洗和提取

    :param data_list: 原始库存信息列表
    :return: 清洗后的库存信息列表
    """
    clean_data_list = []

    for item in data_list:
        # 零件编号 - 只去除空格
        part_number = item.get('partNo', {}).get('number', '').replace(' ', '')
        
        # 仓库信息
        warehouse = item.get('warehouse', '')
        
        # 描述信息
        description = item.get('partNo', {}).get('description', '')
        
        # 可用数量 - 直接获取原始值
        quantity_available = item.get('quantityAvailable', {}).get('amount')
        
        # 单位信息
        unit = item.get('quantityAvailable', {}).get('unitId', '')
        
        clean_data = {
            'part_number': part_number,
            'warehouse': warehouse,
            'description': description,
            'quantity_available': quantity_available,
            'unit': unit
        }
        clean_data_list.append(clean_data)

    return clean_data_list


def extract_all_part_numbers_from_part_data(part_data):
    """
    从零件API返回的数据中提取所有相关的零件编号
    
    包括主零件编号和 partNrInfoSuperSession 中所有的替代零件编号
    
    :param part_data: 零件API返回的原始数据字典
    :return: 零件编号列表（已去重）
    """
    part_numbers = set()
    
    # 添加主零件编号 - 不去空格，保持原始格式用于API请求
    main_part_number = part_data.get('partNo', {}).get('number', '')
    if main_part_number:
        part_numbers.add(main_part_number)
    
    # 递归提取 partNrInfoSuperSession 中的零件编号
    def extract_from_super_session(session_node):
        if not session_node:
            return
        
        # 添加当前节点的零件编号 - 不去空格，保持原始格式用于API请求
        part_no = session_node.get('partNo', {}).get('number', '')
        if part_no:
            part_numbers.add(part_no)
        
        # 递归处理子节点
        children = session_node.get('children', [])
        for child in children:
            extract_from_super_session(child)
    
    # 从 partNrInfoSuperSession 中提取
    super_session = part_data.get('partNrInfoSuperSession', {})
    extract_from_super_session(super_session)
    
    # 转换为列表返回
    return list(part_numbers)
