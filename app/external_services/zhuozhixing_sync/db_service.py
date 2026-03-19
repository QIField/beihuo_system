# -*- coding: utf-8 -*-
"""
数据库服务

负责数据库操作：
1. 清空指定供应商数据
2. 批量插入数据（高性能）
"""

from typing import List, Tuple
from app.utils.database_connection import get_db_connection, db_cursor
from .config import DB_TABLE_NAME, DB_FIELDS, BATCH_SIZE


def clear_supplier_data(supplier_name: str) -> int:
    """
    清空指定供应商的数据

    Args:
        supplier_name: 供应商名称

    Returns:
        删除的行数
    """
    sql = f"DELETE FROM {DB_TABLE_NAME} WHERE supplier_name = %s"

    try:
        with db_cursor(dict_cursor=False) as cursor:
            affected = cursor.execute(sql, (supplier_name,))
            print(f"  ✓ 已清空 {supplier_name} 旧数据: {affected} 条")
            return affected
    except Exception as e:
        print(f"  ✗ 清空数据失败: {e}")
        raise


def batch_insert_records(records: List[Tuple]) -> int:
    """
    批量插入数据（高性能）

    使用 executemany 进行批量插入，性能比单条插入高10-100倍

    Args:
        records: 数据元组列表

    Returns:
        插入的行数
    """
    if not records:
        return 0

    # 构建INSERT语句
    fields_str = ', '.join(DB_FIELDS)
    placeholders = ', '.join(['%s'] * len(DB_FIELDS))
    sql = f"INSERT INTO {DB_TABLE_NAME} ({fields_str}) VALUES ({placeholders})"

    total_inserted = 0

    try:
        with db_cursor(dict_cursor=False) as cursor:
            # 分批插入
            for i in range(0, len(records), BATCH_SIZE):
                batch = records[i:i + BATCH_SIZE]
                cursor.executemany(sql, batch)
                total_inserted += len(batch)
                print(f"    已插入: {total_inserted}/{len(records)} 条")

        print(f"  ✓ 批量插入完成: {total_inserted} 条")
        return total_inserted

    except Exception as e:
        print(f"  ✗ 批量插入失败: {e}")
        raise


def save_supplier_data(supplier_name: str, records: List[Tuple]) -> dict:
    """
    保存供应商数据到数据库

    流程：
    1. 清空该供应商旧数据
    2. 批量插入新数据

    Args:
        supplier_name: 供应商名称
        records: 数据记录列表

    Returns:
        操作结果统计
    """
    print(f"\n[{supplier_name}] 开始保存数据...")

    if not records:
        print(f"  ! 没有数据需要保存")
        return {
            'supplier': supplier_name,
            'deleted': 0,
            'inserted': 0,
            'success': True
        }

    # 清空旧数据
    deleted_count = clear_supplier_data(supplier_name)

    # 插入新数据
    inserted_count = batch_insert_records(records)

    print(f"  ✓ {supplier_name} 数据保存完成")

    return {
        'supplier': supplier_name,
        'deleted': deleted_count,
        'inserted': inserted_count,
        'success': True
    }


def query_data(supplier_name: str = None, limit: int = 100, offset: int = 0) -> List[dict]:
    """
    查询已同步的数据

    Args:
        supplier_name: 供应商名称（可选，None表示查询全部）
        limit: 返回条数
        offset: 偏移量

    Returns:
        数据列表
    """
    if supplier_name:
        sql = f"""
            SELECT * FROM {DB_TABLE_NAME}
            WHERE supplier_name = %s
            ORDER BY sync_time DESC
            LIMIT %s OFFSET %s
        """
        params = (supplier_name, limit, offset)
    else:
        sql = f"""
            SELECT * FROM {DB_TABLE_NAME}
            ORDER BY sync_time DESC, supplier_name
            LIMIT %s OFFSET %s
        """
        params = (limit, offset)

    try:
        with db_cursor(dict_cursor=True) as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    except Exception as e:
        print(f"  ✗ 查询数据失败: {e}")
        return []


def get_data_count(supplier_name: str = None) -> int:
    """
    获取数据总数

    Args:
        supplier_name: 供应商名称（可选）

    Returns:
        数据条数
    """
    if supplier_name:
        sql = f"SELECT COUNT(*) as count FROM {DB_TABLE_NAME} WHERE supplier_name = %s"
        params = (supplier_name,)
    else:
        sql = f"SELECT COUNT(*) as count FROM {DB_TABLE_NAME}"
        params = ()

    try:
        with db_cursor(dict_cursor=True) as cursor:
            cursor.execute(sql, params)
            result = cursor.fetchone()
            return result['count'] if result else 0
    except Exception as e:
        print(f"  ✗ 获取数据总数失败: {e}")
        return 0
