"""
虚拟库存五个组织汇总表格与crmapp_compare_summary对比脚本
- 查询virtual_inventory五个组织表中update_msg为'update'和'add'的数据
- 用oe_code和brand组合与crmapp_compare_summary中对应company做对比
- 输出未匹配的oe和brand到excel，第三列为company

五个组织对应的数据表：
- fsbbr → virtual_inventory
- zhbbr → virtual_inventory_zhbbr
- zsbbr → virtual_inventory_zsbbr
- dgby → virtual_inventory_dgby
- dghf → virtual_inventory_dghf
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pymysql
import pandas as pd
from app.utils.database_connection import get_db_connection


# 五个组织对应的数据表
COMPANY_TABLE_MAP = {
    'fsbbr': 'virtual_inventory',
    'zhbbr': 'virtual_inventory_zhbbr',
    'zsbbr': 'virtual_inventory_zsbbr',
    'dgby': 'virtual_inventory_dgby',
    'dghf': 'virtual_inventory_dghf'
}


def get_virtual_inventory_data_by_company(company, table_name, date_start, date_end):
    """
    从指定组织的虚拟库存表中获取update_msg为'update'或'add'的数据
    
    :param company: 组织代码 (fsbbr, zhbbr, zsbbr, dgby, dghf)
    :param table_name: 对应的表名
    :param date_start: 开始时间
    :param date_end: 结束时间
    :return: 数据列表
    """
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(f"""
                SELECT id, supplier_name, oe_code, brand, price, expiry_date, 
                       warehouse, stock, remark, update_msg, fetch_time
                FROM {table_name} 
                WHERE fetch_time >= %s AND fetch_time <= %s
                  AND (LOWER(update_msg) LIKE %s OR LOWER(update_msg) LIKE %s)
            """, (date_start, date_end, '%update%', '%add%'))
            rows = cursor.fetchall()
            # 为每条记录添加company字段
            for row in rows:
                row['company'] = company
            return rows
    finally:
        conn.close()


def compare_virtual_inventory_with_crmapp():
    """
    对比virtual_inventory五个组织表和crmapp_compare_summary数据
    找出未匹配的oe+brand+company组合
    """
    print("=" * 80)
    print("【虚拟库存与CRM APP对比】查找未匹配的OE+Brand+Company组合")
    print("=" * 80)
    
    # 计算2026.5.12的日期范围
    target_date = datetime(2026, 5, 12)
    date_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    date_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    print(f"\n查询日期范围: {date_start.strftime('%Y-%m-%d %H:%M:%S')} 到 {date_end.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 从五个组织的虚拟库存表中获取数据
    print("\n【从五个组织虚拟库存表中查询数据】")
    all_virtual_data = []
    
    for company, table_name in COMPANY_TABLE_MAP.items():
        print(f"  查询 {company} ({table_name})...", end=" ")
        data = get_virtual_inventory_data_by_company(company, table_name, date_start, date_end)
        print(f"找到 {len(data)} 条")
        all_virtual_data.extend(data)
    
    print(f"\n总计找到 {len(all_virtual_data)} 条update_msg为'update'或'add'的数据")
    
    if not all_virtual_data:
        print("\n没有找到符合条件的数据，脚本结束。")
        return
    
    # 2. 构建virtual_inventory中的(oe, brand, company)组合
    print("\n【构建virtual_inventory的OE+Brand+Company组合】")
    virtual_oe_brand_company_set = set()
    
    for row in all_virtual_data:
        oe = row.get('oe_code')
        brand = row.get('brand')
        company = row.get('company')
        
        if oe:
            virtual_oe_brand_company_set.add((oe, brand, company))
    
    print(f"共 {len(virtual_oe_brand_company_set)} 个不同的 (OE, Brand, Company) 组合")
    
    # 3. 使用内存中的集合对比，避免复杂的SQL JOIN
    print("\n【查询crmapp_compare_summary中的OE+Brand+Company组合】")
    
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 只查询五个company的数据
            print("  正在从crmapp_compare_summary查询数据...")
            cursor.execute("""
                SELECT DISTINCT oe, brand, company
                FROM crmapp_compare_summary
                WHERE company IN ('fsbbr', 'zhbbr', 'zsbbr', 'dgby', 'dghf')
            """)
            
            crmapp_rows = cursor.fetchall()
            crmapp_oe_brand_company_set = set()
            
            for row in crmapp_rows:
                brand = row['brand'] if row['brand'] else None
                crmapp_oe_brand_company_set.add((row['oe'], brand, row['company']))
            
            print(f"  从crmapp_compare_summary获取 {len(crmapp_oe_brand_company_set)} 个组合")
            
            # 4. 在Python中进行集合对比，找出未匹配的数据
            print("\n【对比数据】")
            missing_oe_brand_company_set = virtual_oe_brand_company_set - crmapp_oe_brand_company_set
            print(f"在crmapp_compare_summary中不存在的 (OE, Brand, Company) 组合数量: {len(missing_oe_brand_company_set)}")
            
            if not missing_oe_brand_company_set:
                print("\n所有数据都已匹配，没有缺失的数据。")
                return
            
            # 5. 获取缺失组合的详细信息（去重，每个oe+brand+company只保留一条）
            print("\n【整理未匹配数据】")
            missing_data_dict = {}
            
            for row in all_virtual_data:
                oe = row.get('oe_code')
                brand = row.get('brand')
                company = row.get('company')
                key = (oe, brand, company)
                
                if key in missing_oe_brand_company_set and key not in missing_data_dict:
                    missing_data_dict[key] = {
                        'oe_code': oe,
                        'brand': brand,
                        'company': company,
                        'supplier_name': row.get('supplier_name'),
                        'price': row.get('price'),
                        'warehouse': row.get('warehouse'),
                        'stock': row.get('stock'),
                        'update_msg': row.get('update_msg'),
                        'fetch_time': row.get('fetch_time')
                    }
            
            missing_data = list(missing_data_dict.values())
            print(f"共 {len(missing_data)} 条去重后的未匹配记录")
            
            # 6. 导出到Excel
            df = pd.DataFrame(missing_data)
            
            # 调整列顺序，确保oe_code、brand、company在前三列
            column_order = ['oe_code', 'brand', 'company', 'supplier_name', 'price', 
                           'warehouse', 'stock', 'update_msg', 'fetch_time']
            # 只保留存在的列
            column_order = [col for col in column_order if col in df.columns]
            df = df[column_order]
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"unmatched_oe_brand_company_{timestamp}.xlsx"
            filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filename)
            
            df.to_excel(filepath, index=False, engine='openpyxl')
            print(f"\n✓ 数据已导出到: {filepath}")
            
            # 打印统计信息
            print("\n【按Company统计未匹配数量】")
            company_stats = {}
            for row in missing_data:
                company = row.get('company', 'unknown')
                company_stats[company] = company_stats.get(company, 0) + 1
            
            for company, count in sorted(company_stats.items()):
                print(f"  {company}: {count} 条")
            
            # 打印部分示例
            print("\n【前20条未匹配数据示例】")
            for i, row in enumerate(missing_data[:20]):
                print(f"  {i+1}. OE: {row.get('oe_code')}, Brand: {row.get('brand')}, Company: {row.get('company')}, 供应商: {row.get('supplier_name')}")
            
            if len(missing_data) > 20:
                print(f"  ... 还有 {len(missing_data) - 20} 条记录")
    
    finally:
        conn.close()


if __name__ == '__main__':
    compare_virtual_inventory_with_crmapp()
