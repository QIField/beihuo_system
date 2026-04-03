# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 16:24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_orders_test.py
# @Software: PyCharm
from app.services.dashboard_crm_wms_services.wms_orders import get_orders_by_out_nos

# 示例5：根据 out_no 数组获取多条数据
out_no_list = ["CK0200726022317015775", "CK0201026022409235749", "CK0258026022609371798"]
orders=get_orders_by_out_nos(out_no_list)
for order in orders:
    print(f"订单编号: {order.order_no}, 外部订单号: {order.out_no}")