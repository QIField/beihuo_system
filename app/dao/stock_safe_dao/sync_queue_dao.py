# -*- coding:utf-8 -*-
# @Time    : 2026/10/18
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : sync_queue_dao.py
# @Software: trae-cn

"""
安全库存同步CRM队列表（stock_safe_sync_queue）数据访问层（DAO）

仅提供基础增删改查，业务逻辑（按同步状态筛选、补货候选查询、统计等）由 Service 层实现。

同步状态判定（不设 sync_status 字段，由 synced_at 派生）：
  - synced_at IS NULL      → 待同步
  - synced_at IS NOT NULL  → 已同步
"""

from sqlalchemy import or_

from app.models.orm_models.stock_safe_models.stock_safe_sync_queue import StockSafeSyncQueue


def _to_dict(record) -> dict:
    """将 ORM 记录转换为字典（在 Session 有效期内调用，避免 DetachedInstanceError）"""
    if record is None:
        return None  # pyright: ignore[reportReturnType]
    return {
        "id": record.id,
        "number": record.number,
        "brand_name": record.brand_name,
        "frey_no": record.frey_no,
        "pdname": record.pdname,
        "sync_enabled": record.sync_enabled,
        "synced_at": record.synced_at.strftime("%Y-%m-%d %H:%M:%S") if record.synced_at else None,
        "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        "updated_at": record.updated_at.strftime("%Y-%m-%d %H:%M:%S") if record.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
    }


def batch_insert_queue(session, items: list) -> dict:
    """
    批量插入同步队列（仅插入，已存在的记录跳过）

    以唯一键 uk_number_brand(number, brand_name) 判断是否已存在，
    已存在的记录不做任何更新，直接跳过。

    Args:
        session: orm_session 上下文内的 SQLAlchemy Session
        items: 待插入记录字典列表，每个元素需包含 number / brand_name，
               可选 frey_no / pdname / sync_enabled（默认 1）

    Returns:
        dict: {"inserted": 新增行数, "skipped": 跳过行数, "total": 传入总数}
    """
    if not items:
        return {"inserted": 0, "skipped": 0, "total": 0}

    # 一次性查询已存在的 (number, brand_name) 组合
    keys = {(item["number"], item["brand_name"]) for item in items}
    existing_records = session.query(StockSafeSyncQueue).filter(
        or_(*[
            (StockSafeSyncQueue.number == n) & (StockSafeSyncQueue.brand_name == b)
            for n, b in keys
        ])
    ).all()
    existing_keys = {(r.number, r.brand_name) for r in existing_records}

    inserted = 0
    for item in items:
        key = (item["number"], item["brand_name"])
        if key in existing_keys:
            continue
        record = StockSafeSyncQueue(
            number=item["number"],
            brand_name=item["brand_name"],
            frey_no=item.get("frey_no"),
            pdname=item.get("pdname"),
            sync_enabled=item.get("sync_enabled", 1),
        )
        session.add(record)
        inserted += 1

    session.flush()
    return {"inserted": inserted, "skipped": len(items) - inserted, "total": len(items)}


def fetch_by_number_brand(session, number: str, brand_name: str) -> dict:
    """
    按 (number, brand_name) 查询单条队列记录

    Args:
        session: orm_session 上下文内的 SQLAlchemy Session
        number: OE 号
        brand_name: 品牌名

    Returns:
        dict: 记录字典，不存在返回 None
    """
    record = (
        session.query(StockSafeSyncQueue)
        .filter_by(number=number, brand_name=brand_name)
        .first()
    )
    return _to_dict(record)


def update_by_id(session, queue_id: int, fields: dict) -> int:
    """
    按主键 id 更新指定字段

    Args:
        session: orm_session 上下文内的 SQLAlchemy Session
        queue_id: 主键 id
        fields: 待更新字段字典，如 {"synced_at": None, "pdname": "xxx"}
                时间字段传 None 表示置空，传 "NOW()" 使用数据库当前时间

    Returns:
        受影响的行数（0 表示记录不存在）
    """
    if not fields:
        return 0

    record = session.query(StockSafeSyncQueue).filter_by(id=queue_id).first()
    if not record:
        return 0

    for key, value in fields.items():
        if hasattr(record, key):
            setattr(record, key, value)

    session.flush()
    return 1
