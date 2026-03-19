# -*- coding: utf-8 -*-
"""
数据处理器

完全复刻原Excel导出逻辑：
1. 字段重命名（与原Excel一致）
2. 控制字符清理
3. 空值处理
"""

import re
import pandas as pd
from typing import List, Dict, Any
from .config import FIELD_MAPPING, DB_FIELDS


def clean_cell_value(value: Any) -> Any:
    """
    清理单元格数据

    与原代码 clean_cell() 函数完全一致：
    1. 移除所有控制字符
    2. 空字符串转为 None

    Args:
        value: 原始值

    Returns:
        清理后的值
    """
    # 处理 pandas 的 NaN
    if pd.isna(value):
        return None

    # 处理字符串
    if isinstance(value, str):
        # 移除所有控制字符（与原代码完全一致）
        cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', value)
        # 如果清理后为空字符串，返回None
        return cleaned if cleaned else None

    return value


def rename_fields(data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    字段重命名（与原Excel导出一致）

    Args:
        data_list: 原始数据列表

    Returns:
        重命名后的数据列表
    """
    renamed_data = []

    for item in data_list:
        new_item = {}
        for api_field, db_field in FIELD_MAPPING.items():
            # 获取原始值，如果不存在则为None
            value = item.get(api_field)
            new_item[db_field] = value
        renamed_data.append(new_item)

    return renamed_data


def clean_data(data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    数据清洗（完全复刻原Excel逻辑）

    步骤：
    1. 字段重命名
    2. 遍历所有单元格清理控制字符
    3. 处理空值

    Args:
        data_list: 原始数据列表

    Returns:
        清洗后的数据列表
    """
    if not data_list:
        return []

    # 第一步：字段重命名
    renamed_data = rename_fields(data_list)

    # 第二步：清理每个单元格
    cleaned_data = []
    for item in renamed_data:
        cleaned_item = {}
        for key, value in item.items():
            cleaned_item[key] = clean_cell_value(value)
        cleaned_data.append(cleaned_item)

    return cleaned_data


def prepare_for_database(data_list: List[Dict[str, Any]], supplier_name: str) -> List[tuple]:
    """
    准备数据用于数据库存储

    Args:
        data_list: 清洗后的数据列表
        supplier_name: 供应商名称

    Returns:
        元组列表，每个元组对应一条记录
    """
    if not data_list:
        return []

    db_records = []

    for item in data_list:
        # 按照 DB_FIELDS 顺序构建元组
        record = [supplier_name]  # 第一个字段是 supplier_name

        for field in DB_FIELDS[1:]:  # 跳过 supplier_name
            value = item.get(field)

            # 处理数值类型
            if field == '价格' and value is not None:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = None
            elif field == '库存数' and value is not None:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    value = None
            elif field == '是否共享' and value is not None:
                # 转换为 0/1
                value = 1 if str(value).lower() in ('true', '1', 'yes', '是') else 0

            record.append(value)

        db_records.append(tuple(record))

    return db_records


def process_data(data_list: List[Dict[str, Any]], supplier_name: str) -> List[tuple]:
    """
    完整数据处理流程

    Args:
        data_list: 原始API数据
        supplier_name: 供应商名称

    Returns:
        可直接插入数据库的元组列表
    """
    print(f"  开始数据清洗...")

    # 清洗数据（复刻Excel逻辑）
    cleaned_data = clean_data(data_list)
    print(f"  ✓ 数据清洗完成: {len(cleaned_data)} 条")

    # 准备数据库格式
    db_records = prepare_for_database(cleaned_data, supplier_name)
    print(f"  ✓ 数据格式转换完成")

    return db_records
