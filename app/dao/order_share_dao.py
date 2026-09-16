# -*- coding:utf-8 -*-
# @Time    : 2026/09/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : order_share_dao.py
# @Software: trae-cn

"""
订单分享模块 DAO

职责：order_delivery_info 表的读写（UPSERT）。
说明：所有查询/更新结果均以 plain dict 返回，避免 ORM 实例在 Session 关闭后
      出现 DetachedInstanceError。
"""

from app.models.orm_models.order_delivery_info import OrderDeliveryInfo
from app.utils.orm.session import orm_session


def _to_dict(record):
    """将 ORM 记录转换为字典（在 Session 有效期内调用）"""
    if record is None:
        return None
    return {
        "id": record.id,
        "orders_id": record.orders_id,
        "orders_no": record.orders_no,
        "handler": record.handler,
        "order_mobile": record.order_mobile,
        "create_date": record.create_date,
        "delivery_id": record.delivery_id,
        "jhdate": record.jhdate,
        "ship_date": record.ship_date,
        "photos": record.photos,
        "status": record.status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def get_by_orders_no(orders_no):
    """按订单号查询本地缓存记录，返回 dict"""
    with orm_session() as session:
        record = session.query(OrderDeliveryInfo).filter_by(orders_no=orders_no).first()
        return _to_dict(record)


def get_by_orders_id(orders_id):
    """按 CRM 订单 ID 查询本地缓存记录，返回 dict"""
    with orm_session() as session:
        record = session.query(OrderDeliveryInfo).filter_by(orders_id=orders_id).first()
        return _to_dict(record)


def upsert(record_dict):
    """
    插入或更新订单物流状态记录，返回 dict

    :param record_dict: 包含 orders_id, orders_no, handler, create_date, delivery_id, jhdate, ship_date, status
    """
    with orm_session() as session:
        existing = session.query(OrderDeliveryInfo).filter_by(
            orders_id=record_dict["orders_id"]
        ).first()

        if existing:
            for key, value in record_dict.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            session.flush()
            session.refresh(existing)
            return _to_dict(existing)

        record = OrderDeliveryInfo(**record_dict)
        session.add(record)
        session.flush()
        session.refresh(record)
        return _to_dict(record)
