"""
CRM OE Link API 请求模块 - 简化版
"""

import requests
from config import get_auth_headers


def get_oe_link(number, session):
    """
    获取 OE 链接信息
    
    Args:
        number: 产品编号
        session: requests session 对象（包含 cookie）
    
    Returns:
        包含 product_name, vehicle_name, brand_name 的字典，失败返回 None
    """
    url = 'https://crm.gzbbr.com/api/Product.Product/get_oe_link'
    
    # 使用工具函数获取认证 headers
    headers = get_auth_headers(session)
    
    params = {'number': number}
    
    try:
        # 使用传入的 session（已包含 cookie）
        response = session.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result and result.get('status') == 200:
            data = result.get('data', {})
            return {
                'product_name': data.get('product_name'),
                'vehicle_name': data.get('vehicle_name'),
                'brand_name': data.get('brand_name')
            }
        return None
    except Exception as e:
        print(f"请求失败：{e}")
        return None
