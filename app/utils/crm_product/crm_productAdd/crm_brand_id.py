"""
CRM 品牌 API 请求模块 - 简化版
"""

import requests


def get_brand_list(params=None, session=None):
    """
    获取品牌列表
    
    Args:
        params: 请求参数（可选）
        session: requests session 对象（包含 cookie）
    
    Returns:
        API 响应数据（字典）或 None
    """
    url = 'https://crm.gzbbr.com/api/Product.Brand/index'
    
    # 从 cookie 中获取 authorization
    auth_token = session.cookies.get('authorization')
    
    headers = {
        'accept': 'application/json, text/plain, */*',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0'
    }
    
    # 如果有 authorization token，添加到 header
    if auth_token:
        headers['authorization'] = auth_token
    
    try:
        # 使用传入的 session（已包含 cookie）
        response = session.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"请求失败：{e}")
        return None


def get_brand_dict(session):
    """
    获取品牌字典 {brand_id: l_name_zh}
    
    Args:
        session: requests session 对象（包含 cookie）
    
    Returns:
        品牌字典，格式：{'brand_id': '品牌名称', ...}
        失败时返回空字典
    """
    result = get_brand_list(session=session)
    
    if not result or result.get('status') != 200:
        print("获取品牌列表失败")
        return {}
    
    brand_list = result.get('data', {}).get('list', [])
    
    # 提取 brand_id 和 l_name_zh
    brand_dict = {
        item['brand_id']: item['l_name_zh'] 
        for item in brand_list 
        if 'brand_id' in item and 'l_name_zh' in item
    }
    
    return brand_dict

