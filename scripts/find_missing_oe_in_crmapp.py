"""
查找昨天上传的virtual_inventory数据中，在crmapp_compare_summary中不存在的OE码
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pymysql
import pandas as pd
from app.utils.database_connection import get_db_connection


def find_missing_oe():
    """查找缺失的OE+Brand组合"""
    print("=" * 80)
    print("【查找缺失OE+Brand组合】virtual_inventory vs crmapp_compare_summary")
    print("=" * 80)

    # 计算昨天的日期范围
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)

    print(f"\n查询日期范围: {yesterday_start.strftime('%Y-%m-%d %H:%M:%S')} 到 {yesterday_end.strftime('%Y-%m-%d %H:%M:%S')}")

    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. 获取昨天的virtual_inventory数据（update_status为上传成功的）
            print("\n【查询virtual_inventory数据】")
            cursor.execute("""
                SELECT * 
                FROM virtual_inventory 
                WHERE fetch_time >= %s AND fetch_time <= %s
                  AND update_status = '上传成功'
            """, (yesterday_start, yesterday_end))
            virtual_data = cursor.fetchall()
            print(f"找到 {len(virtual_data)} 条昨天上传成功的数据")

            if not virtual_data:
                print("\n没有找到符合条件的数据，脚本结束。")
                return

            # 2. 获取所有需要检查的 (oe, brand) 组合
            virtual_oe_brand_set = set()
            for row in virtual_data:
                oe = row.get('oe_code')
                brand = row.get('brand')
                if oe:
                    virtual_oe_brand_set.add((oe, brand))
            print(f"共 {len(virtual_oe_brand_set)} 个不同的 (OE, Brand) 组合")

            # 3. 获取crmapp_compare_summary中存在的 (oe, brand) 组合
            print("\n【查询crmapp_compare_summary数据】")
            # 构建查询条件
            conditions = []
            params = []
            for oe, brand in virtual_oe_brand_set:
                conditions.append("(oe = %s AND brand = %s)")
                params.extend([oe, brand])
            
            where_clause = " OR ".join(conditions)
            cursor.execute(f"""
                SELECT DISTINCT oe, brand 
                FROM crmapp_compare_summary 
                WHERE {where_clause}
            """, params)
            crmapp_oe_brand_rows = cursor.fetchall()
            crmapp_oe_brand_set = {(row['oe'], row['brand']) for row in crmapp_oe_brand_rows}
            print(f"在crmapp_compare_summary中找到 {len(crmapp_oe_brand_set)} 个匹配的 (OE, Brand) 组合")

            # 4. 找出缺失的 (oe, brand) 组合
            missing_oe_brand_set = virtual_oe_brand_set - crmapp_oe_brand_set
            print(f"\n【结果】在crmapp_compare_summary中不存在的 (OE, Brand) 组合数量: {len(missing_oe_brand_set)}")

            # 5. 筛选出缺失 (OE, Brand) 组合对应的所有virtual_inventory记录
            missing_data = []
            for row in virtual_data:
                oe = row.get('oe_code')
                brand = row.get('brand')
                if (oe, brand) in missing_oe_brand_set:
                    missing_data.append(row)

            if not missing_data:
                print("\n没有找到缺失的数据，脚本结束。")
                return

            print(f"共 {len(missing_data)} 条记录需要导出")

            # 6. 导出到Excel
            df = pd.DataFrame(missing_data)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"missing_oe_{timestamp}.xlsx"
            filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filename)
            
            df.to_excel(filepath, index=False, engine='openpyxl')
            print(f"\n✓ 数据已导出到: {filepath}")

            # 打印部分示例
            print("\n【前10条缺失数据示例】")
            for i, row in enumerate(missing_data[:10]):
                print(f"  {i+1}. OE: {row.get('oe_code')}, Brand: {row.get('brand')}, 供应商: {row.get('supplier_name')}")

    finally:
        conn.close()


if __name__ == '__main__':
    find_missing_oe()
