# -*- coding:utf-8 -*-
# @Time    : 2026/10/21
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_order_dao.py
# @Software: PyCharm
"""
客访-拿货订单数据访问层（M5，01-主设计文档 4.6/第五节）

数据源：sales_order_history（明细级，只读，已有 idx_customer_id）。
该表一行 = 订单内一个配件明细，必须先按 (orders_id, ddno) 聚合到订单级，
再算销售额指标与列表金额，直接对明细 SUM(total_price) 会重复累加金额。

渠道值域（2026-10-21 bbr_test 实测）：
    order_type_id = 1 常规订单 / 2 退货订单，销售额口径仅统计常规订单（排除退货）。
关联拜访（visit_order_ref）本期未落地，列表"关联拜访"列数据留空。

数据库操作仅保留实际被 Service 调用的函数；业务口径统一放 Service 层。
"""

from sqlalchemy import case, func, and_

from app.models.orm_models.crm.sales_order_history import SalesOrderHistory

# 常规订单（非退货）类型ID，销售额口径过滤用
ORDER_TYPE_NORMAL = 1


def _order_level_subquery(session, partner_ids):
    """
    明细级 → 订单级聚合子查询（金额类指标与列表共用的基表，01 文档第五节）

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表（visit_customer_relation 1:N 绑定）
    :return: SQLAlchemy Subquery（orders_id/ddno/create_date/order_type_id/order_type_name/status/order_amount/items）
    """
    return session.query(
        SalesOrderHistory.orders_id.label("orders_id"),
        SalesOrderHistory.ddno.label("ddno"),
        # 发货金蝶号（列表"订单号"列展示用）；同订单明细行取值一致，MAX 唯一
        func.max(SalesOrderHistory.deliverysapno).label("deliverysapno"),
        func.max(SalesOrderHistory.create_date).label("create_date"),
        func.max(SalesOrderHistory.order_type_id).label("order_type_id"),
        func.max(SalesOrderHistory.order_type_name).label("order_type_name"),
        func.max(SalesOrderHistory.status).label("status"),
        # 订单所属CRM客户（1:N 绑定下按客户等级拆分线上/线下用）；同一订单只归属一个客户，MAX 取值唯一
        func.max(SalesOrderHistory.customer_id).label("customer_id"),
        func.sum(SalesOrderHistory.total_price).label("order_amount"),
        # 配件品类：订单内去重拼接"品牌 品名"（受 MySQL group_concat_max_len 默认 1024 限制，展示用足够）
        # 列名避开 ColumnCollection 内置方法 items()，改用 items_text
        func.group_concat(func.distinct(func.concat(
            func.ifnull(SalesOrderHistory.brand_name, ""),
            " ", func.ifnull(SalesOrderHistory.pdname, ""),
        ))).label("items_text"),
    ).filter(
        SalesOrderHistory.customer_id.in_(partner_ids),
    ).group_by(
        SalesOrderHistory.orders_id, SalesOrderHistory.ddno,
    ).subquery()


def fetch_order_summary(session, partner_ids, year_start_ts, month_start_ts):
    """
    汇总卡聚合（按订单所属CRM客户分组返回，条件聚合避免多次扫描）

    金额口径：仅常规订单（order_type_id=1，排除退货）；
    线上/线下拆分不在 DAO 做（等级口径属业务规则，统一放 Service 层），
    本函数按 customer_id 分组返回，Service 结合 partner_list.level_name 分组求和。

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表
    :param year_start_ts: 本年起始秒级时间戳
    :param month_start_ts: 本月起始秒级时间戳
    :return: [{'customer_id', 'total_amount', 'year_amount', 'month_amount', 'normal_count'}, ...]
    """
    sub = _order_level_subquery(session, partner_ids)
    rows = session.query(
        sub.c.customer_id.label("customer_id"),
        func.coalesce(func.sum(case(
            (sub.c.order_type_id == ORDER_TYPE_NORMAL, sub.c.order_amount), else_=0.0)), 0.0,
        ).label("total_amount"),
        func.coalesce(func.sum(case(
            (and_(sub.c.order_type_id == ORDER_TYPE_NORMAL, sub.c.create_date >= year_start_ts),
             sub.c.order_amount), else_=0.0)), 0.0,
        ).label("year_amount"),
        func.coalesce(func.sum(case(
            (and_(sub.c.order_type_id == ORDER_TYPE_NORMAL, sub.c.create_date >= month_start_ts),
             sub.c.order_amount), else_=0.0)), 0.0,
        ).label("month_amount"),
        func.sum(case(
            (sub.c.order_type_id == ORDER_TYPE_NORMAL, 1), else_=0),
        ).label("normal_count"),
    ).select_from(sub).group_by(sub.c.customer_id).all()
    return [{
        "customer_id": int(r.customer_id),
        "total_amount": float(r.total_amount or 0),
        "year_amount": float(r.year_amount or 0),
        "month_amount": float(r.month_amount or 0),
        "normal_count": int(r.normal_count or 0),
    } for r in rows]


def fetch_oem_qty_stats(session, partner_ids):
    """
    原厂件占比统计（按件数，业务确认 2026-10-22：一条明细的 quantity 即件数）

    口径：常规订单（order_type_id=1）明细中，品牌名含"原厂"的 quantity 合计 ÷ 全部 quantity 合计。
    件数为明细级直接累加（每行 quantity 即该明细件数，无订单级重复累加问题）。

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表
    :return: (oem_qty 原厂件数, total_qty 常规订单总件数)
    """
    row = session.query(
        func.coalesce(func.sum(case(
            (SalesOrderHistory.brand_name.like("%原厂%"), SalesOrderHistory.quantity), else_=0)), 0),
        func.coalesce(func.sum(SalesOrderHistory.quantity), 0),
    ).filter(
        SalesOrderHistory.customer_id.in_(partner_ids),
        SalesOrderHistory.order_type_id == ORDER_TYPE_NORMAL,
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


def fetch_order_page(session, partner_ids, page, limit):
    """
    订单级分页列表（按下单时间倒序）

    :param session: SQLAlchemy Session 对象
    :param partner_ids: CRM客户ID列表
    :param page: 页码（1 起）
    :param limit: 每页条数
    :return: (total 总订单数, rows 行列表，每行为 dict)
    """
    sub = _order_level_subquery(session, partner_ids)
    total = session.query(func.count()).select_from(sub).scalar() or 0
    rows = session.query(
        sub.c.orders_id,
        sub.c.ddno,
        sub.c.deliverysapno,
        sub.c.create_date,
        sub.c.order_type_name,
        sub.c.status,
        sub.c.customer_id,
        sub.c.order_amount,
        sub.c.items_text,
    ).order_by(
        sub.c.create_date.desc(), sub.c.orders_id.desc(),
    ).offset((max(1, page) - 1) * limit).limit(limit).all()
    items = [{
        "orders_id": r.orders_id,
        "ddno": r.ddno,
        "deliverysapno": r.deliverysapno,
        "create_date": r.create_date,
        "order_type_name": r.order_type_name,
        "status": r.status,
        "customer_id": int(r.customer_id) if r.customer_id is not None else None,
        "order_amount": float(r.order_amount) if r.order_amount is not None else None,
        "items_text": r.items_text,
    } for r in rows]
    return int(total), items
