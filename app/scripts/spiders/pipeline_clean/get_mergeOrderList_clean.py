# -*- coding:utf-8 -*-
# @Time    : 2026/4/11 15:30
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : get_mergeOrderList_clean.py
# @Software: PyCharm
import math

import numpy as np
import pandas as pd




def remove_duplicate(data_list,level_id):
    """
    去重和数据清洗函数
    
    该函数执行以下操作：
    1. 将数据列表转换为 DataFrame
    2. 删除 d_sap_no（金蝶单号）为空的记录
    3. 将清洗后的数据转换回字典列表
    4. 过滤只保留数据库模型定义的字段
    
    :param data_list: 原始数据列表，每个元素为一个订单数据字典
    :param level_id: 客户类型level_id
    :return: 过滤后的订单数据列表（已删除 d_sap_no 为空的记录，且只保留模型字段）
    """
    # 要保留的字段
    model_fields = [
        'orders_id', 'customer_id', 'level_id', 'is_wms', 'sap_no', 'd_sap_no',
        'fullname', 'customer_phone', 'sku_num', 'total_quantity', 'realqty',
        'total_price', 'sfje', 'no_receive_amount', 'status', 'order_type_id',
        'order_source_name', 'handler', 'create_date', 'user_id', 'remark',
        'street', 'warehouse', 'order_error','partner_id'
    ]


    # # 初始化空的 DataFrame（冗余代码，保留原格式）
    # df = pd.DataFrame()
    # 将数据列表转换为 DataFrame
    df = pd.DataFrame(data_list)
    # 删除 d_sap_no（金蝶单号）为空的记录，使用 copy() 避免 SettingWithCopyWarning
    df = df.dropna(subset=['d_sap_no']).copy()

    df["level_id"] = level_id

    df=df[model_fields]

    # 只把 partner_id 的空值 强制变成 -1
    # 替换：空字符串 / 空格 / None / NaN  →  0
    # 你要批量处理的字段
    cols = ['partner_id', 'is_wms','customer_id']

    # 循环处理（干净、稳定、不报错）
    for col in cols:
        df[col] = df[col].replace(['', r'^\s*$', None, np.nan], -1, regex=True)


    # df['partner_id'] = df['partner_id'].fillna(-1)
    # # 转成整型（适配你的 int 字段）
    # df['partner_id'] = df['partner_id'].astype(int)

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')


    # 返回过滤后的订单数据列表，供调用者进行入库操作
    return clean_data_list