# -*- coding:utf-8 -*-
# @Time    : 2026/10/01
# @Project : beihuo_system
# @File    : picking_shipping_service.py
# @Software: trae-cn

"""
拣货发货查询服务（只读）

目前实现「已发货」列表：数据来自 wms_orders 表（status = 'shipped'）。
本服务只负责参数校验、字段格式化与分页组装。
"""

from datetime import datetime

from app.dao.external_system_dao import wms_orders_dao
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.services.picking_shipping import picking_shipping_pending_service
from app.utils.orm.session import orm_session

_MAX_LIMIT = 200


def get_shipped_orders(keyword="", shipper="", ship_date_start="", ship_date_end="",
                       order_date_start="", order_date_end="", has_photos="", page=1, limit=20):
    """
    分页查询已发货订单

    :param keyword: 模糊搜索关键词（销售订单号 / 出库单号 / 客户名称）
    :param shipper: 操作员
    :param ship_date_start: 发货时间起始（YYYY-MM-DD）
    :param ship_date_end: 发货时间结束（YYYY-MM-DD）
    :param order_date_start: 订单日期起始（YYYY-MM-DD）
    :param order_date_end: 订单日期结束（YYYY-MM-DD）
    :param has_photos: 是否有图片（空=全部，1=有图片，0=无图片）
    :param page: 页码，从 1 开始
    :param limit: 每页条数
    :return: {'list': [...], 'total': int, 'page': int, 'limit': int}
    """
    keyword = (keyword or "").strip()
    shipper = (shipper or "").strip()
    ship_date_start = (ship_date_start or "").strip()
    ship_date_end = (ship_date_end or "").strip()
    order_date_start = (order_date_start or "").strip()
    order_date_end = (order_date_end or "").strip()
    has_photos = (has_photos or "").strip()
    page = page if page and page > 0 else 1
    limit = limit if limit and limit > 0 else 20
    limit = min(limit, _MAX_LIMIT)

    with orm_session() as session:
        rows, total = wms_orders_dao.query_shipped_orders(
            session,
            keyword=keyword,
            shipper=shipper,
            ship_date_start=ship_date_start,
            ship_date_end=ship_date_end,
            order_date_start=order_date_start,
            order_date_end=order_date_end,
            has_photos=has_photos,
            page=page,
            limit=limit,
        )

    return {
        "list": [_format_row(row) for row in rows],
        "total": total,
        "page": page,
        "limit": limit,
    }


def get_shipped_shippers():
    """
    获取已发货订单中所有不重复的操作员名称

    :return: 操作员名称列表（已按字母/拼音排序）
    """
    with orm_session() as session:
        shippers = wms_orders_dao.query_shipped_shippers(session)
    return shippers


def get_pending_orders_page(keyword="", page=1, limit=20):
    """
    分页查询待发货订单

    待发货数据一次性从 CRM 取回（带 10 分钟缓存），在本函数内做内存搜索和分页。

    :param keyword: 模糊搜索关键词（销售订单号 / 出库单号 / 客户名称）
    :param page: 页码，从 1 开始
    :param limit: 每页条数
    :return: {'list': [...], 'total': int, 'page': int, 'limit': int}
    """
    keyword = (keyword or "").strip()
    page = page if page and page > 0 else 1
    limit = limit if limit and limit > 0 else 20
    limit = min(limit, _MAX_LIMIT)

    rows = picking_shipping_pending_service.get_pending_orders()
    rows = [picking_shipping_pending_service.format_pending_order(r) for r in rows]

    if keyword:
        kw = keyword.lower()
        rows = [
            r for r in rows
            if (r.get("order_no") or "").lower().find(kw) != -1
            or (r.get("out_no") or "").lower().find(kw) != -1
            or (r.get("customer") or "").lower().find(kw) != -1
        ]

    # 待发货按订单创建时间倒序
    rows = sorted(
        rows,
        key=lambda r: r.get("order_date") or "",
        reverse=True,
    )

    total = len(rows)
    start = (page - 1) * limit
    end = start + limit
    return {
        "list": rows[start:end],
        "total": total,
        "page": page,
        "limit": limit,
    }


