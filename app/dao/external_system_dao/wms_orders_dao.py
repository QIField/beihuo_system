# -*- coding:utf-8 -*-
# @Time    : 2026/10/01
# @Project : beihuo_system
# @File    : wms_orders_dao.py
# @Software: trae-cn

"""
拣货发货数据访问层（只读）

说明：
  1. 本模块只做查询（SELECT），不涉及任何写操作
  2. 目前只实现「已发货」列表，数据来自 wms_orders 表（status = 'shipped'）
"""

from sqlalchemy import or_, func

from app.models.orm_models.wms_orders import WmsOrders

# 已发货状态值（旧拣货发货系统写入的固定值）
STATUS_SHIPPED = "shipped"


def _build_date_filter(expr, start, end):
    """
    构造日期范围过滤条件

    字段存储格式为 'YYYY/M/D H:M:S'，使用 STR_TO_DATE 解析后比较。
    起始/结束日期格式为 'YYYY-MM-DD'，自动补齐为当天起止时间。
    """
    filters = []
    if start:
        filters.append(expr >= f"{start} 00:00:00")
    if end:
        filters.append(expr <= f"{end} 23:59:59")
    return filters


def query_shipped_orders(session, keyword=None, shipper=None,
                         ship_date_start=None, ship_date_end=None,
                         order_date_start=None, order_date_end=None,
                         has_photos=None, page=1, limit=20):
    """
    分页查询已发货订单

    :param session: SQLAlchemy Session 对象
    :param keyword: 模糊搜索关键词（销售订单号 / 出库单号 / 客户名称）
    :param shipper: 操作员
    :param ship_date_start: 发货时间起始（YYYY-MM-DD）
    :param ship_date_end: 发货时间结束（YYYY-MM-DD）
    :param order_date_start: 订单日期起始（YYYY-MM-DD）
    :param order_date_end: 订单日期结束（YYYY-MM-DD）
    :param has_photos: 是否有图片（空/None=全部，1=有图片，0=无图片）
    :param page: 页码，从 1 开始
    :param limit: 每页条数
    :return: (当前页数据字典列表, 总条数)
    """
    query = session.query(WmsOrders).filter(WmsOrders.status == STATUS_SHIPPED)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                WmsOrders.order_no.like(like),
                WmsOrders.out_no.like(like),
                WmsOrders.customer.like(like),
            )
        )

    if shipper:
        query = query.filter(WmsOrders.shipper == shipper)

    ship_date_expr = func.str_to_date(WmsOrders.ship_date, "%Y/%c/%e %H:%i:%s")
    for f in _build_date_filter(ship_date_expr, ship_date_start, ship_date_end):
        query = query.filter(f)

    order_date_expr = func.str_to_date(WmsOrders.order_date, "%Y/%c/%e %H:%i:%s")
    for f in _build_date_filter(order_date_expr, order_date_start, order_date_end):
        query = query.filter(f)

    if has_photos == "1":
        query = query.filter(WmsOrders.photos.isnot(None), WmsOrders.photos != "")
    elif has_photos == "0":
        query = query.filter(or_(WmsOrders.photos.is_(None), WmsOrders.photos == ""))

    total = query.count()

    # 按发货时间倒序（created_at 与 ship_date 一致，且为可靠的 DateTime 字段）
    rows = (
        query.order_by(WmsOrders.created_at.desc(), WmsOrders.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return [row.to_dict() for row in rows], total


def query_shipped_shippers(session):
    """
    查询已发货订单中所有不重复的操作员名称

    :param session: SQLAlchemy Session 对象
    :return: 操作员名称列表（已排序）
    """
    rows = (
        session.query(WmsOrders.shipper)
        .filter(WmsOrders.status == STATUS_SHIPPED, WmsOrders.shipper.isnot(None), WmsOrders.shipper != "")
        .distinct()
        .order_by(WmsOrders.shipper)
        .all()
    )
    return [r[0] for r in rows]


def get_order_by_order_id(session, order_id):
    """
    根据 CRM 订单 ID（order_id 字段）查询已发货订单

    :param session: SQLAlchemy Session 对象
    :param order_id: CRM 订单 ID
    :return: 订单字典或 None
    """
    order = (
        session.query(WmsOrders)
        .filter(WmsOrders.status == STATUS_SHIPPED, WmsOrders.order_id == order_id)
        .first()
    )
    return order.to_dict() if order else None


def query_shipped_order_nos(session):
    """
    查询已发货订单的 order_no 集合（去重，取最新 5000 条）

    用于待发货差集判定：CRM 订单中不在该集合内的即视为"未发货"

    ⚠️ 与原项目 wms_send 保持一致：只取最新 5000 条 order_no
    （对应旧系统 not_shipped_yet 的
     SELECT DISTINCT order_no FROM wms_orders ORDER BY created_at DESC LIMIT 5000）

    :param session: SQLAlchemy Session 对象
    :return: set[str]
    """
    rows = (
        session.query(WmsOrders.order_no)
        .filter(WmsOrders.status == STATUS_SHIPPED, WmsOrders.order_no.isnot(None))
        .distinct()
        .order_by(WmsOrders.created_at.desc())
        .limit(5000)
        .all()
    )
    return {r[0] for r in rows}