"""
CRM 产品添加 API 请求模块
"""

import requests


def add_product(product_data, session):
    """
    添加产品到 CRM
    
    Args:
        product_data: 产品数据字典
        session: requests session 对象（包含 cookie）
    """
    url = 'https://crm.gzbbr.com/api/Product.Product/crmProductAdd'
    
    # 从 cookie 中获取 authorization
    auth_token = session.cookies.get('authorization')
    
    headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0'
    }
    
    # 如果有 authorization token，添加到 header
    if auth_token:
        headers['authorization'] = auth_token
    
    try:
        # 使用传入的 session（已包含 cookie）
        response = session.post(url, json=product_data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"请求失败：{e}")
        return None


def create_product_entry(product_name, brand_name, vehicle_name, number, brand_id, session):
    """
    创建产品信息并添加到 CRM
    
    Args:
        product_name: 产品名称（用于 l_name_zh 和 l_name_zh_store）
        brand_name: OE 品牌名称
        vehicle_name: 车型
        number: 产品编号
        brand_id: 品牌 ID
        session: requests session 对象（包含 cookie）
    
    Returns:
        API 响应数据（字典）或 None
    """
    product_data = {
        "number": number,
        "brand_id": brand_id,
        "l_name_zh": product_name,
        "l_name_zh_store": product_name,
        "cass_oebrand_name": brand_name,
        "l_model_zh": vehicle_name
    }
    
    return add_product(product_data, session)