def get_order_detail(order_id, status):
    """
    查询订单详情（已发货 / 待发货共用入口）

    :param order_id: CRM 订单 ID（对应 orders_id）
    :param status: shipped 或 pending
    :return: {'header': {...}, 'items': [...]}
    """
    order_id = int(order_id) if order_id else 0
    if order_id <= 0:
        raise ValueError("订单 ID 无效")

    crm_detail = _fetch_crm_order_detail(order_id)

    if status == "shipped":
        with orm_session() as session:
            order = wms_orders_dao.get_order_by_order_id(session, order_id)
        header = {
            "order_id": order_id,
            "order_no": order.get("order_no") if order else crm_detail.get("order_no", ""),
            "out_no": order.get("out_no") if order else "",
            "customer": order.get("customer") if order else crm_detail.get("customer", ""),
            "order_date": _format_datetime(order.get("order_date")) if order else crm_detail.get("order_date", ""),
            "ship_date": _format_datetime(order.get("ship_date")) if order else "",
            "shipper": order.get("shipper") if order else "",
            "amount": order.get("amount") if order else crm_detail.get("amount", ""),
            "status": "已发货",
            "photos": order.get("photos") if order else "",
        }
    else:
        header = {
            "order_id": order_id,
            "order_no": crm_detail.get("order_no", ""),
            "out_no": "",
            "customer": crm_detail.get("customer", ""),
            "order_date": crm_detail.get("order_date", ""),
            "ship_date": "",
            "shipper": "",
            "amount": crm_detail.get("amount", ""),
            "status": "待发货",
            "pay_type": crm_detail.get("pay_type", ""),
            "address": crm_detail.get("address", ""),
            "photos": "",
        }

    return {
        "header": header,
        "items": crm_detail.get("items", []),
    }


def _fetch_crm_order_detail(order_id):
    """
    调用 CRM orders_view 接口获取订单明细

    :return: {'order_no': ..., 'customer': ..., 'order_date': ..., 'pay_type': ..., 'address': ..., 'amount': ..., 'items': [...]}
    """
    spider = CrmGzbbrSpider()
    try:
        response = spider.get_orders_view(orders_id=order_id, page=1, limit=1000)
        res = response.json()
    finally:
        spider.close()

    if res.get("status") != 200:
        raise RuntimeError(res.get("message") or "CRM 详情接口调用失败")

    data = res.get("data", {})
    table_header = data.get("TableHeader") or {}
    quote_line = data.get("Quotelineitem") or {}
    items = quote_line.get("data") or []

    return {
        "order_no": table_header.get("orders_no") or "",
        "customer": table_header.get("fullname") or "",
        "order_date": _format_datetime(table_header.get("create_date")),
        "pay_type": table_header.get("pay_type_name") or "",
        "address": table_header.get("company_address") or "",
        "amount": table_header.get("sfje") or "",
        "items": [
            {
                "l_name_zh": item.get("l_name_zh") or "",
                "number": item.get("number") or "",
                "brand": item.get("brand") or "",
                "quantity": item.get("quantity") if item.get("quantity") is not None else "",
                "price": item.get("price") if item.get("price") is not None else "",
                "total_price": item.get("total_price") if item.get("total_price") is not None else "",
            }
            for item in items
        ],
    }


def _format_row(row):
    """把数据库行格式化为前端展示字段"""
    photos = row.get("photos") or ""
    photo_count = len([p for p in photos.split(",") if p.strip()]) if photos else 0
    return {
        "order_id": row.get("order_id") or row.get("id") or "",
        "order_no": row.get("order_no") or "",
        "out_no": row.get("out_no") or "",
        "customer": row.get("customer") or "",
        "order_date": _format_datetime(row.get("order_date")),
        "amount": row.get("amount") if row.get("amount") is not None else "",
        "sku_count": row.get("sku_count") if row.get("sku_count") is not None else "",
        "total_quantity": row.get("total_quantity") if row.get("total_quantity") is not None else "",
        "photo_count": photo_count,
        "ship_date": _format_datetime(row.get("ship_date")),
        "shipper": row.get("shipper") or "",
    }


def _format_datetime(value):
    """
    统一时间字段为展示字符串（格式：YYYY-MM-DD HH:MM:SS）

    - 数字 / 纯数字字符串：按时间戳处理（兼容秒级与毫秒级）
    - 常见日期字符串：解析后统一格式
    - 无法解析的字符串：原样返回
    """
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (int, float)):
        return _timestamp_to_str(int(value))
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return _timestamp_to_str(int(stripped))
        for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(stripped, fmt).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return stripped
    return str(value)


def _timestamp_to_str(ts):
    """时间戳转字符串（毫秒级自动降为秒级）"""
    if ts <= 0:
        return ""
    if ts > 1_000_000_000_000:
        ts //= 1000
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError, OverflowError):
        return str(ts)