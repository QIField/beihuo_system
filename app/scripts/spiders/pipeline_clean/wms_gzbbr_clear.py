# -*- coding:utf-8 -*-
# @Time    : 2026/06/15 09:38
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_gzbbr_clear.py
# @Software: trae-cn



import pandas as pd

from app.exceptions.data_exceptions import DataNotFoundError


def get_status_orders_clean(data_list, store='fsbbr', extra_fields=None):
    """
    去重和数据清洗函数

    该函数执行以下操作：
    1. 将数据列表转换为 DataFrame
    2. 删除 pono（拣货单号）为空的记录
    3. 将清洗后的数据转换回字典列表
    4. 过滤只保留数据库模型定义的字段
    5. 可选保留 extra_fields 中指定的额外字段（不入库，仅供上层任务使用）

    :param data_list: 原始数据列表，每个元素为一个订单数据字典
    :param store: 门店标识
    :param extra_fields: 可选，额外需要保留的字段名列表
    :return: 过滤后的订单数据列表
    """
    # 要保留的字段
    model_fields = [
        'type', 'is_checkupdate', 'orders_id', 'orders_no', 'pono',
        'rid', 'frey_no', 'status', 'partner_sapno', 'fullname',
        'orderdate', 'name', 'dhdate', 'jhdate', 'qty', 'toqty',
        'l_name_zh', 'supplier_short_name', 'wait_pick_num', 'already_pick_num'
    ]

    extra_fields = extra_fields or []
    keep_fields = list(model_fields)
    for field in extra_fields:
        if field not in keep_fields:
            keep_fields.append(field)

    # 将数据列表转换为 DataFrame
    df = pd.DataFrame(data_list)

    # 删除 pono（拣货单号）为空的记录，使用 copy() 避免 SettingWithCopyWarning
    df = df.dropna(subset=['pono']).copy()

    # 只保留需要的字段（模型字段 + 可选额外字段）
    available_fields = [col for col in keep_fields if col in df.columns]
    df = df[available_fields]

    # 添加门店store字段
    df['store'] = store

    # 处理空值，将空字符串 / 空格 / None / NaN 替换为 None
    for col in available_fields:
        df[col] = df[col].replace(['', r'^\s*$'], None, regex=True)  # pyright: ignore[reportAttributeAccessIssue]

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')  # pyright: ignore[reportArgumentType]

    # 返回过滤后的订单数据列表，供调用者进行入库操作
    return clean_data_list


def product_list_clean(data,oe_code):
    """
    产品列表数据清洗函数
    
    从 Product.Product/list 接口返回的数据中提取产品信息，
    只保留 name、stock、number、price、product_id、brand_name 字段，
    并且只保留 stock 大于 0 的记录。
    
    :param data: 接口返回的原始 JSON 数据（已解析为字典）
    :return: 清洗后的产品列表，每个元素包含 name、stock、number、price、product_id、brand_name
    """
    if not data or not isinstance(data, dict):
        return []
    
    data_obj = data.get('data', {})
    if not data_obj or not isinstance(data_obj, dict):
        return []
    
    data_list = data_obj.get('data', [])
    if not data_list or not isinstance(data_list, list):
        return []
    
    model_fields = ['name', 'stock', 'number', 'price', 'product_id', 'brand_name']
    
    all_products = []
    for item in data_list:
        child_list = item.get('child', [])
        if child_list and isinstance(child_list, list):
            for product in child_list:
                all_products.append(product)
    
    df = pd.DataFrame(all_products)
    
    if df.empty:
        return []
    
    available_fields = [field for field in model_fields if field in df.columns]
    df = df[available_fields].copy()
    
    df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0)  # pyright: ignore[reportAttributeAccessIssue]
    
    df = df[df['stock'] > 0].copy()
    
    df['contrast_price_flag'] = pd.to_numeric(df['price'], errors='coerce').round(0).astype(int)  # pyright: ignore[reportAttributeAccessIssue]
    df['product_id'] = pd.to_numeric(df['product_id'], errors='coerce')
    df['search_no'] = oe_code
    
    clean_data_list = df.to_dict('records')  # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]
    
    return clean_data_list


def crawl_products_by_oe_brand_clean(oe_code, product_list):
    """
    根据 OE 号精确匹配清洗产品数据
    
    由于 API 返回的是模糊匹配结果，会包含多个不同 OE 号的产品，
    此函数只保留 OE 号与输入完全匹配的产品记录。
    
    :param oe_code: 输入的 OE 号，用于精确匹配
    :param product_list: 接口返回的原始 JSON 数据（已解析为字典）
    :return: 清洗后的产品列表，每个元素包含 name、stock、number、price、product_id、brand_name、contrast_price_flag、search_no
    """
    # 参数校验：检查输入数据是否有效
    if not product_list or not isinstance(product_list, dict):
        return []
    
    # 提取 data.data 层级数据
    data_obj = product_list.get('data', {})
    if not data_obj or not isinstance(data_obj, dict):
        return []
    
    data_list = data_obj.get('data', [])
    if not data_list or not isinstance(data_list, list):
        return []
    
   

    # 定义需要保留的字段列表
    model_fields = ['name', 'stock', 'number', 'price', 'product_id', 'brand_name']
    
    # 使用列表推导式展平所有 child 列表，提取所有产品数据
    child_lists = [item.get('child', []) for item in data_list if isinstance(item.get('child'), list)]
    all_products = [product for child_list in child_lists for product in child_list]
    
    # 检查是否为"找不到产品"的情况
    for product in all_products:
        if product.get('name') == '找不到产品':
            raise DataNotFoundError('找不到产品')

    # 转换为 DataFrame 进行向量化清洗
    df = pd.DataFrame(all_products)
    
    # 空数据检查
    if df.empty:
        return []
    
    # 只保留 is_bold=1 的记录（兼容字符串和整数类型）
    if 'is_bold' in df.columns:
        df['is_bold'] = pd.to_numeric(df['is_bold'], errors='coerce').fillna(0)  # pyright: ignore[reportAttributeAccessIssue]
        df = df[df['is_bold'] == 1].copy()
    
    # 精确匹配 OE 号：将 number 字段转为字符串并去除空格后与输入 OE 号严格比较
    df['number'] = df['number'].astype(str).str.strip()  # pyright: ignore[reportAttributeAccessIssue]
    # df = df[df['number'] == oe_code.strip()].copy()
    
    # 匹配后为空检查
    if df.empty:
        return []
    
    # 只保留模型定义的字段
    available_fields = [field for field in model_fields if field in df.columns]
    df = df[available_fields].copy()
    
 
    
    # 匹配后为空检查
    if df.empty:  # pyright: ignore[reportAttributeAccessIssue]
        return []
    
   
    df['product_id'] = pd.to_numeric(df['product_id'], errors='coerce')
    
    df['price'] = pd.to_numeric(df['price'].replace('', 0), errors='coerce').fillna(0).round(2).astype(float)  # pyright: ignore[reportAttributeAccessIssue]


    # 转换为字典列表返回
    clean_data_list = df.to_dict('records')  # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]
    
    return clean_data_list