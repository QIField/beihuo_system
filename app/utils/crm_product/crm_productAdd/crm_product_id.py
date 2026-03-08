"""
CRM Product ID 查询模块
"""

import requests
from config import get_auth_headers


SEARCH_URL = 'https://crm.gzbbr.com/api/Product.Product/list'


def search_product(session, oe_number):
    """
    查询产品列表
    """
    payload = {
        "numberlist": oe_number,
        "page": 1,
        "limit": 200
    }
    
    headers = get_auth_headers(session)
    response = session.post(SEARCH_URL, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        return response.json()
    return None


def get_product_id(session, oe_number, brand):
    """
    精准匹配获取 product_id
    """
    result = search_product(session, oe_number)
    if not result:
        return None
    
    products = result.get("data", {}).get("data", [])
    
    for product_group in products:
        for child in product_group.get("child", []):
            if (child.get("number") == oe_number and 
                child.get("brand_name") == brand):
                return child.get("product_id")
    
    return None
