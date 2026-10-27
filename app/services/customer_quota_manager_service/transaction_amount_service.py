# -*- coding:utf-8 -*-
# @Time    : 2026/4/20 18:33
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : transaction_amount.py
# @Software: PyCharm
# 数据源说明：2026-10-22 起从旧表 merge_order_list（每周二全量，已停更）切换到
# crm_sales_order（每日 02:00 全量 + 看板心跳增量）；旧表数据与 ORM 模型保留但不再读取。
from app.dao.crm import crm_sales_order_dao
from app.utils.common_util_module.time_conversion_util import get_border_month_timestamp
from app.utils.orm import orm_session


def time_transaction_sum(page,limit,
                         start_month=None, end_month=None,
                         customer_name=None,
                         level_id=None,
                         payment_description=None,
                         total_price_min=None,
                         total_price_max=None
                         ):
    start_time=None
    end_time=None
    page=int(page)
    limit=int(limit)

    if not ((not start_month or start_month.isspace()) and (not end_month or end_month.isspace())):
        start_month = int(start_month)
        end_month = int(end_month)
        start_time, end_time = get_border_month_timestamp((start_month, end_month))

    # 客户名称为空字符串或者为空格时，不查询客户名称
    if not customer_name or customer_name.isspace():
        customer_name=None
    
    if not level_id or level_id.isspace():
        level_id = None
    else:
        level_id = int(level_id)

    if not payment_description or payment_description.isspace():
      payment_description = None

    if not total_price_min or total_price_min.isspace():
        total_price_min = None
    else:
        total_price_min = float(total_price_min)

    if not total_price_max or total_price_max.isspace():
        total_price_max = None
    else:
        total_price_max = float(total_price_max)

    with orm_session() as session:
        # DAO 内已返回 (总数, 字典列表)，Decimal 已转 float
        total, result = crm_sales_order_dao.get_customer_total_price_sum(
            session,
            page=page,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
            customer_name=customer_name,
            level_id= level_id,
            payment_description= payment_description,
            total_price_min=total_price_min,
            total_price_max=total_price_max
        )

        data={
            "total": total,
            "result": result
        }

        return data

