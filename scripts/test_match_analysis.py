"""
匹配分析测试脚本
用于分析 frey_no 与 物料条码 的匹配情况，以及 oe+brand 的分布
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from collections import defaultdict
from app.utils.database_connection import get_db_connection


def analyze_sales_data():
    """分析销量表中的 frey_no 和 oe+brand 分布"""
    print("=" * 80)
    print("【销量表分析】crmapp_sales_history_detail")
    print("=" * 80)

    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. 统计总记录数
            cursor.execute("SELECT COUNT(*) as total FROM crmapp_sales_history_detail")
            total = cursor.fetchone()['total']
            print(f"\n总记录数: {total}")

            # 2. 统计有 frey_no 的记录数
            cursor.execute("""
                SELECT COUNT(*) as count FROM crmapp_sales_history_detail
                WHERE frey_no IS NOT NULL AND frey_no != ''
            """)
            has_frey_no = cursor.fetchone()['count']
            print(f"有 frey_no 的记录数: {has_frey_no} ({has_frey_no/total*100:.2f}%)")

            # 3. 统计唯一的 frey_no 数量
            cursor.execute("""
                SELECT COUNT(DISTINCT frey_no) as count FROM crmapp_sales_history_detail
                WHERE frey_no IS NOT NULL AND frey_no != ''
            """)
            unique_frey_no = cursor.fetchone()['count']
            print(f"唯一的 frey_no 数量: {unique_frey_no}")

            # 4. 统计唯一的 oe+brand 组合数量
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(number, '|', brand_name)) as count
                FROM crmapp_sales_history_detail
                WHERE number IS NOT NULL AND number != ''
                  AND brand_name IS NOT NULL AND brand_name != ''
            """)
            unique_oe_brand = cursor.fetchone()['count']
            print(f"唯一的 oe+brand 组合数量: {unique_oe_brand}")

            # 5. 分析同一个 frey_no 对应多个 oe+brand 的情况
            print("\n【frey_no 与 oe+brand 的对应关系分析】")
            cursor.execute("""
                SELECT
                    frey_no,
                    COUNT(DISTINCT number) as oe_count,
                    COUNT(DISTINCT brand_name) as brand_count,
                    COUNT(DISTINCT CONCAT(number, '|', brand_name)) as oe_brand_count,
                    GROUP_CONCAT(DISTINCT number SEPARATOR ', ') as oes,
                    GROUP_CONCAT(DISTINCT brand_name SEPARATOR ', ') as brands
                FROM crmapp_sales_history_detail
                WHERE frey_no IS NOT NULL AND frey_no != ''
                GROUP BY frey_no
                HAVING oe_brand_count > 1
                LIMIT 20
            """)
            multi_mapping = cursor.fetchall()

            if multi_mapping:
                print(f"\n发现 {len(multi_mapping)} 个 frey_no 对应多个 oe+brand（仅展示前20个）:")
                print("-" * 80)
                for row in multi_mapping:
                    print(f"frey_no: {row['frey_no']}")
                    print(f"  对应 {row['oe_brand_count']} 个 oe+brand 组合")
                    print(f"  OE列表: {row['oes']}")
                    print(f"  品牌列表: {row['brands']}")
                    print()
            else:
                print("\n没有发现 frey_no 对应多个 oe+brand 的情况")

            # 6. 统计 frey_no 对应 oe+brand 数量的分布
            print("\n【frey_no 对应 oe+brand 数量分布】")
            cursor.execute("""
                SELECT
                    oe_brand_count,
                    COUNT(*) as frey_no_count
                FROM (
                    SELECT
                        frey_no,
                        COUNT(DISTINCT CONCAT(number, '|', brand_name)) as oe_brand_count
                    FROM crmapp_sales_history_detail
                    WHERE frey_no IS NOT NULL AND frey_no != ''
                    GROUP BY frey_no
                ) t
                GROUP BY oe_brand_count
                ORDER BY oe_brand_count
            """)
            distribution = cursor.fetchall()

            print("-" * 40)
            print(f"{'oe+brand数量':<15} {'frey_no数量':<15}")
            print("-" * 40)
            for row in distribution:
                print(f"{row['oe_brand_count']:<15} {row['frey_no_count']:<15}")

    finally:
        conn.close()


