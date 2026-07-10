# -*- coding:utf-8 -*-
# @Time    : 2026/06/15 09:38
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_gzbbr_clear.py
# @Software: trae-cn



import pandas as pd


def get_status_orders_clean(data_list,store='fsbbr'):
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
        'orderdate', 'name', 'dhdate', 'jhdate', 'qty', 'toqty',
        'l_name_zh','supplier_short_name', 'wait_pick_num', 'already_pick_num'
    ]

    # 将数据列表转换为 DataFrame
    df = pd.DataFrame(data_list)
    
    # 删除 pono（拣货单号）为空的记录，使用 copy() 避免 SettingWithCopyWarning
    df = df.dropna(subset=['pono']).copy()

    # 只保留模型字段
    df = df[model_fields]
    
    #添加门店store字段
    df['store'] = store

    # 处理空值，将空字符串 / 空格 / None / NaN 替换为 None
    cols = model_fields
    for col in cols:
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