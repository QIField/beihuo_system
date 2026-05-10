"""
Cookie 和 Session 配置模块
提供 CRM 系统的认证和请求会话管理功能
"""

import requests
from .crm_config import get_crm_cookies


# 门店代码映射表
STORE_KEY_MAP = {
    'fsbbr': 'fs',   # 佛山
    'zsbbr': 'zs',   # 中山
    'zhbbr': 'zh',   # 珠海
    'dghf': 'hf',    # 合峰
    'dgby': 'by',    # 百业
}


def get_store_key(store_code):
    """
    根据门店代码获取对应的cookie key
    
    Args:
        store_code: 门店代码，如 fsbbr, zsbbr等
    
    Returns:
        str: cookie接口的key
    """
    return STORE_KEY_MAP.get(store_code, 'fs')


def create_crm_session(store_code='fsbbr'):
    """
    创建带有 CRM 认证信息的 requests Session
    
    Args:
        store_code: 门店代码，如 fsbbr, zsbbr等
    
    Returns:
        requests.Session: 已配置好认证信息的 session 对象
        
    Example:
        >>> session = create_crm_session('fsbbr')
        >>> response = session.get('https://crm.gzbbr.com/api/...')
    """
    store_key = get_store_key(store_code)
    
    # 获取 CRM cookie 认证信息
    crm_cookies = get_crm_cookies(store_key)
    
    # 创建 session
    session = requests.Session()
    
    # 设置基础 headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://crm.gzbbr.com/',
    })
    
    # 将 cookie 认证信息添加到 headers
    session.headers.update(crm_cookies)
    
    return session


def get_auth_headers(session):
    """
    从 session 中提取认证相关的 headers
    
    Args:
        session: requests Session 对象
        
    Returns:
        dict: 包含认证信息的 headers 字典
    """
    # 从 session.headers 中获取 authorization（因为 create_crm_session 把 cookie 放到了 headers）
    auth_token = session.headers.get('authorization')
    
    headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0'
    }
    
    # 如果有 authorization token，添加到 header
    if auth_token:
        headers['authorization'] = auth_token
    else:
        print(f"[警告] 未找到 authorization token，session.headers: {dict(session.headers)}")
        
    return headers


def create_authenticated_headers(cookies_dict=None):
    """
    创建带有认证信息的请求 headers
    
    Args:
        cookies_dict: 可选，自定义 cookie 字典，不传则自动获取
        
    Returns:
        dict: 完整的请求 headers
    """
    if cookies_dict is None:
        cookies_dict = get_crm_cookies()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://crm.gzbbr.com/',
    }
    
    # 合并 cookie 认证信息
    headers.update(cookies_dict)
    
    return headers
