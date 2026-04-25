# -*- coding:utf-8 -*-
# @Time    : 2026/4/23 15:19
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : expected_unpaid_customers_services.py
# @Software: PyCharm

from datetime import datetime
from app.models.orm_models import AccountReceivableList
from app.utils.orm import orm_session


def get_overdue_unpaid_customers(page=1, limit=20, customer_name=None, level_name=None, payment_description=None):
    """
    查询：以今天为准，查看到期日过了，且没有给够钱的顾客数据
    条件：due_date < 今天 AND (tax_total_amount - received_amount) > 0
    
    :param page: 页码
    :param limit: 每页条数
    :param customer_name: 客户名称模糊查询
    :param level_name: 客户等级筛选
    :param payment_description: 付款说明筛选
    :return: {total: 总数, result: 客户列表}
    """
    page = int(page)
    limit = int(limit)
    
    # 生成今天的日期
    today = datetime.now().strftime('%Y-%m-%d')
    
    with orm_session() as session:
        return AccountReceivableList.get_overdue_unpaid_customers(session, page, limit, customer_name, level_name, payment_description, today)
