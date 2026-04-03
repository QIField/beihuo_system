# -*- coding:utf-8 -*-
# @Time    : 2026/3/30 16:48
# @Author  : xingkongtub
# @Project : overall_project
# @File    : wms_orders.py
# @Software: PyCharm
from app.models.raw_sql_models.wms_orders_raw import WmsOrders


def get_orders_by_out_nos(out_no_list):
    # 核心 SQL：SELECT * FROM wms_orders WHERE out_no IN (...)
    # orders = WmsOrders.query.filter(
    #     WmsOrders.out_no.in_(out_no_list)
    # ).all()

    orders = WmsOrders.get_by_out_nos(out_no_list)

    return orders

