"""
检查库存表数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from app.utils.database_connection import get_db_connection


def check_inventory_data():
    """检查库存表数据"""
    print("=" * 80)
    print("【检查库存表数据】crmapp_beihuo")
    print("=" * 80)

    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. 统计有物料名称的记录数
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM crmapp_beihuo 
                WHERE 物料名称 IS NOT NULL AND 物料名称 != ''
            """)
            has_name = cursor.fetchone()['count']
            print(f"\n有物料名称的记录数: {has_name}")

            # 2. 统计没有物料名称的记录数
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM crmapp_beihuo 
                WHERE 物料名称 IS NULL OR 物料名称 = ''
            """)
            no_name = cursor.fetchone()['count']
            print(f"没有物料名称的记录数: {no_name}")

            # 3. 查看几个有物料名称的示例
            print("\n【有物料名称的示例】")
            cursor.execute("""
                SELECT 物料条码, 物料名称, oe, 品牌
                FROM crmapp_beihuo 
                WHERE 物料名称 IS NOT NULL AND 物料名称 != ''
                LIMIT 5
            """)
            rows = cursor.fetchall()
            for row in rows:
                print(f"  物料条码: {row['物料条码']}, 物料名称: {row['物料名称']}, OE: {row['oe']}, 品牌: {row['品牌']}")

            # 4. 查看几个没有物料名称的示例
            print("\n【没有物料名称的示例】")
            cursor.execute("""
                SELECT 物料条码, 物料名称, oe, 品牌
                FROM crmapp_beihuo 
                WHERE 物料名称 IS NULL OR 物料名称 = ''
                LIMIT 5
            """)
            rows = cursor.fetchall()
            for row in rows:
                print(f"  物料条码: {row['物料条码']}, 物料名称: {row['物料名称']}, OE: {row['oe']}, 品牌: {row['品牌']}")

            # 5. 检查特定的 frey_no（从截图中看到的）
            print("\n【检查特定 frey_no 的数据】")
            test_frey_nos = ['700406501', '700500301', '700500401']
            for frey_no in test_frey_nos:
                cursor.execute("""
                    SELECT 物料条码, 物料名称, oe, 品牌, 库存数量
                    FROM crmapp_beihuo 
                    WHERE 物料条码 = %s
                """, (frey_no,))
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        print(f"  {frey_no}: 名称={row['物料名称']}, OE={row['oe']}, 品牌={row['品牌']}, 库存={row['库存数量']}")
                else:
                    print(f"  {frey_no}: 未找到")

    finally:
        conn.close()


if __name__ == '__main__':
    check_inventory_data()
