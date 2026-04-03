# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 16:01
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_orders_raw_test.py
# @Software: PyCharm


# 示例1：创建新订单
from app.models.raw_sql_models.wms_orders_raw import WmsOrders
from datetime import datetime



# 示例2：根据ID获取订单
order = WmsOrders.get_by_id(7)
if order:
    print(f"订单编号: {order.order_no}, 客户: {order.customer}")

# 示例3：根据订单编号获取订单
order = WmsOrders.get_by_order_no("XSDD002202602230019")
if order:
    print(f"订单ID: {order.id}, 状态: {order.status}")



# 示例5：根据 out_no 数组获取多条数据
out_no_list = ["CK0200726022317015775", "CK0201026022409235749", "CK0258026022609371798"]
orders = WmsOrders.get_by_out_nos(out_no_list)
for order in orders:
    print(f"订单编号: {order.order_no}, 外部订单号: {order.out_no}")

