"""
备货数据服务模块

提供备货数据的更新和拉取功能，支持手动和自动两种模式。
"""

from .sync_service import (
    update_company,
    update_all_companies,
    fetch_company,
    fetch_all_companies,
    update_then_fetch_all,
)

__all__ = [
    'update_company',
    'update_all_companies',
    'fetch_company',
    'fetch_all_companies',
    'update_then_fetch_all',
]
