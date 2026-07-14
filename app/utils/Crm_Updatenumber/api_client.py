#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRM UpdateNumber 接口模块
用于更新产品的 numbers（替换号/OE号列表）
"""

import requests
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config.crm_config import get_crm_cookies


UPDATE_NUMBER_URL = 'https://crm.gzbbr.com/api/Product.Product/updateNumber'

# 门店代码映射表（根据你的系统调整）
STORE_KEY_MAP = {
    'fsbbr': 'fs',      # 佛山
    'zsbbr': 'zs',         # 中山
    'zhbbr': 'zh',         # 珠海
    'dghf': 'hf',         # 合峰
    'dgby': 'by',         # 百业
}


def get_store_key(store_code):
    """
    根据门店代码获取对应的cookie key
    
    Args:
        store_code: 门店代码，如 fsbbr, zs, zh等
    
    Returns:
        str: cookie接口的key
    """
    return STORE_KEY_MAP.get(store_code, 'fs')


def create_crm_session(store_key='fs'):
    """
    创建带有CRM认证信息的session
    
    Args:
        store_key: 门店key，可选值：fs, zs, zh, hf, by
    
    Returns:
        requests.Session: 已配置好认证信息的session
    """
    session = requests.Session()
    
    # 获取CRM cookie
    cookies = get_crm_cookies(store_key)
    
    # 设置基础headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://crm.gzbbr.com/',
    })
    
    # 注入cookie认证信息
    session.headers.update(cookies)
    
    return session


def update_product_numbers(product_id, numbers, each_numbers="", store_code=None):
    """
    更新产品的替换号/OE号列表
    
    Args:
        product_id: 产品ID
        numbers: 替换号列表，如 ["A000000001119"]
        each_numbers: 已废弃，不再传给 CRM
        store_code: 门店代码，如 fsbbr, zs, zh等，不传则默认使用fs
    
    Returns:
        dict: API响应结果
    """
    # 根据门店代码获取key
    store_key = get_store_key(store_code) if store_code else 'fs'
    
    # 自动创建带认证的session
    session = create_crm_session(store_key)
    
    payload = {
        "product_id": str(product_id),
        "numbers": numbers
    }
    
    headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8',
        'origin': 'https://crm.gzbbr.com',
        'referer': 'https://crm.gzbbr.com/',
    }
    
    auth_token = session.headers.get('authorization')
    if auth_token:
        headers['authorization'] = auth_token
    
    response = session.post(UPDATE_NUMBER_URL, headers=headers, json=payload, timeout=30)
    return response.json()
