# -*- coding:utf-8 -*-
# @Time    : 2026/10/13 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_customer_relation_dao.py
# @Software: PyCharm
"""
客访-高德客户与CRM客户关联表（visit_customer_relation）数据访问层

职责：
1. 幂等建表（对应 sql/visit/visit_customer_relation.sql）
2. 绑定行查询 / 插入或更新（upsert，按 amap_customer_id + partner_id 同一对幂等）
3. 绑定表单的 CRM 客户搜索（partner_list，排除已绑定与禁用客户）

绑定关系为 1:N：一条高德客户可绑定多条CRM客户（amap_customer_id 普通索引），
一条CRM客户仅归属一个高德客户（uk_partner_id 唯一键兜底）。

设计文档：doc/客访管理/03-高德客户档案与客户绑定模块设计.md
"""

from sqlalchemy import or_, not_

from app.models.orm_models.base_models import BaseModels
from app.models.orm_models.crm.partner_list import PartnerList
from app.models.orm_models.visit.visit_customer_relation import VisitCustomerRelation
from app.utils.orm.session import get_engine

# 建表幂等标记（每进程只执行一次）
_table_ensured = False


def ensure_table():
    """幂等建表（IF NOT EXISTS），每进程只执行一次。"""
    global _table_ensured
    if _table_ensured:
        return
    BaseModels.metadata.create_all(get_engine(), tables=[VisitCustomerRelation.__table__])
    _table_ensured = True


def list_by_amap_customer_id(session, amap_customer_id):
    """
    按高德客户POI编码查询全部当前绑定行（1:N，可能多条）

    :param session: SQLAlchemy Session 对象
    :param amap_customer_id: 高德客户POI编码（visit_amap_customer.amap_poi_id）
    :return: VisitCustomerRelation 对象列表（按绑定时间倒序）
    """
    return session.query(VisitCustomerRelation).filter(
        VisitCustomerRelation.amap_customer_id == amap_customer_id).order_by(
        VisitCustomerRelation.created_at.desc(), VisitCustomerRelation.id.desc()).all()


def get_by_amap_and_partner(session, amap_customer_id, partner_id):
    """
    按（高德客户POI编码, CRM客户ID）同一对查询绑定行（重复绑定幂等 upsert 用）

    :param session: SQLAlchemy Session 对象
    :param amap_customer_id: 高德客户POI编码（visit_amap_customer.amap_poi_id）
    :param partner_id: CRM客户ID（partner_list.partner_id）
    :return: VisitCustomerRelation 或 None
    """
    return session.query(VisitCustomerRelation).filter(
        VisitCustomerRelation.amap_customer_id == amap_customer_id,
        VisitCustomerRelation.partner_id == partner_id).first()


def get_by_partner_id(session, partner_id):
    """
    按CRM客户ID查询当前绑定行（绑定前冲突预检：CRM侧 1:1，uk_partner_id 兜底）

    :param session: SQLAlchemy Session 对象
    :param partner_id: CRM客户ID（partner_list.partner_id）
    :return: VisitCustomerRelation 或 None
    """
    return session.query(VisitCustomerRelation).filter(
        VisitCustomerRelation.partner_id == partner_id).first()


def delete_relation(session, amap_customer_id, partner_id):
    """
    删除指定绑定行（解绑 = 物理删除，不 commit，事务提交由服务层统一控制）

    :param session: SQLAlchemy Session 对象
    :param amap_customer_id: 高德客户POI编码
    :param partner_id: CRM客户ID
    :return: 是否删除了绑定行
    """
    deleted = session.query(VisitCustomerRelation).filter(
        VisitCustomerRelation.amap_customer_id == amap_customer_id,
        VisitCustomerRelation.partner_id == partner_id).delete()
    return deleted > 0


def upsert_relation(session, amap_customer_id, partner_id, last_operator, bind_remark=""):
    """
    插入或更新绑定行（不 commit，事务提交由服务层统一控制）

    同一对（amap_customer_id, partner_id）已存在绑定行则更新操作人/备注（重复绑定幂等），
    否则插入新行（一条高德客户可绑定多条CRM客户，1:N 追加式）。

    :param session: SQLAlchemy Session 对象
    :param amap_customer_id: 高德客户POI编码
    :param partner_id: CRM客户ID
    :param last_operator: 最后操作人（绑定人）
    :param bind_remark: 绑定备注（名称差异说明）
    :return: VisitCustomerRelation 绑定行对象
    """
    row = get_by_amap_and_partner(session, amap_customer_id, partner_id)
    if row:
        row.last_operator = last_operator
        row.bind_remark = bind_remark or None
    else:
        row = VisitCustomerRelation(
            amap_customer_id=amap_customer_id,
            partner_id=partner_id,
            last_operator=last_operator,
            bind_remark=bind_remark or None,
        )
        session.add(row)
    session.flush()
    return row


def search_crm_partners(session, keyword, limit=20):
    """
    绑定表单的 CRM 客户搜索（fullname/short_name/remenber_code 模糊匹配）

    排除：已绑定到其他高德客户的 CRM 客户（uk_partner_id 1:1）、已禁用客户。

    :param session: SQLAlchemy Session 对象
    :param keyword: 搜索关键词（客户名称/简称/记忆代码）
    :param limit: 返回条数上限
    :return: PartnerList 对象列表
    """
    kw = f"%{keyword}%"
    bound_ids = session.query(VisitCustomerRelation.partner_id)
    return session.query(PartnerList).filter(
        or_(
            PartnerList.fullname.like(kw),
            PartnerList.short_name.like(kw),
            PartnerList.remenber_code.like(kw),
        ),
        not_(PartnerList.partner_id.in_(bound_ids)),
        or_(PartnerList.is_disabled.is_(None), PartnerList.is_disabled == 0),
    ).order_by(PartnerList.fullname).limit(limit).all()
