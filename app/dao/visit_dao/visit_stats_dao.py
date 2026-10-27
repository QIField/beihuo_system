# -*- coding:utf-8 -*-
# @Time    : 2026/10/22
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_stats_dao.py
# @Software: PyCharm
"""
客访-详情页指标卡数据访问层（M3，01-主设计文档 第六节）

服务对象：customer_stats_service.py（GET /new/api/visit/customers/stats）。
指标卡各维度统计统一收敛到本模块，与拿货订单 Tab（visit_order_dao）、
拜访历史时间轴（visit_record_dao）的数据访问互相独立，互不依赖。

金额类口径：sales_order_history 明细级 → 订单级聚合（_order_amount_subquery），
禁止直接对明细 SUM(total_price)（重复累加）；本子查询仅聚合金额所需列，
不跑 group_concat / 状态列，比拿货订单列表基表更轻。
件数类口径：明细级直接累加（每行 quantity 即件数，无重复累加问题）。

数据库操作仅保留实际被 Service 调用的函数；业务口径统一放 Service 层。
"""

from sqlalchemy import and_, case, func

from app.models.orm_models.crm.crm_sales_order import CrmSalesOrder
from app.models.orm_models.crm.sales_order_history import SalesOrderHistory
from app.models.orm_models.visit.visit_record import VisitRecord

# 订单类型：1=常规订单（拿货额口径） 2=退货订单（退货金额/退货率口径）
ORDER_TYPE_NORMAL = 1
ORDER_TYPE_REFUND = 2
# crm_sales_order 订单类型（StringToIntType 落库为数字）：1=销售订单（欠款余额口径）
CRM_ORDER_TYPE_SALES = 1


def _order_amount_subquery(session, partner_ids):
    """
    明细级 → 订单级金额聚合子查询（拿货额/退货金额共用的基表）

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表（visit_customer_relation 1:N 绑定）
    :return: SQLAlchemy Subquery（orders_id/ddno/create_date/order_type_id/customer_id/order_amount）
    """
    return session.query(
        SalesOrderHistory.orders_id.label("orders_id"),
        SalesOrderHistory.ddno.label("ddno"),
        func.max(SalesOrderHistory.create_date).label("create_date"),
        # 同一订单只归属一个类型/客户，MAX 取值唯一
        func.max(SalesOrderHistory.order_type_id).label("order_type_id"),
        # 订单所属CRM客户（线上/线下占比按客户等级拆分用）
        func.max(SalesOrderHistory.customer_id).label("customer_id"),
        func.sum(SalesOrderHistory.total_price).label("order_amount"),
    ).filter(
        SalesOrderHistory.customer_id.in_(partner_ids),
    ).group_by(
        SalesOrderHistory.orders_id, SalesOrderHistory.ddno,
    ).subquery()


def fetch_visit_stats(session, amap_customer_id):
    """
    拜访统计（累计拜访次数 + 最近拜访时间，条件聚合单次扫描）

    :param session: SQLAlchemy Session 对象
    :param amap_customer_id: 高德客户POI编码（visit_amap_customer.amap_poi_id）
    :return: (visit_count 累计拜访次数, last_visit_time 最近拜访时间 datetime|None)
    """
    row = session.query(
        func.count(),
        func.max(VisitRecord.visit_time),
    ).filter(
        VisitRecord.status == 1,
        VisitRecord.amap_customer_id == amap_customer_id,
    ).one()
    return int(row[0] or 0), row[1]


def fetch_sales_amount_grouped(session, partner_ids, since_ts):
    """
    累计拿货额 + 近30天成交金额（常规订单订单级金额，按所属CRM客户分组返回）

    口径：仅常规订单（order_type_id=1，排除退货），与拿货订单 Tab 销售额口径一致；
    按 customer_id 分组返回，Service 结合 partner_list.level_name 判定后
    拆分线上/线下（线上订单占比），全量求和即累计拿额、30天窗内求和即成交金额，
    单次扫描三用。

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表（visit_customer_relation 1:N 绑定）
    :param since_ts: 近30天窗口起始秒级时间戳（成交金额口径，业务确认 2026-10-23）
    :return: [{'customer_id', 'total_amount', 'amount_30d'}, ...]
    """
    sub = _order_amount_subquery(session, partner_ids)
    rows = session.query(
        sub.c.customer_id.label("customer_id"),
        func.coalesce(func.sum(case(
            (sub.c.order_type_id == ORDER_TYPE_NORMAL, sub.c.order_amount), else_=0.0)), 0.0,
        ).label("total_amount"),
        func.coalesce(func.sum(case(
            (and_(sub.c.order_type_id == ORDER_TYPE_NORMAL, sub.c.create_date >= since_ts),
             sub.c.order_amount), else_=0.0)), 0.0,
        ).label("amount_30d"),
    ).select_from(sub).group_by(sub.c.customer_id).all()
    return [{
        "customer_id": int(r.customer_id),
        "total_amount": float(r.total_amount or 0),
        "amount_30d": float(r.amount_30d or 0),
    } for r in rows]


