# -*- coding:utf-8 -*-
# @Time    : 2026/4/26
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_get_status_orders_clean.py
# @Software: PyCharm

import numpy as np
import pandas as pd


def remove_duplicate(data_list):
    """
    去重和数据清洗函数
    
    该函数执行以下操作：
    1. 将数据列表转换为 DataFrame
    2. 删除 pono（拣货单号）为空的记录
    3. 将清洗后的数据转换回字典列表
    4. 过滤只保留数据库模型定义的字段
    
    :param data_list: 原始数据列表，每个元素为一个订单数据字典
    :return: 过滤后的订单数据列表（已删除 pono 为空的记录，且只保留模型字段）
    """
    # 要保留的字段
    model_fields = [
        'type', 'is_checkupdate', 'orders_id', 'orders_no', 'pono',
        'rid', 'frey_no', 'status', 'partner_sapno', 'fullname',
        'orderdate', 'name', 'dhdate', 'jhdate','printtime','companyname', 'qty', 'toqty',
        'l_name_zh','product_id','order_source_type','supplier_short_name', 'wait_pick_num', 'already_pick_num',
        'delivery_status','is_transfer_order'
    ]

    # 将数据列表转换为 DataFrame
    df = pd.DataFrame(data_list)
    
    # 删除 pono（拣货单号）为空的记录，使用 copy() 避免 SettingWithCopyWarning
    df = df.dropna(subset=['pono']).copy()

    # 只保留模型字段
    df = df[model_fields]

    # 处理空值，将空字符串 / 空格 / None / NaN 替换为 None
    cols = model_fields
    for col in cols:
        df[col] = df[col].replace(['', r'^\s*$'], None, regex=True)

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')

    # 返回过滤后的订单数据列表，供调用者进行入库操作
    return clean_data_list
