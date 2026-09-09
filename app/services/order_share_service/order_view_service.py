# -*- coding:utf-8 -*-
# @Time    : 2026/09/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : order_view_service.py
# @Software: trae-cn

"""
订单分享页面数据服务

职责：根据订单号（明文）获取订单物流状态视图，供公开页面渲染。
当前实现：调用 order_status_service，走 CRM 实时查询 + 本地状态缓存。
"""

from app.services.order_share_service.order_status_service import get_order_status_view


def get_order_basic_by_no(order_no):
    """
    按订单号查询订单信息（对客页面用）

    :param order_no: 订单号（明文）
    :return: 页面展示字段字典；查不到返回 None
    """
    return get_order_status_view(order_no)
