# -*- coding: utf-8 -*-
"""
物料在途库存 - 查询服务（只读）

按公司 + 物料条码(frey_no)获取当前在途明细。

刻意使用原生 PyMySQL（get_db_connection）而非 ORM：
本接口要解释的"在途数量"单元格来自同一 PyMySQL 连接（/api/beihuo 等），
明细必须与该数字同源，避免 ORM 与原生两套库配置错位导致明细查不到。
"""

import pymysql.cursors

from app.utils.database_connection import get_db_connection


def _date_str(value):
    """Date 转 'YYYY-MM-DD' 字符串，空值返回空串"""
    return value.strftime('%Y-%m-%d') if value else ''


def find_intransit_details(company, frey_no):
    """
    查询指定公司下某物料条码的当前在途明细

    :param company: 公司代码（由后端 get_user_store() 确定，不信任前端传入）
    :param frey_no: 物料条码
    :return: list[dict]，按预计到货日期升序
    """
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        cursor.execute(
            """
            SELECT supplier_name, purchase_quantity, price,
                   order_date, expected_delivery_date, warehouse_name
            FROM b2b_intransit_stock
            WHERE company = %s AND frey_no = %s
            ORDER BY expected_delivery_date ASC
            """,
            (company, frey_no)
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return [
        {
            'supplier_name': row['supplier_name'] or '',
            'purchase_quantity': row['purchase_quantity'],
            'price': float(row['price']) if row['price'] is not None else None,
            'order_date': _date_str(row['order_date']),
            'expected_delivery_date': _date_str(row['expected_delivery_date']),
            'warehouse_name': row['warehouse_name'] or '',
        }
        for row in rows
    ]
