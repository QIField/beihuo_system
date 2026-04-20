# -*- coding:utf-8 -*-
# @Time    : 2026/4/15 17:03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : v_customer_order_statistics_test.py
# @Software: PyCharm
from app.models.orm_models.v_customer_order_statistics import CustomerOrderStatistics
from app.utils.orm import orm_session



def test():
    with orm_session() as session:


        # 2. 带过滤条件（查询level_id=3的数据，第2页，每页10条）
        data_list, total = CustomerOrderStatistics.get_paged(
            session,
            page=2,
            limit=20,
        )

        # 4. 打印结果
        print(f"总条数：{total}")
        for i, data in enumerate(data_list,1):
            print(f"<UNK>{i}<UNK>{data}")
            print(f"   订单数量: {data.order_count}")
            print(f"   总金额: {data.total_price_sum}")
            print(f"   实付金额: {data.sfje_sum}")
            print(f"   客户等级: {data.level_name}")




def decs_test():
    with orm_session() as session:
        data_list,total = CustomerOrderStatistics.get_paged(
            session,
            page=2,
            limit=10,
            # 多字段排序：先id，再name
            order_by=["level_id","total_price_sum"],
            # 对应排序：id降序，name升序
            desc=[True, True]
        )

        for i, data in enumerate(data_list,1):
            print(f"<UNK>{i}<UNK>{data}")
            print(f" {data.order_count}    {data.total_price_sum}    {data.level_id}    {data.level_name}")

        print("="*100)
        # 老用法：单字段排序，完美兼容
        data_list2, total2 = CustomerOrderStatistics.get_paged(
            session,
            page=2,
            limit=10,
            order_by="order_count",
            desc=True
        )

        for i, data in enumerate(data_list2, 1):
            print(f"<UNK>{i}<UNK>{data}")
            print(f" {data.order_count}    {data.total_price_sum}     {data.level_id}    {data.level_name}")


def time_test():
    with orm_session() as session:
        data_list, total = CustomerOrderStatistics.get_paged(
            session,
            page=1,
            limit=100,
            level_id=22
        )
        print(f"<UNK>{total}")
        for i, data in enumerate(data_list,1):
            print(f"<UNK>{i}<UNK>{data}")
            print(f" {data.order_count}    {data.total_price_sum}     {data.level_id}    {data.level_name}")

if __name__ == '__main__':

    # test()

    time_test()

