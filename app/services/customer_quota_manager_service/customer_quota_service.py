# -*- coding:utf-8 -*-
# @Time    : 2026/4/24 09:45
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : customer_quota_service.py
# @Software: PyCharm

from app.models.orm_models import CustomerQuota
from app.utils.orm import orm_session


def get_customer_quota_list(page, limit, fullname=None, quota_status=None):
    """
    获取客户额度列表
    
    :param page: 页码
    :param limit: 每页条数
    :param fullname: 客户名称（可选，模糊查询）
    :param quota_status: 额度状态（可选）
    :return: {total: 总数, result: 数据列表}
    """
    page = int(page)
    limit = int(limit)
    
    # 客户名称为空字符串或者为空格时，不查询
    if not fullname or fullname.isspace():
        fullname = None
    
    # 额度状态为空字符串或者为空格时，不查询
    if not quota_status or quota_status.isspace():
        quota_status = None
    
    with orm_session() as session:
        total, result = CustomerQuota.get_paginated_list(
            session,
            page=page,
            limit=limit,
            fullname=fullname,
            quota_status=quota_status
        )
        
        result = CustomerQuota.list_to_dict_list(result)
        
        data = {
            "total": total,
            "result": result
        }
        
        return data


def get_customer_quota_by_id(id):
    """
    根据 ID 获取客户额度记录
    
    :param id: 主键 ID
    :return: CustomerQuota 字典或 None
    """
    with orm_session() as session:
        obj = CustomerQuota.get_by_id(session, id)
        return obj.to_dict() if obj else None


def update_customer_quota(id, data):
    """
    更新客户额度记录
    
    :param id: 主键 ID
    :param data: 更新数据字典
    :return: 更新后的 CustomerQuota 字典或 None
    """
    with orm_session() as session:
        obj = CustomerQuota.update(session, id, data)
        if obj:
            session.commit()
            return obj.to_dict()
        return None
