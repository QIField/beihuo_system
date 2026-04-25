"""
单产品调试脚本 - 追踪 P11377615379 YCGN 的数据来源
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from datetime import datetime, timedelta
from app.utils.database_connection import get_db_connection


def debug_product(frey_no):
    """调试单个产品的数据处理流程"""
    print("=" * 80)
    print(f"【调试产品】frey_no: {frey_no}")
    print("=" * 80)

    # 步骤1: 查询销量表数据
    print("\n【步骤1】查询销量表 (crmapp_sales_history_detail)")
    print("-" * 80)
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 查询近1年的销量数据
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            
            sql = """
                SELECT 
                    frey_no,
                    number as oe,
                    brand_name as brand,
                    quantity,
                    create_date
                FROM crmapp_sales_history_detail
                WHERE frey_no = %s
                  AND create_date >= %s
                  AND create_date <= %s
                ORDER BY create_date
            """
            cursor.execute(sql, (frey_no, start_date, end_date))
            rows = cursor.fetchall()
            
            total_sales = sum(float(row['quantity'] or 0) for row in rows)
            print(f"  查询条件: frey_no='{frey_no}', 日期范围 {start_date} 到 {end_date}")
            print(f"  销量记录数: {len(rows)}")
            print(f"  总销量: {total_sales}")
            
            if rows:
                print(f"  第一条记录: OE={rows[0]['oe']}, 品牌={rows[0]['brand']}, 数量={rows[0]['quantity']}, 日期={rows[0]['create_date']}")
                print(f"  最后一条记录: OE={rows[-1]['oe']}, 品牌={rows[-1]['brand']}, 数量={rows[-1]['quantity']}, 日期={rows[-1]['create_date']}")
            else:
                print("  ⚠️ 没有找到销量记录")
    finally:
        conn.close()

    # 步骤2: 查询库存表数据
    print("\n【步骤2】查询库存表 (crmapp_beihuo)")
    print("-" * 80)
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT
                    物料条码 as frey_no,
                    oe,
                    品牌 as brand,
                    物料名称 as product_name,
                    库存数量 as stock_qty,
                    库存金额 as inventory_amount
                FROM crmapp_beihuo
                WHERE 物料条码 = %s
            """
            cursor.execute(sql, (frey_no,))
            rows = cursor.fetchall()
            
            print(f"  查询条件: 物料条码='{frey_no}'")
            print(f"  库存记录数: {len(rows)}")
            
            if rows:
                for i, row in enumerate(rows):
                    print(f"  记录{i+1}: OE={row['oe']}, 品牌={row['brand']}, 物料名称={row['product_name']}, 库存数量={row['stock_qty']}")
                
                # 计算合并后的库存
                total_stock = sum(float(row['stock_qty'] or 0) for row in rows)
                print(f"  合并后总库存: {total_stock}")
            else:
                print("  ⚠️ 没有找到库存记录")
    finally:
        conn.close()

    # 步骤3: 查询在途表数据
    print("\n【步骤3】查询在途表 (crmapp_compare_summary)")
    print("-" * 80)
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT
                    frey_no,
                    stock_zaitu_list
                FROM crmapp_compare_summary
                WHERE frey_no = %s
                  AND stock_zaitu_list IS NOT NULL
                  AND stock_zaitu_list != ''
                  AND stock_zaitu_list != '[]'
            """
            cursor.execute(sql, (frey_no,))
            rows = cursor.fetchall()
            
            print(f"  查询条件: frey_no='{frey_no}'")
            print(f"  在途记录数: {len(rows)}")
            
            if rows:
                import json
                for row in rows:
                    try:
                        zaitu_list = json.loads(row['stock_zaitu_list'])
                        if isinstance(zaitu_list, list):
                            total_zaitu = sum(float(item.get('purchase_quantity', 0) or 0) for item in zaitu_list)
                            print(f"  在途数量: {total_zaitu}")
                            for item in zaitu_list:
                                print(f"    - 数量: {item.get('purchase_quantity', 0)}, 供应商: {item.get('supplier_name', '')}")
                    except:
                        print(f"  解析在途数据失败: {row['stock_zaitu_list']}")
            else:
                print("  ⚠️ 没有找到在途记录")
    finally:
        conn.close()

    # 步骤4: 模拟计算过程
    print("\n【步骤4】模拟安全库存计算")
    print("-" * 80)
    
    # 重新获取数据进行计算
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 获取销量数据
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT quantity, create_date
                FROM crmapp_sales_history_detail
                WHERE frey_no = %s
                  AND create_date >= %s
                  AND create_date <= %s
            """, (frey_no, start_date, end_date))
            sales_rows = cursor.fetchall()
            
            if sales_rows:
                from collections import defaultdict
                daily_sales = defaultdict(float)
                for row in sales_rows:
                    create_date = row['create_date']
                    if isinstance(create_date, str):
                        create_date = datetime.strptime(create_date, '%Y-%m-%d %H:%M:%S')
                    sale_date = create_date.strftime('%Y-%m-%d')
                    daily_sales[sale_date] += float(row['quantity'] or 0)
                
                total_days = 365
                total_sales = sum(daily_sales.values())
                avg_daily = total_sales / total_days
                
                daily_sales_list = list(daily_sales.values())
                if len(daily_sales_list) > 1:
                    variance = sum((x - avg_daily) ** 2 for x in daily_sales_list) / len(daily_sales_list)
                    std_daily = variance ** 0.5
                else:
                    std_daily = 0
                
                print(f"  统计天数: {total_days}")
                print(f"  总销量: {total_sales}")
                print(f"  平均日销量: {avg_daily:.4f}")
                print(f"  销量标准差: {std_daily:.4f}")
                
                # 计算安全库存 (简化版)
                z_factor = 1.2  # B类产品
                lead_time = 1
                base_safety_stock = z_factor * std_daily * (lead_time ** 0.5)
                print(f"  基础安全库存: {base_safety_stock:.2f}")
            else:
                print("  没有销量数据，无法计算")
    finally:
        conn.close()

    print("\n" + "=" * 80)
    print("【调试完成】")
    print("=" * 80)


if __name__ == '__main__':
    # 调试用户指定的产品
    test_frey_no = 'P11377615379 YCGN'
    debug_product(test_frey_no)
