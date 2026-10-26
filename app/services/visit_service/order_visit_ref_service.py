# -*- coding:utf-8 -*-
# @Time    : 2026/10/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : order_visit_ref_service.py
# 客访-订单拜访关联服务（05-订单拜访关联模块设计.md）
# 接口层见 app/api/visit/visit_api.py（PUT / DELETE /new/api/visit/order-refs）；
# 纯人工维护（无自动匹配，业务确认 2026-10-24）：一次拜访关联多张订单（1:N），
# 一张订单最多一条关联行（uk_orders_id），取消 = 物理删除。
# 关联锚点 = 发货金蝶号（sales_order_history.deliverysapno，业务确认一单一号且不空）。
# 展示装配（查询侧，按页批量）：
#   build_visit_ref_map   → M5 拿货订单列表"关联拜访"列（customer_order_service）；
#   build_converted_map   → M4 拜访时间轴"已转化订单"标签（visit_record_service）。

from app.dao.visit_dao import visit_customer_relation_dao, visit_order_ref_dao
from app.models.orm_models.crm.sales_order_history import SalesOrderHistory
from app.models.orm_models.visit.visit_order_ref import VisitOrderRef
from app.models.orm_models.visit.visit_record import VisitRecord
from app.utils.orm.session import orm_session


def _fmt_visit_time(dt):
    """datetime → 'YYYY-MM-DD HH:MM'（空返回 None）"""
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def build_visit_ref_map(session, orders_ids):
    """
    M5 装配：发货金蝶号集合 → "关联拜访"展示数据（INVALID 拜访视为无关联）

    INNER JOIN visit_record（status=1）：拜访作废后的悬空关联行展示层兜底显示"无"
    （05 文档级联说明：作废接口落地时须同步级联删除关联行）。

    :param session: SQLAlchemy Session 对象
    :param orders_ids: 发货金蝶号列表（当前页订单）
    :return: dict {orders_id: {'recordId', 'visitTime', 'recorder'}}
    """
    visit_order_ref_dao.ensure_table()
    if not orders_ids:
        return {}
    rows = session.query(
        VisitOrderRef.orders_id,
        VisitOrderRef.record_id,
        VisitRecord.visit_time,
        VisitRecord.recorder,
    ).join(
        VisitRecord,
        (VisitRecord.id == VisitOrderRef.record_id) & (VisitRecord.status == 1),
    ).filter(
        VisitOrderRef.orders_id.in_(orders_ids),
    ).all()
    return {
        r.orders_id: {
            "recordId": r.record_id,
            "visitTime": _fmt_visit_time(r.visit_time),
            "recorder": r.recorder,
        }
        for r in rows
    }


def build_converted_map(session, record_ids):
    """
    M4 装配：拜访记录ID集合 → 关联订单号列表（orders_id 字段自带，无需回查订单表）

    :param session: SQLAlchemy Session 对象
    :param record_ids: 拜访记录ID列表（当前页拜访）
    :return: dict {record_id: [发货金蝶号, ...]}
    """
    visit_order_ref_dao.ensure_table()
    if not record_ids:
        return {}
    rows = session.query(
        VisitOrderRef.record_id,
        VisitOrderRef.orders_id,
    ).filter(
        VisitOrderRef.record_id.in_(record_ids),
    ).all()
    converted = {}
    for r in rows:
        converted.setdefault(r.record_id, []).append(r.orders_id)
    return converted


def bind_order_visit(orders_id, record_id, remarks="", operator=""):
    """
    指定 / 改绑（05 文档第三节：无行插入 / 有行覆盖 record_id、matched_by、remarks）

    校验：
      1. orders_id（发货金蝶号）非空，且在 sales_order_history 中存在；
      2. record_id 对应拜访存在且 status=1；
      3. 订单所属 CRM 客户 ∈ 该拜访客户当前绑定的 partner_ids 集合（防跨客户错挂）。

    :param orders_id: 发货金蝶号
    :param record_id: 关联拜访记录ID（visit_record.id）
    :param remarks: 关联备注，选填
    :param operator: 操作人（登录用户名）
    :return: {'ordersId', 'recordId', 'remarks'}
    :raises ValueError: 参数不合法 / 订单或拜访不存在 / 跨客户错挂
    """
    orders_id = str(orders_id or "").strip()
    if not orders_id:
        raise ValueError("缺少订单标识（发货金蝶号）")
    try:
        record_id = int(str(record_id).strip())
    except (TypeError, ValueError):
        raise ValueError("缺少拜访记录标识")
    if record_id <= 0:
        raise ValueError("拜访记录标识不合法")

    visit_order_ref_dao.ensure_table()
    with orm_session() as session:
        # 校验 1：订单存在（按发货金蝶号反查明细，取订单所属 CRM 客户，业务确认一单一号）
        order_customer_ids = [
            row[0] for row in session.query(SalesOrderHistory.customer_id).filter(
                SalesOrderHistory.deliverysapno == orders_id).distinct().all()
            if row[0] is not None
        ]
        if not order_customer_ids:
            raise ValueError("订单不存在（发货金蝶号无匹配）")

        # 校验 2：拜访存在且未作废
        visit = session.query(
            VisitRecord.id, VisitRecord.status, VisitRecord.amap_customer_id,
        ).filter(VisitRecord.id == record_id).first()
        if not visit:
            raise ValueError("拜访记录不存在")
        if visit.status != 1:
            raise ValueError("拜访记录已作废，不可关联")

        # 校验 3：订单客户 ∈ 拜访客户当前绑定集合（1:N 绑定，防跨客户错挂）
        relations = visit_customer_relation_dao.list_by_amap_customer_id(session, visit.amap_customer_id)
        bound_partner_ids = {r.partner_id for r in relations}
        if not bound_partner_ids.intersection(order_customer_ids):
            raise ValueError("订单所属客户与该拜访客户不匹配，禁止跨客户关联")

        visit_order_ref_dao.upsert_link(
            session, orders_id=orders_id, record_id=record_id,
            matched_by=operator or "unknown", remarks=remarks,
        )

    return {"ordersId": orders_id, "recordId": record_id, "remarks": remarks or None}


def unbind_order(orders_id):
    """
    取消关联 = 物理删除该行（业务确认 2026-10-24；误删恢复 = 重新指定一次）

    :param orders_id: 发货金蝶号
    :raises ValueError: 参数不合法 / 该订单本无关联
    """
    orders_id = str(orders_id or "").strip()
    if not orders_id:
        raise ValueError("缺少订单标识（发货金蝶号）")

    visit_order_ref_dao.ensure_table()
    with orm_session() as session:
        deleted = visit_order_ref_dao.delete_by_orders_id(session, orders_id)
    if not deleted:
        raise ValueError("该订单暂无关联拜访")
