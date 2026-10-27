# -*- coding:utf-8 -*-
# @Time    : 2026/10/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_order_ref.py
# 客访-订单与拜访关联表 ORM 模型

from sqlalchemy import Column, String, DateTime, BigInteger, UniqueConstraint, func, text

from ..base_models import BaseModels


class VisitOrderRef(BaseModels):
    """
    对应数据库表：visit_order_ref（设计文档 doc/客访管理/05-订单拜访关联模块设计.md 第二节）
    一次拜访关联多张订单（1:N）；一张订单最多一条关联行（uk_orders_id，M5"关联拜访"列单值展示前提）。
    orders_id 存发货金蝶号（sales_order_history.deliverysapno，业务确认一单一号且不空）；
    纯人工维护（无自动匹配），取消 = 物理删除，改绑 = 覆盖同一行 record_id/matched_by/remarks。
    数据库操作见 app/dao/visit_dao/visit_order_ref_dao.py
    """

    __tablename__ = "visit_order_ref"

    __table_args__ = (
        UniqueConstraint("orders_id", name="uk_orders_id"),
        {"comment": "客访-订单与拜访关联表(一次拜访关联多张订单,纯人工维护)"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键，自增")
    orders_id = Column(String(255), nullable=False,
                       comment="订单标识=发货金蝶号（sales_order_history.deliverysapno）")
    record_id = Column(BigInteger, nullable=False, comment="关联拜访记录ID → visit_record.id")
    matched_by = Column(String(50), nullable=False, comment="操作人（登录用户名）")
    remarks = Column(String(255), comment="关联备注（改绑原因、归属说明）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                        comment="更新时间")
