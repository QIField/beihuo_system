# -*- coding:utf-8 -*-
# @Time    : 2026/7/10
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm
# @Desc    : WMS 采购入库单明细同步服务包

from .return_items_detail_service import sync_wms_return_items_detail

__all__ = ['sync_wms_return_items_detail']