def analyze_inventory_data():
    """分析库存表中的 物料条码 和 oe+品牌 分布"""
    print("\n" + "=" * 80)
    print("【库存表分析】crmapp_beihuo")
    print("=" * 80)

    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. 统计总记录数
            cursor.execute("SELECT COUNT(*) as total FROM crmapp_beihuo")
            total = cursor.fetchone()['total']
            print(f"\n总记录数: {total}")

            # 2. 统计有 物料条码 的记录数
            cursor.execute("""
                SELECT COUNT(*) as count FROM crmapp_beihuo
                WHERE 物料条码 IS NOT NULL AND 物料条码 != ''
            """)
            has_barcode = cursor.fetchone()['count']
            print(f"有 物料条码 的记录数: {has_barcode} ({has_barcode/total*100:.2f}%)")

            # 3. 统计唯一的 物料条码 数量
            cursor.execute("""
                SELECT COUNT(DISTINCT 物料条码) as count FROM crmapp_beihuo
                WHERE 物料条码 IS NOT NULL AND 物料条码 != ''
            """)
            unique_barcode = cursor.fetchone()['count']
            print(f"唯一的 物料条码 数量: {unique_barcode}")

            # 4. 统计唯一的 oe+品牌 组合数量
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(oe, '|', 品牌)) as count
                FROM crmapp_beihuo
                WHERE oe IS NOT NULL AND oe != ''
                  AND 品牌 IS NOT NULL AND 品牌 != ''
            """)
            unique_oe_brand = cursor.fetchone()['count']
            print(f"唯一的 oe+品牌 组合数量: {unique_oe_brand}")

            # 5. 分析同一个 物料条码 对应多个 oe+品牌 的情况
            print("\n【物料条码 与 oe+品牌 的对应关系分析】")
            cursor.execute("""
                SELECT
                    物料条码,
                    COUNT(DISTINCT oe) as oe_count,
                    COUNT(DISTINCT 品牌) as brand_count,
                    COUNT(DISTINCT CONCAT(oe, '|', 品牌)) as oe_brand_count,
                    GROUP_CONCAT(DISTINCT oe SEPARATOR ', ') as oes,
                    GROUP_CONCAT(DISTINCT 品牌 SEPARATOR ', ') as brands
                FROM crmapp_beihuo
                WHERE 物料条码 IS NOT NULL AND 物料条码 != ''
                GROUP BY 物料条码
                HAVING oe_brand_count > 1
                LIMIT 20
            """)
            multi_mapping = cursor.fetchall()

            if multi_mapping:
                print(f"\n发现 {len(multi_mapping)} 个 物料条码 对应多个 oe+品牌（仅展示前20个）:")
                print("-" * 80)
                for row in multi_mapping:
                    print(f"物料条码: {row['物料条码']}")
                    print(f"  对应 {row['oe_brand_count']} 个 oe+品牌 组合")
                    print(f"  OE列表: {row['oes']}")
                    print(f"  品牌列表: {row['brands']}")
                    print()
            else:
                print("\n没有发现 物料条码 对应多个 oe+品牌 的情况")

            # 6. 统计 物料条码 对应 oe+品牌 数量的分布
            print("\n【物料条码 对应 oe+品牌 数量分布】")
            cursor.execute("""
                SELECT
                    oe_brand_count,
                    COUNT(*) as barcode_count
                FROM (
                    SELECT
                        物料条码,
                        COUNT(DISTINCT CONCAT(oe, '|', 品牌)) as oe_brand_count
                    FROM crmapp_beihuo
                    WHERE 物料条码 IS NOT NULL AND 物料条码 != ''
                    GROUP BY 物料条码
                ) t
                GROUP BY oe_brand_count
                ORDER BY oe_brand_count
            """)
            distribution = cursor.fetchall()

            print("-" * 40)
            print(f"{'oe+品牌数量':<15} {'物料条码数量':<15}")
            print("-" * 40)
            for row in distribution:
                print(f"{row['oe_brand_count']:<15} {row['barcode_count']:<15}")

    finally:
        conn.close()


def test_match():
    """测试 frey_no 和 物料条码 的匹配情况"""
    print("\n" + "=" * 80)
    print("【匹配测试】frey_no vs 物料条码")
    print("=" * 80)

    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. 获取销量表中的所有 frey_no
            cursor.execute("""
                SELECT DISTINCT frey_no
                FROM crmapp_sales_history_detail
                WHERE frey_no IS NOT NULL AND frey_no != ''
            """)
            sales_frey_nos = set(row['frey_no'] for row in cursor.fetchall())
            print(f"\n销量表中的 frey_no 数量: {len(sales_frey_nos)}")

            # 2. 获取库存表中的所有 物料条码
            cursor.execute("""
                SELECT DISTINCT 物料条码
                FROM crmapp_beihuo
                WHERE 物料条码 IS NOT NULL AND 物料条码 != ''
            """)
            inventory_barcodes = set(row['物料条码'] for row in cursor.fetchall())
            print(f"库存表中的 物料条码 数量: {len(inventory_barcodes)}")

            # 3. 计算匹配情况
            matched = sales_frey_nos & inventory_barcodes
            only_in_sales = sales_frey_nos - inventory_barcodes
            only_in_inventory = inventory_barcodes - sales_frey_nos

            print(f"\n【匹配结果】")
            print("-" * 40)
            print(f"双向匹配数量: {len(matched)}")
            print(f"仅在销量表中的 frey_no: {len(only_in_sales)}")
            print(f"仅在库存表中的 物料条码: {len(only_in_inventory)}")
            print(f"匹配率: {len(matched)/len(sales_frey_nos)*100:.2f}%" if sales_frey_nos else "N/A")

            # 4. 展示一些未匹配的例子
            if only_in_sales:
                print(f"\n【仅在销量表中的 frey_no 示例（前10个）】")
                for frey_no in list(only_in_sales)[:10]:
                    print(f"  - {frey_no}")

            if only_in_inventory:
                print(f"\n【仅在库存表中的 物料条码 示例（前10个）】")
                for barcode in list(only_in_inventory)[:10]:
                    print(f"  - {barcode}")

            # 5. 展示匹配成功的示例
            if matched:
                print(f"\n【匹配成功的示例（前10个）】")
                for frey_no in list(matched)[:10]:
                    print(f"  - {frey_no}")

    finally:
        conn.close()


def test_oe_brand_match():
    """测试传统的 oe+brand 匹配情况"""
    print("\n" + "=" * 80)
    print("【传统匹配测试】oe+brand")
    print("=" * 80)

    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. 获取销量表中的所有 oe+brand
            cursor.execute("""
                SELECT DISTINCT CONCAT(number, '|', brand_name) as oe_brand
                FROM crmapp_sales_history_detail
                WHERE number IS NOT NULL AND number != ''
                  AND brand_name IS NOT NULL AND brand_name != ''
            """)
            sales_oe_brands = set(row['oe_brand'] for row in cursor.fetchall())
            print(f"\n销量表中的 oe+brand 组合数量: {len(sales_oe_brands)}")

            # 2. 获取库存表中的所有 oe+品牌
            cursor.execute("""
                SELECT DISTINCT CONCAT(oe, '|', 品牌) as oe_brand
                FROM crmapp_beihuo
                WHERE oe IS NOT NULL AND oe != ''
                  AND 品牌 IS NOT NULL AND 品牌 != ''
            """)
            inventory_oe_brands = set(row['oe_brand'] for row in cursor.fetchall())
            print(f"库存表中的 oe+品牌 组合数量: {len(inventory_oe_brands)}")

            # 3. 计算匹配情况
            matched = sales_oe_brands & inventory_oe_brands
            only_in_sales = sales_oe_brands - inventory_oe_brands
            only_in_inventory = inventory_oe_brands - sales_oe_brands

            print(f"\n【匹配结果】")
            print("-" * 40)
            print(f"双向匹配数量: {len(matched)}")
            print(f"仅在销量表中的组合: {len(only_in_sales)}")
            print(f"仅在库存表中的组合: {len(only_in_inventory)}")
            print(f"匹配率: {len(matched)/len(sales_oe_brands)*100:.2f}%" if sales_oe_brands else "N/A")

    finally:
        conn.close()


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("安全库存匹配分析工具")
    print("=" * 80)

    try:
        analyze_sales_data()
        analyze_inventory_data()
        test_match()
        test_oe_brand_match()

        print("\n" + "=" * 80)
        print("分析完成")
        print("=" * 80)

    except Exception as e:
        print(f"\n分析过程中出错: {e}")
        import traceback
        traceback.print_exc()