def fetch_order_count_grouped(session, partner_ids, since_ts):
    """
    常规订单成交次数（订单级去重计数，按所属CRM客户分组返回）

    口径（业务确认 2026-10-23）：一张常规订单 = 一次成交，订单级去重计数
    （明细 COUNT 会虚高，全表 19,159 行明细对应 14,508 单）；
    线上/线下拆分由 Service 按绑定 CRM 客户等级（is_online_level）完成，
    平台成交次数 = 线上订单数，线下成交次数 = 线下订单数。

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表（visit_customer_relation 1:N 绑定）
    :param since_ts: 时间下限（秒级时间戳，近30天动态传 now-30d）
    :return: [{'customer_id', 'order_count'}, ...]
    """
    sub = _order_amount_subquery(session, partner_ids)
    rows = session.query(
        sub.c.customer_id.label("customer_id"),
        func.count().label("order_count"),
    ).select_from(sub).filter(
        sub.c.order_type_id == ORDER_TYPE_NORMAL,
        sub.c.create_date >= since_ts,
    ).group_by(sub.c.customer_id).all()
    return [{
        "customer_id": int(r.customer_id),
        "order_count": int(r.order_count or 0),
    } for r in rows]


def fetch_refund_amount(session, partner_ids, since_ts=None):
    """
    累计退货金额（退货订单订单级金额合计）

    口径：退货订单（order_type_id=2）订单级金额合计，逐单取绝对值——
    退货单明细 total_price 实测为负值（bbr_test 客户 931 合计 -3,879.16），
    业务口径"累计退货金额"按正数展示。

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表（visit_customer_relation 1:N 绑定）
    :param since_ts: 时间下限（秒级时间戳，按订单级 create_date 过滤），None = 不限；
        近30天动态"退货金额"传 now-30d，核心指标"累计退货金额"不传
    :return: 退货金额合计 float
    """
    sub = _order_amount_subquery(session, partner_ids)
    query = session.query(
        func.coalesce(func.sum(case(
            (sub.c.order_type_id == ORDER_TYPE_REFUND, func.abs(sub.c.order_amount)), else_=0.0)), 0.0,
        ),
    ).select_from(sub)
    if since_ts:
        query = query.filter(sub.c.create_date >= since_ts)
    val = query.scalar()
    return float(val or 0)


def fetch_last_order_time(session, partner_ids):
    """
    最近成交时间（常规订单最后下单时间）

    口径：常规订单（order_type_id=1）明细 MAX(create_date)——实测同订单明细行
    create_date 全部一致（14,508 退货单 0 例外），明细级 MAX = 订单级 MAX；
    不限时间窗口（业务口径：客户最近一次拿货时间）。

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表（visit_customer_relation 1:N 绑定）
    :return: 最近成交时间秒级时间戳 int|None（无常规订单时 None）
    """
    val = session.query(
        func.max(SalesOrderHistory.create_date),
    ).filter(
        SalesOrderHistory.customer_id.in_(partner_ids),
        SalesOrderHistory.order_type_id == ORDER_TYPE_NORMAL,
    ).scalar()
    return int(val) if val else None


def fetch_refund_qty_stats(session, partner_ids):
    """
    退货率件数统计（退货件数 + 常规订单件数，条件聚合单次扫描）

    口径（业务确认 2026-10-22：退货率按件数统计）：
    退货件数 = 退货订单明细 ABS(quantity) 合计——退货单明细 quantity 实测全为负值
    （退多少开多少，部分退货只记退掉的部分，全表 19,159 行均负）；
    常规订单件数 = 常规订单明细 quantity 合计。均为明细级直接累加，无重复累加问题。

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表（visit_customer_relation 1:N 绑定）
    :return: (refund_qty 退货件数, total_qty 常规订单件数)
    """
    row = session.query(
        func.coalesce(func.sum(case(
            (SalesOrderHistory.order_type_id == ORDER_TYPE_REFUND,
             func.abs(SalesOrderHistory.quantity)), else_=0)), 0),
        func.coalesce(func.sum(case(
            (SalesOrderHistory.order_type_id == ORDER_TYPE_NORMAL,
             SalesOrderHistory.quantity), else_=0)), 0),
    ).filter(
        SalesOrderHistory.customer_id.in_(partner_ids),
        SalesOrderHistory.order_type_id.in_([ORDER_TYPE_NORMAL, ORDER_TYPE_REFUND]),
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


def fetch_unpaid_amount(session, partner_ids):
    """
    欠款余额（crm_sales_order 常规订单未结算金额合计）

    口径：SUM(no_receive_amount)，仅销售订单（order_type_name=1，退货订单不计入）；
    不过滤 status，与客户额度管理（crm_sales_order_dao.get_customer_total_price_sum）口径一致。
    数据源：crm_sales_order（每日 02:00 窗口任务 + 周六 02:00 近一年任务 + 看板心跳增量），
    历史订单结清后的 no_receive_amount 变动由周六任务回刷。
    关联键：customer_id = partner_list.partner_id（实测与 partner_id 字段等值）。

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表（visit_customer_relation 1:N 绑定）
    :return: 欠款余额 float（可为负 = 多结/冲抵）
    """
    val = session.query(
        func.coalesce(func.sum(CrmSalesOrder.no_receive_amount), 0.0),
    ).filter(
        CrmSalesOrder.customer_id.in_(partner_ids),
        CrmSalesOrder.order_type_name == CRM_ORDER_TYPE_SALES,
    ).scalar()
    return float(val or 0)
