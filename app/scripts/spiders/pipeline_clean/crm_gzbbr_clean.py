# -*- coding:utf-8 -*-
# @Time    : 2026/06/06 13:03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crm_gzbbr_clean.py
# @Software: trae-cn
import numpy as np
import pandas as pd
import json
from typing import List, Dict, Union


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




def clean_sales_order_history(data: Union[Dict, List], store: str) -> List[Dict]:
    """
    销售订单历史数据清洗函数

    该函数执行以下操作：
    1. 从完整响应中提取 data.data 列表（Dict格式）或直接使用数据列表（List格式）
    2. 将数据列表转换为 DataFrame
    3. 数据清洗和字段过滤
    4. 处理空值
    5. 将清洗后的数据转换回字典列表

    支持两种输入格式：
    - Dict: 完整的API响应数据字典，自动从 data.data 提取列表
    - List: 已提取的数据列表，直接清洗

    :param data: 原始数据，Union[Dict, List]，可以是API响应字典或数据列表
    :param store: 仓库标识
    :return: 清洗后的销售订单历史数据列表
    """
    if isinstance(data, dict):
        # 兼容旧格式：从完整API响应中提取 data.data
        if not data or 'data' not in data:
            return []
        data_list = data.get('data', {}).get('data', [])
    else:
        # 新格式：直接使用传入的数据列表
        data_list = data if data else []

    if not data_list:
        return []

    df = pd.DataFrame(data_list)

    # 要保留的字段
    model_fields = [
        # 人员
        'handler',          # 处理人ID（创建人id）
        'user_id',          # 用户ID（经收人id）
        'seller_id',        # 销售员ID（创建人id）
        'customer_id',      # 客户ID
        # 订单类型与时间
        'order_type_id',    # 订单类型ID
        'create_date',      # 创建时间戳
        'send_date',        # 发货时间戳
        # 订单标识
        'orders_id',        # 订单ID
        'ddno',             # 订单号
        'ddsapno',          # 订单金蝶号
        # 状态
        'status',           # 订单状态（中文）
        'origin_status',    # 原始状态码
        # 客户信息
        'fullname',         # 客户全称
        # 数量
        'quantity',         # 数量
        'sfqty',            # 实发数量
        # 价格与金额
        'price',            # 单价
        'cost_price',       # 成本价
        'total_price',      # 总价
        'sfje',             # 实付金额
        # 产品信息
        'product_id',       # 产品ID
        'orders_items_id',  # 订单明细ID
        'brand_id',         # 品牌ID
        'pdname',           # 产品名称
        'frey_no',          # 菲尔号
        'l_model_zh',       # 车型（中文）
        'number',           # OE号
        # WMS与发货
        'is_wms',           # 是否WMS订单
        'delivery_status',  # 发货状态
        'logistics_name',   # 物流公司名称
        'kingdee_status',   # 金蝶状态
        'logistics_user_id',# 物流用户ID
        # 仓库
        'warehouse_no',     # 仓库编号
        # 品牌与订单类型
        'brand_name',       # 品牌名称
        'order_type_name',  # 订单类型名称
        # 用户与创建者
        'user_name',        # 用户名
        'creater',          # 创建人
        'seller_name',      # 销售员名称
        # 发货单号
        'deliverysapno',    # 发货金蝶号
        'deliveryordersno', # 发货单号
    ]

    # 只保留存在的字段
    available_fields = [field for field in model_fields if field in df.columns]
    df = df[available_fields].copy()

    df['store'] = store

    # 处理数字字段的空值：空字符串/空格/None/NaN → -1
    numeric_cols = [
        'handler', 'user_id', 'seller_id', 'customer_id',
        'order_type_id', 'orders_id', 'origin_status',
        'product_id', 'orders_items_id', 'brand_id', 'is_wms',
        'delivery_status', 'kingdee_status', 'logistics_user_id'
    ]
    available_numeric_cols = [col for col in numeric_cols if col in df.columns]

    for col in available_numeric_cols:
        df[col] = df[col].replace(['', r'^\s*$', None, np.nan], -1, regex=True)
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(-1).astype(int)
        except:
            pass

    # 处理金额和数量字段，转为 float
    amount_cols = [
        'quantity', 'sfqty', 'price', 'cost_price',
        'total_price', 'sfje'
    ]
    available_amount_cols = [col for col in amount_cols if col in df.columns]

    for col in available_amount_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')

    return clean_data_list


def crm_sales_order_clear(data_list,store,level_id = None):
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
        'total_price', 'sfje', 'no_receive_amount', 'status', 
        'order_source_name', 'handler', 'create_date', 'user_id', 'remark',
        'street', 'warehouse', 'order_error','partner_id','store','order_type_name'
    ]


    # # 初始化空的 DataFrame（冗余代码，保留原格式）
    # df = pd.DataFrame()
    # 将数据列表转换为 DataFrame
    df = pd.DataFrame(data_list)
    # 删除 d_sap_no（金蝶单号）为空的记录，使用 copy() 避免 SettingWithCopyWarning
    df = df.dropna(subset=['d_sap_no']).copy()

    if level_id is None:
        df["level_id"] = 0
    else:
        df["level_id"] = level_id


    
    df["store"] = store


    df=df[model_fields]

    # 只把 partner_id 的空值 强制变成 -1
    # 替换：空字符串 / 空格 / None / NaN  →  0
    # 你要批量处理的字段
    cols = ['partner_id', 'is_wms','customer_id']

    # 循环处理（干净、稳定、不报错）
    for col in cols:
        df[col] = df[col].replace(['', r'^\s*$', None, np.nan], -1, regex=True)  # pyright: ignore[reportAttributeAccessIssue]


    # df['partner_id'] = df['partner_id'].fillna(-1)
    # # 转成整型（适配你的 int 字段）
    # df['partner_id'] = df['partner_id'].astype(int)

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')  # pyright: ignore[reportArgumentType]


    # 返回过滤后的订单数据列表，供调用者进行入库操作
    return clean_data_list