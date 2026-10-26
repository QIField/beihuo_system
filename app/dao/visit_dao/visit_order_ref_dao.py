# -*- coding:utf-8 -*-
# @Time    : 2026/10/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_order_ref_dao.py
# """
# 客访-订单与拜访关联表（visit_order_ref）数据访问层
#
# 职责：
# 1. 幂等建表（对应 sql/visit/visit_order_ref.sql）
# 2. 按 orders_id / record_id 批量查询（M5 订单列表 / M4 拜访时间轴展示装配）
# 3. 关联写入（指定插入 / 改绑覆盖）与取消（物理删除，05 文档第三节）
#
# 设计文档：doc/客访管理/05-订单拜访关联模块设计.md
# """

from app.models.orm_models.base_models import BaseModels
from app.models.orm_models.visit.visit_order_ref import VisitOrderRef
from app.utils.orm.session import get_engine

# 建表幂等标记（每进程只执行一次）
_table_ensured = False


def ensure_table():
    """幂等建表（IF NOT EXISTS），每进程只执行一次。"""
    global _table_ensured
    if _table_ensured:
        return
    BaseModels.metadata.create_all(get_engine(), tables=[VisitOrderRef.__table__])
    _table_ensured = True


def get_by_orders_id(session, orders_id):
    """
    按发货金蝶号查询关联行（改绑覆盖 / 取消删除定位）

    :param session: SQLAlchemy Session 对象
    :param orders_id: 发货金蝶号（sales_order_history.deliverysapno）
    :return: VisitOrderRef 或 None
    """
    return session.query(VisitOrderRef).filter(VisitOrderRef.orders_id == orders_id).first()


def get_map_by_orders_ids(session, orders_ids):
    """
    按发货金蝶号集合批量查询（M5 订单列表"关联拜访"列装配）

    :param session: SQLAlchemy Session 对象
    :param orders_ids: 发货金蝶号列表（当前页订单）
    :return: dict {orders_id: VisitOrderRef}
    """
    if not orders_ids:
        return {}
    rows = session.query(VisitOrderRef).filter(VisitOrderRef.orders_id.in_(orders_ids)).all()
    return {r.orders_id: r for r in rows}


def get_map_by_record_ids(session, record_ids):
    """
    按拜访记录ID集合批量查询（M4 拜访时间轴"已转化订单"标签装配）

    :param session: SQLAlchemy Session 对象
    :param record_ids: 拜访记录ID列表（当前页拜访）
    :return: dict {record_id: [VisitOrderRef, ...]}（一次拜访关联多张订单，1:N）
    """
    if not record_ids:
        return {}
    rows = session.query(VisitOrderRef).filter(VisitOrderRef.record_id.in_(record_ids)).all()
    ref_map = {}
    for r in rows:
        ref_map.setdefault(r.record_id, []).append(r)
    return ref_map


def upsert_link(session, orders_id, record_id, matched_by, remarks=None):
    """
    指定 / 改绑（不 commit，事务提交由服务层统一控制）

    无行 → 插入；已有行（改绑）→ 覆盖 record_id / matched_by / remarks（uk_orders_id 保证至多一行）。

    :param session: SQLAlchemy Session 对象
    :param orders_id: 发货金蝶号
    :param record_id: 关联拜访记录ID
    :param matched_by: 操作人（登录用户名）
    :param remarks: 关联备注，选填
    :return: VisitOrderRef 关联行对象
    """
    row = get_by_orders_id(session, orders_id)
    if row:
        row.record_id = record_id
        row.matched_by = matched_by
        row.remarks = remarks or None
    else:
        row = VisitOrderRef(
            orders_id=orders_id,
            record_id=record_id,
            matched_by=matched_by,
            remarks=remarks or None,
        )
        session.add(row)
    session.flush()
    return row


def delete_by_orders_id(session, orders_id):
    """
    取消关联 = 物理删除该行（业务确认 2026-10-24，不保留取消痕迹）

    :param session: SQLAlchemy Session 对象
    :param orders_id: 发货金蝶号
    :return: 删除行数（0=该订单本无关联）
    """
    return session.query(VisitOrderRef).filter(VisitOrderRef.orders_id == orders_id).delete()
