# -*- coding:utf-8 -*-
# @Time    : 2026/09/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : order_view_service.py
# @Software: trae-cn

"""
订单分享页面数据服务

职责：根据订单号（明文）查询订单基本信息，组装为页面展示字段。
当前数据源：crm_sales_order 表（sap_no = 订单号，order_type_name=1 销售订单）。
数据源（CRM 其他接口）确认后，仅需调整本文件的查询逻辑，路由与加密层不变。
"""

import logging
from datetime import datetime

from sqlalchemy import text

from app.utils.orm.session import orm_session

logger = logging.getLogger(__name__)

# 订单状态展示文案映射（状态值确认后在此补充，未命中时展示原始值）
STATUS_TEXT_MAPPING = {}

_QUERY_ORDER_BASIC_SQL = text("""
    SELECT
        sap_no,
        d_sap_no,
        fullname,
        total_quantity,
        total_price,
        status,
        handler,
        create_date
    FROM crm_sales_order
    WHERE sap_no = :order_no
      AND order_type_name = 1
    ORDER BY orders_id DESC
    LIMIT 1
""")


def get_order_basic_by_no(order_no):
    """
    按订单号查询订单基本信息（销售订单，重复单号取最新一条）

    :param order_no: 订单号（明文）
    :return: 页面展示字段字典；查不到返回 None
    """
    with orm_session() as session:
        row = session.execute(_QUERY_ORDER_BASIC_SQL, {"order_no": order_no}).mappings().first()

    if row is None:
        logger.info("[订单分享] 订单号 %s 未查到数据", order_no)
        return None

    return {
        "order_no": row["sap_no"],
        "kingdee_no": row["d_sap_no"],
        "customer_name": row["fullname"],
        "quantity": row["total_quantity"],
        "amount": row["total_price"],
        "status": STATUS_TEXT_MAPPING.get(row["status"], row["status"]),
        "handler": row["handler"],
        "created_at": _format_timestamp(row["create_date"]),
    }


def _format_timestamp(ts):
    """秒级时间戳转展示字符串（YYYY-MM-DD HH:MM）"""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError, OverflowError):
        return ""
