# -*- coding: utf-8 -*-
"""
库存任务模块
包含黑名单管理和上传过滤功能
"""

from .blacklist_manager import (
    init_blacklist_table,
    add_to_blacklist,
    remove_from_blacklist,
    get_blacklist,
    batch_add_to_blacklist,
    clear_blacklist,
    is_in_blacklist
)

from .upload_filter import (
    load_blacklist_to_memory,
    filter_by_blacklist,
    get_filter_stats,
    refresh_blacklist_cache,
    is_in_blacklist_memory
)

__all__ = [
    # 黑名单管理
    'init_blacklist_table',
    'add_to_blacklist',
    'remove_from_blacklist',
    'get_blacklist',
    'batch_add_to_blacklist',
    'clear_blacklist',
    'is_in_blacklist',
    # 上传过滤
    'load_blacklist_to_memory',
    'filter_by_blacklist',
    'get_filter_stats',
    'refresh_blacklist_cache',
    'is_in_blacklist_memory',
]
