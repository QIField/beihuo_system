# -*- coding:utf-8 -*-
# @Time    : 2026/10/28 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_customer_owner_dao.py
# @Software: PyCharm
"""
客访-高德客户负责人关联表（visit_customer_owner）数据访问层

职责：
1. 幂等建表（对应 sql/visit/visit_customer_owner.sql）
2. 负责人绑定行查询（按客户正查 / 按负责人反查）/ 批量查询（列表页负责人列）
3. 绑定行插入 / 物理删除（解绑）

关系为多对多：一条高德客户可绑定多个负责人，一个负责人可负责多条高德客户；
只存当前有效关系，解绑即物理删除该行、不留历史。

设计文档：doc/客访管理/07-负责人绑定.md
"""

from app.models.orm_models.base_models import BaseModels
from app.models.orm_models.visit.visit_customer_owner import VisitCustomerOwner
from app.utils.orm.session import get_engine

# 建表幂等标记（每进程只执行一次）
_table_ensured = False


def ensure_table():
    """幂等建表（IF NOT EXISTS），每进程只执行一次。"""
    global _table_ensured
    if _table_ensured:
        return
    BaseModels.metadata.create_all(get_engine(), tables=[VisitCustomerOwner.__table__])
    _table_ensured = True


def list_by_customer_id(session, visit_amap_customer_id):
    """
    按客户物理主键查询全部负责人绑定行（多对多，可能多条）

    :param session: SQLAlchemy Session 对象
    :param visit_amap_customer_id: visit_amap_customer.id（物理主键）
    :return: VisitCustomerOwner 对象列表（按绑定时间倒序）
    """
    return session.query(VisitCustomerOwner).filter(
        VisitCustomerOwner.visit_amap_customer_id == visit_amap_customer_id).order_by(
        VisitCustomerOwner.created_at.desc(), VisitCustomerOwner.id.desc()).all()


def list_by_customer_ids(session, customer_ids, chunk_size=500):
    """
    按客户物理主键集合批量查询绑定行（客户列表页负责人列，uk_customer_user 最左前缀）

    :param session: SQLAlchemy Session 对象
    :param customer_ids: visit_amap_customer.id 列表
    :param chunk_size: 分批 IN 查询大小
    :return: VisitCustomerOwner 对象列表
    """
    rows = []
    customer_ids = [c for c in customer_ids if c]
    for i in range(0, len(customer_ids), chunk_size):
        chunk = customer_ids[i:i + chunk_size]
        rows.extend(session.query(VisitCustomerOwner).filter(
            VisitCustomerOwner.visit_amap_customer_id.in_(chunk)).all())
    return rows


def list_by_user_id(session, user_id):
    """
    按负责人ID反查其负责的客户绑定行（idx_user_id，后续数据权限基础）

    :param session: SQLAlchemy Session 对象
    :param user_id: 负责人ID（crmapp_users.id）
    :return: VisitCustomerOwner 对象列表
    """
    return session.query(VisitCustomerOwner).filter(
        VisitCustomerOwner.user_id == user_id).order_by(
        VisitCustomerOwner.created_at.desc(), VisitCustomerOwner.id.desc()).all()


def get_by_customer_and_user(session, visit_amap_customer_id, user_id):
    """
    按（客户物理主键, 负责人ID）同一对查询绑定行（重复绑定幂等判断用）

    :param session: SQLAlchemy Session 对象
    :param visit_amap_customer_id: visit_amap_customer.id（物理主键）
    :param user_id: 负责人ID（crmapp_users.id）
    :return: VisitCustomerOwner 或 None
    """
    return session.query(VisitCustomerOwner).filter(
        VisitCustomerOwner.visit_amap_customer_id == visit_amap_customer_id,
        VisitCustomerOwner.user_id == user_id).first()


def insert_owner(session, visit_amap_customer_id, user_id, operator):
    """
    插入绑定行（不 commit，事务提交由服务层统一控制）

    同一对（客户+负责人）由 uk_customer_user 唯一键兜底并发，
    Duplicate entry 由服务层捕获后按幂等成功处理。

    :param session: SQLAlchemy Session 对象
    :param visit_amap_customer_id: visit_amap_customer.id（物理主键）
    :param user_id: 负责人ID（crmapp_users.id）
    :param operator: 操作用户id（当前登录用户）
    :return: VisitCustomerOwner 绑定行对象
    """
    row = VisitCustomerOwner(
        visit_amap_customer_id=visit_amap_customer_id,
        user_id=user_id,
        operator=operator,
    )
    session.add(row)
    session.flush()
    return row


def delete_owner(session, visit_amap_customer_id, user_id):
    """
    删除指定绑定行（解绑 = 物理删除，不 commit，事务提交由服务层统一控制）

    :param session: SQLAlchemy Session 对象
    :param visit_amap_customer_id: visit_amap_customer.id（物理主键）
    :param user_id: 负责人ID（crmapp_users.id）
    :return: 是否删除了绑定行
    """
    deleted = session.query(VisitCustomerOwner).filter(
        VisitCustomerOwner.visit_amap_customer_id == visit_amap_customer_id,
        VisitCustomerOwner.user_id == user_id).delete()
    return deleted > 0
