# -*- coding:utf-8 -*-
"""
OE搜索日志表（oe_search_log）数据访问层

职责：
1. 批量写入/更新 OE 搜索日志数据
2. 按日期范围清空数据（支持全量重跑）
3. 为搜索热度分析提供基础数据
"""

from typing import List, Dict, Any

from sqlalchemy import text

from app.utils.orm.session import orm_session


def batch_upsert(rows: List[Dict[str, Any]]) -> int:
    """
    批量 upsert OE 搜索日志数据（单批次）

    使用 INSERT ... ON DUPLICATE KEY UPDATE 实现，
    依赖唯一索引 (source_biz_id)。

    Args:
        rows: 待写入记录字典列表（一批）

    Returns:
        按传入数据条数统计的记录数（因 MySQL ON DUPLICATE KEY UPDATE 的 affected rows
        不直接表示实际写入/更新条数，故按传入记录数返回）
    """
    if not rows:
        return 0

    sql = text("""
        INSERT INTO oe_search_log (
            source_biz_id,
            brand_name,
            product_name,
            oe_number,
            num,
            search_time,
            search_date
        ) VALUES (
            :source_biz_id,
            :brand_name,
            :product_name,
            :oe_number,
            :num,
            :search_time,
            :search_date
        )
        ON DUPLICATE KEY UPDATE
            brand_name = VALUES(brand_name),
            product_name = VALUES(product_name),
            oe_number = VALUES(oe_number),
            num = VALUES(num),
            search_time = VALUES(search_time),
            search_date = VALUES(search_date),
            updated_at = NOW()
    """)

    with orm_session() as session:
        session.execute(sql, rows)
    return len(rows)


def clear_by_date_range(search_date_start: str, search_date_end: str) -> int:
    """
    按搜索日期范围清空 OE 搜索日志数据

    用于全量同步前先清理旧数据，保证数据一致性。

    Args:
        search_date_start: 开始日期，格式 YYYY-MM-DD
        search_date_end: 结束日期，格式 YYYY-MM-DD

    Returns:
        删除行数
    """
    sql = text("""
        DELETE FROM oe_search_log
        WHERE search_date >= :search_date_start
          AND search_date <= :search_date_end
    """)
    with orm_session() as session:
        result = session.execute(sql, {
            "search_date_start": search_date_start,
            "search_date_end": search_date_end,
        })
        return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]


def clear_by_date(search_date: str) -> int:
    """
    按单个搜索日期清空 OE 搜索日志数据

    Args:
        search_date: 日期，格式 YYYY-MM-DD

    Returns:
        删除行数
    """
    return clear_by_date_range(search_date, search_date)
