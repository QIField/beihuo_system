# -*- coding:utf-8 -*-
"""
WMS 库存操作推送服务 - 通用工具函数
"""

from typing import Any, Optional


def _safe_int(value: Any) -> Optional[int]:
    """安全转换为整数，失败返回 None"""
    if value is None or value == '':
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _safe_decimal(value: Any) -> Optional[float]:
    """安全转换为浮点数，失败返回 None"""
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _is_not_empty(value: Any) -> bool:
    """判断字段是否为非空值"""
    if value is None:
        return False
    return bool(str(value).strip())
