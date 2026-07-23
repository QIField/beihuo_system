"""
多渠道报价调价 - 数据访问层

职责：
- supplier_info 表查询
- qq_msg 表写入
- multi_channel_quote_import 表写入/查询
"""

from datetime import datetime
from typing import List, Dict, Any

from app.utils.database_connection import db_cursor


def fetch_suppliers_by_car_brand(car_brand: str) -> List[Dict[str, Any]]:
    """
    根据车辆品牌从 supplier_info 表查询匹配的供应商

    匹配规则：supplier_info.car_brand 包含输入的车辆品牌即匹配
    （如车辆品牌为'宝马'，可匹配 '宝马'、'奔驰/宝马' 等记录）
    """
    if not car_brand:
        return []

    sql = """
        SELECT `id`, `supplier`, `car_brand`, `main_business`
        FROM `supplier_info`
        WHERE `car_brand` LIKE %s
    """
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, (f"%{car_brand}%",))
        return cursor.fetchall()


def save_to_qq_msg(rows: List[Dict[str, Any]]) -> None:
    """
    将 OE / 供应商 / QQ 保存到 qq_msg 表

    Args:
        rows: 展开后的行，每个元素包含 oe, supplier_text, qq
    """
    if not rows:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    insert_sql = """
        INSERT INTO `qq_msg` (`OE`, `供应商`, `QQ`, `状态`, `读取时间`)
        VALUES (%s, %s, %s, %s, %s)
    """

    with db_cursor(dict_cursor=False) as cursor:
        for row in rows:
            cursor.execute(
                insert_sql,
                (
                    row.get("oe", ""),
                    row.get("supplier_text", ""),
                    row.get("qq", ""),
                    "待处理",
                    now,
                ),
            )


def save_import_records(rows: List[Dict[str, Any]], create_by: str = "") -> None:
    """
    将导入的 OE 关键字段保存到 multi_channel_quote_import 表

    Args:
        rows: 合并后的行，每个元素包含 oe, brand, car_brand, supplier_text, qq
        create_by: 导入人
    """
    if not rows:
        return

    insert_sql = """
        INSERT INTO `multi_channel_quote_import`
        (`oe`, `brand`, `car_brand`, `inquiry_supplier`, `create_by`, `create_time`)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """

    with db_cursor(dict_cursor=False) as cursor:
        for row in rows:
            cursor.execute(
                insert_sql,
                (
                    row.get("oe", ""),
                    row.get("brand", ""),
                    row.get("car_brand", ""),
                    row.get("supplier_text", ""),
                    create_by,
                ),
            )


def fetch_recent_imports(hours: int = 36) -> List[Dict[str, Any]]:
    """
    查询最近 N 小时内导入的 OE 关键字段

    Args:
        hours: 时间窗口（小时），默认 36 小时

    Returns:
        行列表，每个元素包含 oe, brand, car_brand, supplier_text（即 inquiry_supplier）, qq
    """
    sql = """
        SELECT DISTINCT `oe`, `brand`, `car_brand`, `inquiry_supplier`
        FROM `multi_channel_quote_import`
        WHERE `create_time` >= DATE_SUB(NOW(), INTERVAL %s HOUR)
        ORDER BY `create_time` DESC
    """

    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, (hours,))
        rows = cursor.fetchall()

    return [
        {
            "oe": row["oe"],
            "brand": row["brand"],
            "car_brand": row["car_brand"],
            "supplier_text": row["inquiry_supplier"] or "",
            "qq": row["inquiry_supplier"] or "",
        }
        for row in rows
    ]
