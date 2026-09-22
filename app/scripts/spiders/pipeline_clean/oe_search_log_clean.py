# -*- coding:utf-8 -*-
"""
OE搜索日志数据清洗函数

职责：
1. 过滤 API 原始字段，只保留数据库模型定义的字段
2. 类型转换（id、num、时间等）
3. 生成冗余字段 search_date
"""

from datetime import datetime
from typing import List, Dict, Union

import numpy as np
import pandas as pd


def clean_oe_search_log(data: Union[Dict, List], store: str = 'fs') -> List[Dict]:
    """
    OE 搜索日志数据清洗函数

    该函数执行以下操作：
    1. 从完整响应中提取 data.data 列表（Dict格式）或直接使用数据列表（List格式）
    2. 将数据列表转换为 DataFrame
    3. 数据清洗和字段过滤
    4. 处理空值和类型转换
    5. 将清洗后的数据转换回字典列表

    支持两种输入格式：
    - Dict: 完整的API响应数据字典，自动从 data.data 提取列表
    - List: 已提取的数据列表，直接清洗

    :param data: 原始数据，Union[Dict, List]
    :param store: 门店标识（当前仅透传，保留扩展性）
    :return: 清洗后的 OE 搜索日志数据列表
    """
    if isinstance(data, dict):
        if not data or 'data' not in data:
            return []
        data_list = data.get('data', {}).get('data', [])
    else:
        data_list = data if data else []

    if not data_list:
        return []

    df = pd.DataFrame(data_list)

    # 要保留的字段（数据库模型定义）
    model_fields = [
        'id',
        'brand_name', 'product_name',
        'oe_number', 'num', 'search_time',
    ]

    # 只保留存在的字段
    available_fields = [field for field in model_fields if field in df.columns]
    df = df[available_fields].copy()

    # 重命名 id -> source_biz_id
    if 'id' in df.columns:
        df = df.rename(columns={'id': 'source_biz_id'})

    # 处理数字字段的空值：空字符串/空格/None/NaN -> -1
    numeric_cols = ['num']
    available_numeric_cols = [col for col in numeric_cols if col in df.columns]
    for col in available_numeric_cols:
        df[col] = df[col].replace(['', r'^\s*$', None, np.nan], -1, regex=True)
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(-1).astype(int)
        except Exception:
            pass

    # 字符串字段去空格
    str_cols = [
        'source_biz_id',
        'brand_name', 'product_name', 'oe_number'
    ]
    available_str_cols = [col for col in str_cols if col in df.columns]
    for col in available_str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace(['None', 'nan', 'NaN', ''], None)

    # 解析 search_time 为 datetime，并生成 search_date
    if 'search_time' in df.columns:
        df['search_time'] = pd.to_datetime(df['search_time'], errors='coerce')
        df['search_date'] = df['search_time'].dt.strftime('%Y-%m-%d')

    # 添加 store 字段（扩展用）
    df['store'] = store

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')

    return clean_data_list
