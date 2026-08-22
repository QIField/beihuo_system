# -*- coding:utf-8 -*-
"""
导出数据提供者

按页面拆分的导出数据查询与配置模块，每个提供者负责一个页面的导出行为。
"""

from .beihuo_provider import BEIHUO_EXPORT_CONFIG, fetch_beihuo_data
from .cart_provider import CART_EXPORT_CONFIG, fetch_cart_data
from .date_query_provider import DATE_QUERY_EXPORT_CONFIG, fetch_date_query_data

__all__ = [
    'BEIHUO_EXPORT_CONFIG',
    'fetch_beihuo_data',
    'CART_EXPORT_CONFIG',
    'fetch_cart_data',
    'DATE_QUERY_EXPORT_CONFIG',
    'fetch_date_query_data',
]
