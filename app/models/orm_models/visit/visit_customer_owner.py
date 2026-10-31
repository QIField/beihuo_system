# -*- coding:utf-8 -*-
# @Time    : 2026/10/28 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_customer_owner.py
# @Software: PyCharm

from sqlalchemy import Column, DateTime, Integer, func, text

from ..base_models import BaseModels


class VisitCustomerOwner(BaseModels):
    """
    客访-高德客户负责人关联表 ORM 模型

    对应数据库表：visit_customer_owner（设计文档 doc/客访管理/07-负责人绑定.md）
    负责人（crmapp_users 系统用户）与高德客户（visit_amap_customer）多对多绑定：
    一条高德客户可绑定多个负责人，一个负责人可负责多条高德客户。
    只存当前有效关系，解绑即物理删除该行、不留历史；
    uk_customer_user 唯一键保证同一对（客户+负责人）不重复绑定。
    数据库操作见 app/dao/visit_dao/visit_customer_owner_dao.py
    """

    __tablename__ = "visit_customer_owner"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键，自增")
    visit_amap_customer_id = Column(Integer, nullable=False, comment="visit_amap_customer.id")
    user_id = Column(Integer, nullable=False, comment="负责人ID → crmapp_users.id")
    operator = Column(Integer, nullable=False, comment="操作用户id")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间，默认当前时间（即绑定时间）")
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                        comment="更新时间，默认当前时间并随更新自动变更")

    def __repr__(self):
        return f"<VisitCustomerOwner visit_amap_customer_id={self.visit_amap_customer_id} user_id={self.user_id}>"
