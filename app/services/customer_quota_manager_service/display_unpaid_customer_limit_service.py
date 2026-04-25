# -*- coding:utf-8 -*-
# @Time    : 2026/4/24 15:49
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : display_unpaid_customer_limit_service.py
# @Software: PyCharm

from datetime import datetime
from app.models.orm_models import AccountReceivableList
from app.utils.orm import orm_session


def get_overdue_unpaid_customers_with_quota(page=1, limit=20, customer_name=None, level_name=None, payment_description=None, quota_status=None):
    """
    查询：以今天为准，查看到期日过了，且没有给够钱的顾客数据，并关联客户授信总额度
    条件：due_date < 今天 AND (tax_total_amount - received_amount) > 0
    
    :param page: 页码
    :param limit: 每页条数
    :param customer_name: 客户名称模糊查询
    :param level_name: 客户等级筛选
    :param payment_description: 付款说明筛选
    :param quota_status: 授信额度状态筛选：exhausted-已用尽，available-未用尽
    :return: {total: 总数, result: 客户列表}
    """
    page = int(page)
    limit = int(limit)
    
    # 生成今天的日期
    today = datetime.now().strftime('%Y-%m-%d')
    
    with orm_session() as session:
        return AccountReceivableList.get_overdue_unpaid_customers_with_quota(
            session, page, limit, customer_name, level_name, payment_description, quota_status, today
        )


def get_receipts_by_customer_code(customer_code, page=1, limit=20, payment_status=None):
    """
    根据客户编码分页获取应收单列表
    
    :param customer_code: 客户编码
    :param page: 页码
    :param limit: 每页条数
    :param payment_status: 付款状态：'unpaid' 未结清，'paid' 已结清，None 全部
    :return: {total: 总数, result: 数据列表}
    """
    page = int(page)
    limit = int(limit)
    
    with orm_session() as session:
        return AccountReceivableList.get_paginated_by_customer_code(
            session, customer_code, page, limit, payment_status
        )
