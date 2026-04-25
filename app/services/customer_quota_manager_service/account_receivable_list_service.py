# -*- coding:utf-8 -*-
# @Time    : 2026/4/23 11:53
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : account_receivable_list_service.py
# @Software: PyCharm

from app.models.orm_models import AccountReceivableList
from app.utils.orm import orm_session


def get_account_receivable_list(page, limit, receipt_no=None, customer_name=None):
    """
    获取应收单列表
    
    :param page: 页码
    :param limit: 每页条数
    :param receipt_no: 单据编号（可选）
    :param customer_name: 客户名称（可选）
    :return: {total: 总数, result: 数据列表}
    """
    page = int(page)
    limit = int(limit)
    
    # 单据编号为空字符串或者为空格时，不查询单据编号
    if not receipt_no or receipt_no.isspace():
        receipt_no = None
    
    # 客户名称为空字符串或者为空格时，不查询客户名称
    if not customer_name or customer_name.isspace():
        customer_name = None
    
    with orm_session() as session:
        total, result = AccountReceivableList.get_paginated_list(
            session,
            page=page,
            limit=limit,
            receipt_no=receipt_no,
            customer_name=customer_name
        )
        
        result = AccountReceivableList.list_to_dict_list(result)
        
        data = {
            "total": total,
            "result": result
        }
        
        return data


def get_unpaid_customers(page=1, limit=20, customer_name=None, level_name=None, payment_description=None):
    """
    查询一：以 customer_code 分组，查看有多少客户没有给够钱
    条件：(tax_total_amount - received_amount) > 0
    
    :param page: 页码
    :param limit: 每页条数
    :param customer_name: 客户名称模糊查询
    :param level_name: 客户等级筛选
    :param payment_description: 付款说明筛选
    :return: {total: 总数, result: 客户列表}
    """
    page = int(page)
    limit = int(limit)
    
    with orm_session() as session:
        return AccountReceivableList.get_unpaid_customers(session, page, limit, customer_name, level_name, payment_description)
