# -*- coding:utf-8 -*-
# @Time    : 2026/09/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : order_status_service.py
# @Software: trae-cn

"""
订单物流状态服务

职责：
1. 维护本地 order_delivery_info 缓存表
2. 根据当前状态决定是否需要继续推进查询
3. 调用 CRM 接口与 WMS 表，更新状态

状态流转：
    已下单 → 仓库已接单 → 已出库
    （jhdate 为空）   （jhdate 有值，ship_date 为空/未匹配）   （ship_date 有值）
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import text

from app.dao import order_share_dao
from app.models.orm_models.order_delivery_info import OrderDeliveryInfo
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.utils.orm.session import orm_session

logger = logging.getLogger(__name__)

STATUS_ORDERED = OrderDeliveryInfo.STATUS_ORDERED
STATUS_PICKED = OrderDeliveryInfo.STATUS_PICKED
STATUS_SHIPPED = OrderDeliveryInfo.STATUS_SHIPPED

_WMS_SHIP_DATE_SQL = text("""
    SELECT ship_date
    FROM wms_orders
    WHERE order_id = :orders_id
    LIMIT 1
""")


def get_order_status_view(orders_no, crm_spider=None, refresh=False):
    """
    获取订单物流状态视图（含缓存与增量推进）

    :param orders_no: CRM 订单号（明文）
    :param crm_spider: 可选外部传入的 CrmGzbbrSpider 实例，用于复用会话
    :param refresh: 是否强制刷新（当前未用于绕过缓存，仅作为扩展预留）
    :return: 页面展示字段字典；查不到或接口异常返回 None
    """
    own_spider = crm_spider is None
    spider = crm_spider or CrmGzbbrSpider()

    try:
        cached = order_share_dao.get_by_orders_no(orders_no)

        # 已出库：直接返回，无需再查
        if cached and cached.get("status") == STATUS_SHIPPED:
            return _build_view(cached)

        # 已下单：直接从 deliveryView 开始查 jhdate
        if cached and cached.get("status") == STATUS_ORDERED and cached.get("delivery_id"):
            record = _advance_from_ordered(spider, cached)
            return _build_view(record) if record else _build_view(cached)

        # 仓库已接单：直接查 wms_orders 的 ship_date
        if cached and cached.get("status") == STATUS_PICKED and cached.get("orders_id"):
            record = _advance_from_picked(cached)
            return _build_view(record) if record else _build_view(cached)

        # 无缓存 或 状态异常：走完整流程
        record = _full_flow(spider, orders_no)
        return _build_view(record) if record else None

    except Exception:
        logger.exception("[订单分享] 获取订单 %s 状态异常", orders_no)
        # 异常时尽量返回已有缓存，保证页面不挂
        cached = order_share_dao.get_by_orders_no(orders_no)
        return _build_view(cached) if cached else None
    finally:
        if own_spider:
            spider.close()


def _full_flow(spider, orders_no):
    """完整流程：从 mergeOrderList 开始，一步步推进到最终状态"""
    orders_id = _fetch_orders_id(spider, orders_no)
    if not orders_id:
        logger.warning("[订单分享] mergeOrderList 未找到订单 %s", orders_no)
        return None

    create_date, delivery_id = _fetch_orders_view(spider, orders_id)

    # 此时还无法判断状态，先按已下单存一份（delivery_id 可能为空则停止）
    if not delivery_id:
        logger.info("[订单分享] 订单 %s 无 delivery_id，暂记为已下单", orders_no)
        return order_share_dao.upsert({
            "orders_id": orders_id,
            "orders_no": orders_no,
            "create_date": create_date,
            "delivery_id": None,
            "jhdate": None,
            "ship_date": None,
            "status": STATUS_ORDERED,
        })

    jhdate = _fetch_jhdate(spider, delivery_id)
    if not jhdate:
        return order_share_dao.upsert({
            "orders_id": orders_id,
            "orders_no": orders_no,
            "create_date": create_date,
            "delivery_id": delivery_id,
            "jhdate": None,
            "ship_date": None,
            "status": STATUS_ORDERED,
        })

    ship_date = _fetch_ship_date(orders_id)
    status = STATUS_SHIPPED if ship_date else STATUS_PICKED

    return order_share_dao.upsert({
        "orders_id": orders_id,
        "orders_no": orders_no,
        "create_date": create_date,
        "delivery_id": delivery_id,
        "jhdate": jhdate,
        "ship_date": ship_date,
        "status": status,
    })


def _advance_from_ordered(spider, cached):
    """已下单状态推进：查 deliveryView 的 jhdate"""
    jhdate = _fetch_jhdate(spider, cached["delivery_id"])
    if not jhdate:
        return None  # 状态不变

    ship_date = _fetch_ship_date(cached["orders_id"])
    status = STATUS_SHIPPED if ship_date else STATUS_PICKED

    return order_share_dao.upsert({
        "orders_id": cached["orders_id"],
        "orders_no": cached["orders_no"],
        "create_date": cached["create_date"],
        "delivery_id": cached["delivery_id"],
        "jhdate": jhdate,
        "ship_date": ship_date,
        "status": status,
    })


def _advance_from_picked(cached):
    """仓库已接单状态推进：查 wms_orders 的 ship_date"""
    ship_date = _fetch_ship_date(cached["orders_id"])
    if not ship_date:
        return None  # 状态不变

    return order_share_dao.upsert({
        "orders_id": cached["orders_id"],
        "orders_no": cached["orders_no"],
        "create_date": cached["create_date"],
        "delivery_id": cached["delivery_id"],
        "jhdate": cached["jhdate"],
        "ship_date": ship_date,
        "status": STATUS_SHIPPED,
    })


def _fetch_orders_id(spider, orders_no):
    """调 mergeOrderList 获取 orders_id（默认近半个月）"""
    now = datetime.now()
    start = now - timedelta(days=15)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)

    resp = spider.get_mergeOrderList(
        page=1,
        limit=50,
        orderdate_start=start_ms,
        orderdate_end=end_ms,
    )
    resp.raise_for_status()
    data = resp.json()

    order_list = data.get("data", {}).get("list", {}).get("data", [])
    for item in order_list:
        if item.get("orders_no") == orders_no:
            return item.get("orders_id")
    return None


def _fetch_orders_view(spider, orders_id):
    """调 orders_view 获取 create_date 和 delivery_id"""
    resp = spider.get_orders_view(orders_id=orders_id)
    resp.raise_for_status()
    data = resp.json()

    table_header = data.get("data", {}).get("TableHeader", {})
    create_date_raw = table_header.get("create_date")
    delivery_id = table_header.get("delivery_id")

    return _normalize_timestamp(create_date_raw), delivery_id


def _fetch_jhdate(spider, delivery_id):
    """调 deliveryView 获取 jhdate"""
    resp = spider.get_delivery_view(delivery_id=delivery_id)
    resp.raise_for_status()
    data = resp.json()

    jhdate_raw = data.get("data", {}).get("TableHeader", {}).get("pack", {}).get("jhdate")
    return _normalize_datetime(jhdate_raw)


def _fetch_ship_date(orders_id):
    """查 wms_orders 获取 ship_date"""
    with orm_session() as session:
        row = session.execute(_WMS_SHIP_DATE_SQL, {"orders_id": orders_id}).mappings().first()
    return row["ship_date"] if row else None


def _normalize_timestamp(ts):
    """统一时间戳为秒级（兼容毫秒）"""
    if not ts:
        return None
    try:
        ts = int(ts)
        return ts // 1000 if ts > 1_000_000_000_0 else ts
    except (ValueError, TypeError):
        return None


def _normalize_datetime(value):
    """统一日期字段为 datetime 对象（兼容字符串和时间戳）"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        ts = int(value)
        ts = ts // 1000 if ts > 1_000_000_000_0 else ts
        try:
            return datetime.fromtimestamp(ts)
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def _build_view(record):
    """将记录（dict 或 ORM 实例）组装为页面展示字段"""
    # 兼容 dict 和 ORM 实例访问
    getter = record.get if isinstance(record, dict) else lambda k, default=None: getattr(record, k, default)
    return {
        "orders_id": getter("orders_id"),
        "orders_no": getter("orders_no"),
        "status": getter("status"),
        "create_date": _format_timestamp(getter("create_date")),
        "jhdate": _format_datetime(getter("jhdate")),
        "ship_date": _format_datetime(getter("ship_date")),
    }


def _format_datetime(value):
    """datetime 对象或字符串转展示字符串"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str):
        return value[:16] if len(value) >= 16 else value
    return None


def _format_timestamp(ts):
    """秒级时间戳转展示字符串"""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError, OverflowError):
        return ""
