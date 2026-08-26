# -*- coding:utf-8 -*-
# @Time    : 2026/08/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_useless_data_dao.py
# @Software: trae-cn

"""
安全库存废弃数据表（stock_safe_useless_data）数据访问层

职责：
1. 将 stock_safe 表中的记录写入 stock_safe_useless_data 废弃表（insert_useless_data）
2. 按条码删除废弃记录（delete_useless_data_by_freys），用于"恢复数据"

说明：不删除 / 修改 stock_safe 表，废弃仅用于在列表查询中按 frey_no 排除该数据。
表级别存量数据均为必填业务标识字段，故原始记录缺失某字段时不做拦截，
统一由业务层（stock_safe_useless_data_service）负责组装待写入的数据字段。
"""

from sqlalchemy import text


def insert_useless_data(session, rows: list, batch_size: int = 500) -> int:
    """
    批量插入废弃数据到 stock_safe_useless_data 表（INSERT IGNORE）

    采用 INSERT IGNORE 策略：
    - 命中联合唯一键 uk_number_brand_pdname（number, brand_name, pdname）
      或条码唯一键 uk_frey_no（frey_no）时，静默跳过，不会导致整批失败。
    - created_at / updated_at 走数据库默认值，不显式写入。

    Args:
        session: 或m_session 上下文内的 SQLAlchemy Session（用于保证事务一致性）
        rows: 待插入记录字典列表，每个元素需包含 number / brand_name / frey_no / pdname
        batch_size: 每批插入行数，默认 500

    Returns:
        实际插入的行数
    """
    if not rows:
        return 0

    sql = text("""
        INSERT IGNORE INTO stock_safe_useless_data (
            number,
            brand_name,
            frey_no,
            pdname
        )
        VALUES (
            :number,
            :brand_name,
            :frey_no,
            :pdname
        )
    """)

    total = 0
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        result = session.execute(sql, chunk)
        total += result.rowcount  # pyright: ignore[reportAttributeAccessIssue]
    return total


def delete_useless_data_by_freys(session, freys: list) -> int:
    """
    按条码（frey_no）删除 stock_safe_useless_data 表中的废弃记录（恢复数据）

    Args:
        session: 或m_session 上下文内的 SQLAlchemy Session
        freys: 待恢复的条码 frey_no 列表

    Returns:
        删除的行数
    """
    if not freys:
        return 0

    sql = text("DELETE FROM stock_safe_useless_data WHERE frey_no IN :freys")
    result = session.execute(sql, {"freys": tuple(freys)})
    return result.rowcount  # pyright: ignore[reportAttributeAccessIssue]