# -*- coding:utf-8 -*-
# @Time    : 2026/06/06 13:03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crm_gzbbr_clean.py
# @Software: trae-cn
import numpy as np
import pandas as pd
import json
from typing import List, Dict


def clean_purchase_order_list(data_list: List[Dict],store:str) -> List[Dict]:
    """
    采购订单数据清洗和去重函数

    该函数执行以下操作：
    1. 将数据列表转换为 DataFrame
    2. 数据清洗和字段过滤（保留已确认字段）
    3. 处理空值
    4. 将清洗后的数据转换回字典列表

    :param data_list: 原始数据列表，每个元素为一个采购订单数据字典
    :return: 过滤后的采购订单数据列表
    """
    if not data_list:
        return []

    df = pd.DataFrame(data_list)

    # 要保留的字段（根据 demo/test 确认）
    model_fields = [
        # 订单标识
        'purchase_order_id', 'pono',
        # 供应商
        'partner_id', 'fullname', 'supplier_phone',
        # 订单状态
        'status', 'order_type_id', 'order_source_type',
        # 金额
        'total', 'amount_money', 'received_quantity',
        'received', 'shipping_fee', 'packing_fee',
        # 时间
        'create_date', 'expected_delivery_date', 'e_date',
        # 其他
        'name', 'payment_description', 'is_wms', 'remarks'
    ]

    # 只保留存在的字段
    available_fields = [field for field in model_fields if field in df.columns]
    df = df[available_fields].copy()

    df['store']=store

    # 处理数字字段的空值：空字符串/空格/None/NaN → -1
    numeric_cols = [
        'purchase_order_id', 'partner_id', 'status',
        'order_type_id', 'order_source_type', 'is_wms'
    ]
    available_numeric_cols = [col for col in numeric_cols if col in df.columns]

    for col in available_numeric_cols:
        df[col] = df[col].replace(['', r'^\s*$', None, np.nan], -1, regex=True)  # pyright: ignore[reportAttributeAccessIssue]
        # 尝试转为整数
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(-1).astype(int)  # pyright: ignore[reportAttributeAccessIssue]
        except:
            pass

    # 处理金额字段，转为 float
    amount_cols = [
        'total', 'amount_money', 'received_quantity',
        'received', 'shipping_fee', 'packing_fee'
    ]
    available_amount_cols = [col for col in amount_cols if col in df.columns]

    for col in available_amount_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)  # pyright: ignore[reportAttributeAccessIssue]

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')  # pyright: ignore[reportArgumentType]

    return clean_data_list    # pyright: ignore[reportReturnType]


def clean_purchase_order_items(data_dict: Dict, store: str) -> List[Dict]:
    """
    采购订单明细数据清洗函数

    该函数执行以下操作：
    1. 从完整响应中提取 Quotelineitem.data
    2. 将数据列表转换为 DataFrame
    3. 数据清洗和字段过滤
    4. 处理空值
    5. 将清洗后的数据转换回字典列表

    :param data_dict: 完整的API响应数据字典
    :param store: 仓库标识
    :return: 过滤后的采购订单明细数据列表
    """
    if not data_dict or 'data' not in data_dict:
        return []

    # 提取 Quotelineitem.data
    quotelineitem = data_dict.get('data', {}).get('Quotelineitem', {})
    data_list = quotelineitem.get('data', [])

    if not data_list:
        return []

    df = pd.DataFrame(data_list)

    # 要保留的字段（根据 demo/test 确认）
    model_fields = [
        # 订单明细标识
        'purchase_order_line_id', 'purchase_order_id', 'no',
        # 产品信息
        'product_id', 'number', 'l_model_zh', 'brand',
        'l_name_zh', 'brand_code', 'frey_no', 'user_code', 'unit',
        # 数量和金额
        'purchase_quantity', 'price', 'amount_money', 'unit_cost',
        'received_quantity', 'gift',
        # 费用
        'shipping_fee', 'unit_shipping_fee', 'packing_fee', 'unit_packing_fee',
        # 其他
        'delivery_date', 'company_remark', 'is_unsalable', 'ks_price'
    ]

    # 只保留存在的字段
    available_fields = [field for field in model_fields if field in df.columns]
    df = df[available_fields].copy()

    df['store'] = store

    # 处理数字字段的空值：空字符串/空格/None/NaN → -1
    numeric_cols = [
        'purchase_order_line_id', 'purchase_order_id', 'no', 'product_id',
        'gift', 'is_unsalable'
    ]
    available_numeric_cols = [col for col in numeric_cols if col in df.columns]

    for col in available_numeric_cols:
        df[col] = df[col].replace(['', r'^\s*$', None, np.nan], -1, regex=True)  # pyright: ignore[reportAttributeAccessIssue]
        # 尝试转为整数
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(-1).astype(int)  # pyright: ignore[reportAttributeAccessIssue]
        except:
            pass

    # 处理金额和数量字段，转为 float
    amount_cols = [
        'purchase_quantity', 'price', 'amount_money', 'unit_cost',
        'received_quantity', 'shipping_fee', 'unit_shipping_fee',
        'packing_fee', 'unit_packing_fee', 'ks_price'
    ]
    available_amount_cols = [col for col in amount_cols if col in df.columns]

    for col in available_amount_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)  # pyright: ignore[reportAttributeAccessIssue]

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')  # pyright: ignore[reportArgumentType]

    return clean_data_list    # pyright: ignore[reportReturnType]
