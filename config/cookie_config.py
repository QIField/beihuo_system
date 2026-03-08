"""
Cookie 和 Session 配置模块
提供 CRM 系统的认证和请求会话管理功能
"""

import requests
from .crm_config import get_crm_cookies


def create_crm_session():
    """
    创建带有 CRM 认证信息的 requests Session
    
    Returns:
        requests.Session: 已配置好认证信息的 session 对象
        
    Example:
        >>> session = create_crm_session()
        >>> response = session.get('https://crm.gzbbr.com/api/...')
    """
    # 获取 CRM cookie 认证信息
    crm_cookies = get_crm_cookies()
    
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
