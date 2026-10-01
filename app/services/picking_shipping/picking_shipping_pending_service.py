# -*- coding:utf-8 -*-
# @Time    : 2026/10/01
# @Project : beihuo_system
# @File    : picking_shipping_pending_service.py
# @Software: trae-cn

"""
拣货发货「待发货」查询服务（只读，不落库）

数据来源与旧系统 wms_send 完全一致：
  待发货 = CRM 近 5 天销售订单（mergeOrderList，order_type_id=1）− 本地 wms_orders 已发货记录

流程（对应旧系统 crm_dd_api/crm_api.py 的 getOrder + not_shipped_yet）：
  1. 计算"今天往前 5 天 ~ 今天"的毫秒时间窗
  2. 调爬虫 CrmGzbbrSpider.get_mergeOrderList 实时取销售订单（limit=5000）
  3. 查本地 wms_orders 已发货的订单号集合，pandas 做左连接差集，保留未发货的
  4. 结果缓存 10 分钟（app/core/cache_utils.Cache，跨请求复用，避免每次实时打 CRM）

注意：
  - 不做任何写库操作
  - 待发货永远以实时 CRM 数据为准，wms_orders 只用于判定"哪些已经发过货"
"""

from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd

from app.core.cache_utils import get_default_cache
from app.dao.external_system_dao import wms_orders_dao
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.utils.orm.session import orm_session

# 与旧系统 wms_send 保持一致：只取近 N 天的销售订单
DAYS_BACK = 5
# CRM 接口单次拉取上限（旧系统 page=1&limit=5000，一把梭不分页）
FETCH_LIMIT = 5000
# 待发货结果缓存时间（秒）
CACHE_TTL = 600
# 缓存键（带命名空间前缀，避免与其它模块在共享默认缓存中的键冲突）
_PENDING_CACHE_KEY = "picking_shipping:pending_orders"

# CRM 原始字段 -> 前端展示字段（对齐旧系统 not_shipped_yet 的重命名）
_FIELD_MAP = {
    "orders_id": "id",
    "orders_no": "order_no",
    "d_sap_no": "out_no",
    "fullname": "customer",
    "create_date": "order_date_ts",
    "sfje": "amount",
    "sku_num": "sku_count",
    "total_quantity": "total_quantity",
}


def _get_today_timestamp_range():
    """
    获取时间窗的毫秒级时间戳（与旧系统 get_today_timestamp_range 一致）

    返回：(start_ts, end_ts)
      start_ts = (今天 - DAYS_BACK) 00:00:00
      end_ts   = 今天 23:59:59
    """
    start_day = date.today() - timedelta(days=DAYS_BACK)
    end_day = date.today()
    start_time = datetime.combine(start_day, datetime.min.time())
    end_time = datetime.combine(end_day, datetime.max.time())
    return int(start_time.timestamp() * 1000), int(end_time.timestamp() * 1000)


def _fetch_crm_pending_orders():
    """
    实时调 CRM mergeOrderList，返回"未发货"订单的原始字段字典列表

    对应旧系统 getOrder() + not_shipped_yet()
    """
    start_ts, end_ts = _get_today_timestamp_range()

    spider = CrmGzbbrSpider()
    try:
        response = spider.get_mergeOrderList(
            page=1,
            limit=FETCH_LIMIT,
            orderdate_start=start_ts,
            orderdate_end=end_ts,
            order_type_id=1,  # 只取销售订单
        )
        res = response.json()
    finally:
        spider.close()

    if res.get("status") != 200:
        return []

    data = res.get("data", {}).get("list", {}).get("data", [])
    if not data:
        return []

    df = pd.DataFrame(data)
    keep = [f for f in _FIELD_MAP.keys() if f in df.columns]
    df = df[keep].copy()

    # 排除本地已发货：与旧系统一致，用 wms_orders 的 order_no 做差集
    with orm_session() as session:
        shipped_nos = wms_orders_dao.query_shipped_order_nos(session)
    if shipped_nos:
        shipped_df = pd.DataFrame({"order_no": list(shipped_nos)})
        shipped_df["_shipped"] = 1
        df = pd.merge(df, shipped_df, left_on="orders_no", right_on="order_no", how="left")
        df = df[df["_shipped"].isna()].drop(columns=["order_no", "_shipped"])

    df = df.replace(np.nan, "")
    records = df.to_dict("records")

    # 字段重命名：原始 CRM 字段 -> 展示字段
    renamed = []
    for row in records:
        renamed.append({new_key: row.get(old_key) for old_key, new_key in _FIELD_MAP.items()})
    return renamed


def get_pending_orders():
    """
    获取待发货订单（带 10 分钟缓存）

    :return: 待发货订单字典列表，字段见 _FIELD_MAP（含 order_date_ts 秒级时间戳）
    """
    cache = get_default_cache()
    cached = cache.get(_PENDING_CACHE_KEY)
    if cached is not None:
        return cached

    result = _fetch_crm_pending_orders()
    if result:
        cache.set(_PENDING_CACHE_KEY, result, ttl=CACHE_TTL)
    return result


def _timestamp_to_str(ts):
    """秒级时间戳转展示字符串"""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError, OverflowError):
        return ""


def format_pending_order(row):
    """把 CRM 原始行格式化为前端展示字段"""
    return {
        "order_id": row.get("id") or "",
        "order_no": row.get("order_no") or "",
        "out_no": row.get("out_no") or "",
        "customer": row.get("customer") or "",
        "order_date": _timestamp_to_str(row.get("order_date_ts")),
        "amount": row.get("amount") if row.get("amount") not in (None, "") else "",
        "sku_count": row.get("sku_count") if row.get("sku_count") not in (None, "") else "",
        "total_quantity": row.get("total_quantity") if row.get("total_quantity") not in (None, "") else "",
    }