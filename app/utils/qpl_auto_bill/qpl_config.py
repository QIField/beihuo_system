#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""配置"""

# 基础URL
BASE_URL = 'https://qpl-gateway.qipeilong.cn'

# Token缓存（按组织缓存）
_token_cache = {}

# 支持的组织列表
SUPPORTED_COMPANIES = ['fsbbr']

# 组织代码到配置键名的映射
COMPANY_TOKEN_KEY_MAP = {
    'fsbbr': 'QPL_AUTH_TOKEN_fs',
    # 未来可添加更多组织映射
    # 'gzbbr': 'QPL_AUTH_TOKEN_gz',
}


def get_qpl_token(company='fsbbr'):
    """
    获取指定组织的Token（延迟加载，从数据库配置获取）
    
    Args:
        company: 组织代码，默认fsbbr
    
    Returns:
        str: Token字符串
    """
    global _token_cache
    
    # 检查缓存
    if company in _token_cache:
        return _token_cache[company]
    
    # 从映射获取配置键名
    config_key = COMPANY_TOKEN_KEY_MAP.get(company)
    if not config_key:
        print(f"[汽配龙配置] 未找到组织 {company} 的Token配置映射")
        return None
    
    # 从数据库获取配置
    from config.config_list_manager.config_cache import get_config_value
    token = get_config_value(config_key)
    
    # 缓存token
    if token:
        _token_cache[company] = token
    
    return token


def get_headers(company='fsbbr'):
    """
    获取指定组织的Headers（延迟加载token）
    
    Args:
        company: 组织代码，默认fsbbr
    
    Returns:
        dict: Headers字典
    """
    token = get_qpl_token(company)
    return {
        'Content-Type': 'application/json',
        'Authorization': token,
        'authtype': 'qpl_merchant',
        'origin': 'https://s.qipeilong.cn',
        'referer': 'https://s.qipeilong.cn/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'qpl-info': 'QPL/WEB-BIZ',
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9'
    }


def clear_token_cache(company=None):
    """
    清除Token缓存
    
    Args:
        company: 组织代码，不传则清除所有缓存
    """
    global _token_cache
    if company:
        _token_cache.pop(company, None)
    else:
        _token_cache = {}


def get_supported_companies():
    """获取支持的组织列表"""
    return SUPPORTED_COMPANIES.copy()