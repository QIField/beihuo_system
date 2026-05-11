# -*- coding:utf-8 -*-
# @Time    : 2026/5/5 09:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_return_items_clean.py
# @Software: PyCharm

import numpy as np
import pandas as pd


def clean_return_items(data_list):
    """
    退货商品数据清洗函数

    该函数执行以下操作：
    1. 将数据列表转换为 DataFrame
    2. 只保留数据库模型定义的字段
    3. 处理空值，将空字符串 / 空格 / None / NaN 替换为 None
    4. 将清洗后的数据转换回字典列表

    :param data_list: 原始数据列表，每个元素为一个退货商品数据字典
    :return: 清洗后的退货商品数据列表
    """
    # 要保留的字段
    model_fields = [
        'brand_code', 'brand_name_en', 'suffix', 'return_qty',
        'frey_no', 'number', 'qty', 'kw_no', 'warehouse_name',
        'kc', 'brandname', 'l_name_zh', 'product_remark',
        'pono', 'orders_no', 'orders_id','needqty','status','type_param'
    ]

    if not data_list:
        return []

    # 将数据列表转换为 DataFrame
    df = pd.DataFrame(data_list)

    # 只保留模型字段
    df = df.reindex(columns=model_fields)

    # 处理空值，将空字符串 / 空格 / None / NaN 替换为 None
    for col in model_fields:
        df[col] = df[col].replace(['', r'^\s*$'], None, regex=True)

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')

    # 返回清洗后的退货商品数据列表，供调用者进行入库操作
    return clean_data_list
