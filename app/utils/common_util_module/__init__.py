# -*- coding:utf-8 -*-
# @Time    : 2026/4/16
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm

"""
common_util_module - 公共工具模块统一入口

对外推荐使用以下方式导入:
    from app.utils.common_util_module import Cache, get_default_cache, cache_function_result
    from app.utils.common_util_module import get_month_timestamp, timestamp_to_str
"""

# ============================================================
# 时间工具
# ============================================================
from app.utils.common_util_module.time_conversion_util import (
    get_month_timestamp,
    get_day_timestamp,
    get_timestamp_from_str,
    timestamp_to_str,
    get_relative_month_timestamp,
    get_border_month_timestamp,
)

# ============================================================
# 缓存工具
# ============================================================


__all__ = [
    # 时间工具
    "get_month_timestamp",
    "get_day_timestamp",
    "get_timestamp_from_str",
    "timestamp_to_str",
    "get_relative_month_timestamp",
    "get_border_month_timestamp",
    # 缓存工具

]
