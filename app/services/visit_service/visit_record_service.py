# -*- coding:utf-8 -*-
# @Time    : 2026/10/13 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_record_service.py
# @Software: PyCharm
# 拜访记录查询服务：M2 拜访历史记录（分页 + 客户/拜访人筛选，按记录时间倒序）
# 查询见 app/dao/visit_dao/visit_record_dao.py page_records；
# 客户名称经 amap_customer_id 关联 visit_amap_customer 取用（记录表不冗余存储）；
# "已转化订单"标签经 visit_order_ref 按拜访反查关联订单号装配（05-订单拜访关联模块设计.md 第四节）。

from app.dao.visit_dao import visit_amap_customer_dao, visit_record_dao
from app.services.visit_service import order_visit_ref_service
from app.utils.orm.session import orm_session


def _serialize(row, name_map, converted_orders):
    """ORM 对象 → 时间轴行 dict（须在会话内调用，避免 DetachedInstanceError）"""
    return {
        "id": row.id,
        "amap_customer_id": row.amap_customer_id,
        "customer_name": name_map.get(row.amap_customer_id),
        "recorder": row.recorder,
        "visit_time": row.visit_time.strftime("%Y-%m-%d %H:%M:%S") if row.visit_time else None,
        "content": row.content,
        "images": row.images,
        # 已转化订单（M4，05 文档）：有≥1条关联即 true，convertedOrders 为发货金蝶号列表
        "converted": bool(converted_orders),
        "converted_orders": converted_orders,
    }


def get_record_list(page=1, limit=20, amap_customer_id=None):
    """
    分页查询拜访记录（M2 拜访历史时间轴，按记录时间倒序）

    :param page: 页码
    :param limit: 每页条数（最大 200）
    :param amap_customer_id: 按客户筛选，选填
    :return: {'list': [...], 'total': N, 'page': p, 'limit': l}
    """
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        limit = min(max(1, int(limit)), 200)
    except (TypeError, ValueError):
        limit = 20

    # 空白视为未筛选
    amap_customer_id = (amap_customer_id or "").strip() or None

    with orm_session() as session:
        total, rows = visit_record_dao.page_records(
            session, page=page, limit=limit, amap_customer_id=amap_customer_id)
        # 会话内完成关联查询与序列化，避免会话关闭后访问过期实例
        name_map = visit_amap_customer_dao.get_customer_name_map(
            session, sorted({r.amap_customer_id for r in rows}))
        # "已转化订单"标签装配（M4，05 文档）：按当前页拜访批量反查关联订单号
        converted_map = order_visit_ref_service.build_converted_map(session, [r.id for r in rows])
        items = [_serialize(r, name_map, converted_map.get(r.id) or []) for r in rows]

    return {
        "list": items,
        "total": total,
        "page": page,
        "limit": limit,
    }
