# -*- coding:utf-8 -*-
# @Time    : 2026/4/13
# @File    : wms_orders_test.py

from app.models.orm_models.wms_orders import WmsOrders
from app.utils.orm.session import orm_session


def test_get_by_id():
    """测试根据 ID 获取订单"""
    print("=" * 50)
    print("<UNK> ID <UNK>")
    with orm_session() as session:
        order = WmsOrders.get_by_id(session, 7)
        if order:
            print(f"[test_get_by_id] 订单编号: {order.order_no}, 客户: {order.customer}")
        else:
            print("[test_get_by_id] 未找到订单")
    print("=" * 50)

def test_get_by_order_no():
    """测试根据订单编号获取订单"""
    print("=" * 50)
    print("[test_get_by_order_no] <UNK>")
    with orm_session() as session:
        order = WmsOrders.get_by_order_no(session, "XSDD002202602230018")
        if order:
            print(f"[test_get_by_order_no] 订单ID: {order.id}, 状态: {order.status}")
        else:
            print("[test_get_by_order_no] 未找到订单")
    print("=" * 50)


def test_get_by_out_nos():
    """测试根据 out_no 数组获取多条数据"""
    print("=" * 50)
    print("[test_get_by_out_nos] <UNK>")
    with orm_session() as session:
        out_no_list = ["CK0201026022610355792", "CK0201226022612464833", "CK0200726022612460703"]
        orders = WmsOrders.get_by_out_nos(session, out_no_list)
        print(f"[test_get_by_out_nos] 查询到 {len(orders)} 条订单")
        for order in orders:
            print(f"  订单编号: {order.order_no}, 出库单号: {order.out_no}")
    print("=" * 50)

def test_to_dict():
    """测试 to_dict 方法"""
    print("="*50)
    print("[test_to_dict] <UNK>")
    with orm_session() as session:
        order = WmsOrders.get_by_id(session, 7)
        if order:
            order_dict = order.to_dict()
            print(f"[test_to_dict] 转换后的字典: {order_dict}")
            print(f"[test_to_dict] 订单编号: {order_dict.get('order_no')}")
        else:
            print("[test_to_dict] 未找到订单")
    print("=" * 50)

if __name__ == "__main__":
    print("开始测试 WmsOrders ORM 模型...\n")
    
    test_get_by_id()
    print()
    
    test_get_by_order_no()
    print()
    
    test_get_by_out_nos()
    print()
    
    test_to_dict()
    print()
    
    print("测试完成!")
