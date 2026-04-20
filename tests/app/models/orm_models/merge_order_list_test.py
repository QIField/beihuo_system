# -*- coding:utf-8 -*-
# @Time    : 2026/4/16 16:25
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : merge_order_list_test.py
# @Software: PyCharm
from app.models.orm_models import MergeOrderList
from app.utils.orm import orm_session


def test_order_stat():
    # 1. 测试1：只传分页，不传任何筛选条件（查全部）
    print("=== 测试1：不传筛选条件 ===")
    with orm_session() as session:
        res1, total1 = MergeOrderList.get_customer_total_price_sum(
            session,
            page=1,
            limit=10,
            start_time=None,
            end_time=None,
            customer_name=None
        )
        print("=" * 100)
        print(f"总条数：{total1}，当前页条数：{len(res1)}")
        for item in res1:
            print(f"{item.order_count}    {item.total_price_sum}    {item.level_id}    {item.level_name}")
        print("="*100)

        # 2. 测试2：只传时间范围
        print("\n=== 测试2：只传时间 ===")
        res2, total2 = MergeOrderList.get_customer_total_price_sum(
            session,
            page=1,
            limit=10,
            start_time=1769875200,
            end_time=1772294399,
            customer_name=None
        )
        print("=" * 100)
        print(f"总条数：{total2}，当前页条数：{len(res2)}")
        for item in res2:
            print(f"{item.order_count}    {item.total_price_sum}    {item.level_id}    {item.level_name}")
        print("="*100)
        # 3. 测试3：传时间 + 客户
        print("\n=== 测试3：时间+客户 ===")
        res3, total3 = MergeOrderList.get_customer_total_price_sum(
            session,
            page=1,
            limit=10,
            start_time=1769875200,
            end_time=1772294399,
            customer_name="GZ途虎养车"
        )
        print("=" * 100)
        print(f"总条数：{total3}，当前页条数：{len(res3)}")
        for item in res3:
            print(f"{item.order_count}    {item.total_price_sum}    {item.level_id}    {item.level_name}")
        print("=" * 100)
if __name__ == '__main__':
    test_order_stat()