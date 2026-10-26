# -*- coding:utf-8 -*-
# @Time    : 2026/10/12 17:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : amap_customer_service.py
# @Software: PyCharm
# 高德客户查询服务：M1 客户列表（分页 + 客户类型/拿货渠道筛选 + 客户名称/地址关键词搜索）
# 列表查询见 app/dao/visit_dao/visit_amap_customer_dao.py page_customers；
# 客户详情聚合（头部 + 基础档案）拆分至 customer_detail_service.py，
# CRM 侧数据经 visit_customer_relation 绑定桥接 partner_list（只读）。

from datetime import datetime, timedelta

from app.dao.visit_dao import visit_amap_customer_dao
from app.utils.orm.session import orm_session

# 拜访状态口径（设计文档 2.4：last_visit_time 驱动 30天内已拜访/超期未拜访）
VISIT_VALID_DAYS = 30
VISIT_STATUS_VISITED = "visited_30d"   # 30天内已拜访
VISIT_STATUS_OVERDUE = "overdue"       # 超期未拜访（含从未拜访，last_visit_time 为空）

STATUS_LABELS = {0: "未关联CRM", 1: "已关联CRM", 2: "无效"}


def _fmt_datetime(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def _serialize(row, visited_threshold):
    """ORM 对象 → 列表行 dict（含拜访状态判定与展示标签）"""
    last_visit = row.last_visit_time
    if last_visit and last_visit >= visited_threshold:
        visit_status, visit_cls, visit_label = (
            VISIT_STATUS_VISITED, "v-tag--green", "30天内已拜访")
    else:
        visit_status, visit_cls, visit_label = (
            VISIT_STATUS_OVERDUE, "v-tag--red", "超期未拜访")

    return {
        "id": row.id,
        "poi": row.amap_poi_id,
        "customer_name": row.customer_name,
        "tag": row.tag,
        "address": row.address,
        "customer_type": row.customer_type,
        "business_circle": row.business_circle,
        "contact_person": row.contact_person,
        "status": row.status,
        "status_label": STATUS_LABELS.get(row.status, "未知"),
        "visit_status": visit_status,
        "visit_status_label": visit_label,
        "visit_status_cls": visit_cls,
        "last_visit_time": _fmt_datetime(last_visit),
        "visit_time": _fmt_datetime(row.visit_time),
        "created_at": _fmt_datetime(row.created_at),
    }


def get_customer_list(page=1, limit=20, customer_type=None, purchase_channels=None, keyword=None):
    """
    分页查询客户列表（M1，支持客户类型/拿货渠道筛选 + 客户名称/地址关键词搜索）

    :param page: 页码
    :param limit: 每页条数（最大 200）
    :param customer_type: 客户类型筛选，选填（多值字段按整词包含匹配，
                          哨兵值 EMPTY_MULTI 表示筛选"无"）
    :param purchase_channels: 拿货渠道筛选，选填（同上）
    :param keyword: 搜索关键词，选填（客户名称/地址模糊匹配，任一命中即返回）
    :return: {'list': [...], 'total': N, 'page': p, 'limit': l, 'unbound_count': N}
    """
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        limit = min(max(1, int(limit)), 200)
    except (TypeError, ValueError):
        limit = 20

    # 空白视为未筛选，避免 LIKE 匹配空词导致恒空结果
    customer_type = (customer_type or "").strip() or None
    purchase_channels = (purchase_channels or "").strip() or None
    keyword = (keyword or "").strip() or None

    visited_threshold = datetime.now() - timedelta(days=VISIT_VALID_DAYS)

    with orm_session() as session:
        total, rows = visit_amap_customer_dao.page_customers(
            session, page=page, limit=limit,
            customer_type=customer_type, purchase_channels=purchase_channels,
            keyword=keyword)
        unbound_count = visit_amap_customer_dao.count_by_status(session, status=0)
        # 会话内完成序列化，避免会话关闭后访问过期实例（DetachedInstanceError）
        items = [_serialize(r, visited_threshold) for r in rows]

    return {
        "list": items,
        "total": total,
        "page": page,
        "limit": limit,
        "unbound_count": unbound_count,
    }


def get_filter_options():
    """
    列表筛选下拉选项（来源：visit_amap_customer 实际数据，随导入动态变化）

    customer_type / purchase_channels 均为 | 分隔多值字段，拆分为单值后去重排序。

    :return: {'customer_types': [...], 'purchase_channels': [...]}
    """
    with orm_session() as session:
        types_raw = visit_amap_customer_dao.get_distinct_customer_types(session)
        channels_raw = visit_amap_customer_dao.get_distinct_purchase_channels(session)
    return {
        "customer_types": sorted({t for raw in types_raw for t in raw.split('|') if t}),
        "purchase_channels": sorted({c for raw in channels_raw for c in raw.split('|') if c}),
    }

