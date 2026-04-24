"""
安全库存数据库服务
负责读取销量、库存数据，保存计算结果
"""

import json
import pymysql
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from app.utils.database_connection import get_db_connection, db_cursor
from .config import TABLE_NAME, SALES_HISTORY_DAYS


class SafetyStockDBService:
    """
    安全库存数据库服务类
    """
    
    @staticmethod
    def init_table():
        """初始化数据表"""
        from app.utils.database.tables.safety_stock_tables import init_safety_stock_calculation_table
        init_safety_stock_calculation_table()
    
    @staticmethod
    def get_sales_data(start_date: str = None, end_date: str = None) -> Dict[str, Dict]:
        """
        从销量明细表读取数据
        
        Args:
            start_date: 开始日期，默认近1年
            end_date: 结束日期，默认今天
            
        Returns:
            字典，key为 "oe|brand"，value包含销量统计信息
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=SALES_HISTORY_DAYS)).strftime('%Y-%m-%d')
            
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 读取销量明细，按frey_no分组
                # 简化SQL，在Python中处理日期格式化
                sql = """
                    SELECT 
                        frey_no,
                        quantity,
                        create_date
                    FROM crmapp_sales_history_detail
                    WHERE create_date >= %s
                      AND create_date <= %s
                      AND frey_no IS NOT NULL 
                      AND frey_no != ''
                    ORDER BY frey_no, create_date
                """
                cursor.execute(sql, (start_date, end_date))
                rows = cursor.fetchall()
                
                # 按frey_no分组统计
                product_data = defaultdict(lambda: {
                    'frey_no': '',
                    'daily_sales': defaultdict(float),  # 按天统计销量
                    'monthly_sales': defaultdict(float),  # 按月统计销量
                    'total_sales': 0,
                    'sale_days': set()  # 有销售的天数
                })
                
                for row in rows:
                    key = f"{row['frey_no']}"
                    # 在Python中处理日期格式化
                    create_date = row['create_date']
                    if isinstance(create_date, str):
                        create_date = datetime.strptime(create_date, '%Y-%m-%d %H:%M:%S')
                    
                    sale_date = create_date.strftime('%Y-%m-%d')
                    year_month = create_date.strftime('%Y-%m')
                    
                    product_data[key]['frey_no'] = row['frey_no']
                    product_data[key]['daily_sales'][sale_date] += float(row['quantity'] or 0)
                    product_data[key]['monthly_sales'][year_month] += float(row['quantity'] or 0)
                    product_data[key]['total_sales'] += float(row['quantity'] or 0)
                    product_data[key]['sale_days'].add(sale_date)
                
                # 计算平均日销量和标准差
                result = {}
                for key, data in product_data.items():
                    daily_sales_list = list(data['daily_sales'].values())
                    total_days = (datetime.strptime(end_date, '%Y-%m-%d') - 
                                 datetime.strptime(start_date, '%Y-%m-%d')).days + 1
                    
                    # 平均日销量 = 总销量 / 统计天数
                    avg_daily = data['total_sales'] / total_days if total_days > 0 else 0
                    
                    # 标准差计算
                    if len(daily_sales_list) > 1:
                        variance = sum((x - avg_daily) ** 2 for x in daily_sales_list) / len(daily_sales_list)
                        std_daily = variance ** 0.5
                    else:
                        std_daily = 0
                    
                    # 转换月销量字典格式 {1:销量, 2:销量...}
                    monthly_sales = {}
                    for ym, qty in data['monthly_sales'].items():
                        month = int(ym.split('-')[1])
                        monthly_sales[month] = monthly_sales.get(month, 0) + qty
                    
                    result[key] = {
                        'frey_no': data['frey_no'],
                        'total_sales': data['total_sales'],
                        'avg_daily': avg_daily,
                        'std_daily': std_daily,
                        'monthly_sales': monthly_sales
                    }
                
                return result
                
        finally:
            conn.close()
    
    @staticmethod
    def get_inventory_data() -> Dict[str, Dict]:
        """
        从库存表读取当前库存数据
        
        Returns:
            字典，key为 "frey_no"，value包含库存信息
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                    SELECT 
                        物料条码 as frey_no,
                        物料名称 as product_name,
                        库存数量 as stock_qty,
                        库存金额 as inventory_amount
                    FROM crmapp_beihuo
                    WHERE 物料条码 IS NOT NULL 
                      AND 物料条码 != ''
                """
                cursor.execute(sql)
                rows = cursor.fetchall()
                
                result = {}
                for row in rows:
                    key = f"{row['frey_no']}"
                    result[key] = {
                        'frey_no': row['frey_no'],
                        'product_name': row['product_name'],
                        'stock_qty': float(row['stock_qty'] or 0),
                        'inventory_amount': float(row['inventory_amount'] or 0)
                    }
                
                return result
                
        finally:
            conn.close()
    
    @staticmethod
    def get_in_transit_data() -> Dict[str, float]:
        """
        从在途库存表读取在途数量
        
        Returns:
            字典，key为 "oe|brand"，value为在途数量
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                    SELECT 
                        oe,
                        brand,
                        stock_zaitu_list
                    FROM crmapp_compare_summary
                    WHERE stock_zaitu_list IS NOT NULL
                      AND stock_zaitu_list != ''
                      AND stock_zaitu_list != '[]'
                      AND stock_zaitu_list != '{}'
                """
                cursor.execute(sql)
                rows = cursor.fetchall()
                
                result = {}
                for row in rows:
                    key = f"{row['oe']}|{row['brand']}"
                    try:
                        zaitu_list = json.loads(row['stock_zaitu_list'])
                        if isinstance(zaitu_list, list):
                            # 累加所有在途数量
                            total_qty = sum(
                                float(item.get('purchase_quantity', 0) or 0) 
                                for item in zaitu_list
                            )
                            result[key] = total_qty
                    except:
                        continue
                
                return result
                
        finally:
            conn.close()
    
    @staticmethod
    def save_calculation_results(results: List[Dict], calc_date: str = None) -> int:
        """
        保存计算结果到数据库
        
        Args:
            results: 计算结果列表
            calc_date: 计算日期，默认今天
            
        Returns:
            保存的记录数
        """
        if calc_date is None:
            calc_date = datetime.now().strftime('%Y-%m-%d')
            
        if not results:
            return 0
            
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 先删除当天的旧数据
                delete_sql = f"DELETE FROM {TABLE_NAME} WHERE calc_date = %s"
                cursor.execute(delete_sql, (calc_date,))
                
                # 插入新数据
                insert_sql = f"""
                    INSERT INTO {TABLE_NAME} (
                        frey_no, product_name, abc_class,
                        avg_daily_sales, sales_std, seasonal_factor,
                        base_safety_stock, safety_stock,
                        reorder_point, target_stock,
                        current_stock, in_transit_qty, available_stock, inventory_amount,
                        sellable_days, stock_status, calc_date
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """
                
                values = []
                for r in results:
                    values.append((
                        r['frey_no'],
                        r.get('product_name', ''),
                        r['abc_class'],
                        r['avg_daily_sales'],
                        r['sales_std'],
                        r['seasonal_factor'],
                        r['base_safety_stock'],
                        r['safety_stock'],
                        r['reorder_point'],
                        r['target_stock'],
                        r['current_stock'],
                        r['in_transit_qty'],
                        r['available_stock'],
                        r.get('inventory_amount', 0),
                        r['sellable_days'],
                        r['stock_status'],
                        calc_date
                    ))
                
                cursor.executemany(insert_sql, values)
                conn.commit()
                return len(values)
                
        except Exception as e:
            print(f"保存计算结果失败: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()
    
    @staticmethod
    def get_calculation_results(calc_date: str = None, 
                                stock_status: str = None,
                                abc_class: str = None,
                                limit: int = 1000) -> List[Dict]:
        """
        查询计算结果
        
        Args:
            calc_date: 计算日期，默认最新日期
            stock_status: 库存状态筛选
            abc_class: ABC分类筛选
            limit: 返回条数限制
            
        Returns:
            计算结果列表
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 如果没有指定日期，取最新日期
                if calc_date is None:
                    cursor.execute(f"SELECT MAX(calc_date) as max_date FROM {TABLE_NAME}")
                    row = cursor.fetchone()
                    calc_date = row['max_date'] if row and row['max_date'] else datetime.now().strftime('%Y-%m-%d')
                
                # 构建查询条件
                where_conditions = ["calc_date = %s"]
                params = [calc_date]
                
                if stock_status:
                    where_conditions.append("stock_status = %s")
                    params.append(stock_status)
                    
                if abc_class:
                    where_conditions.append("abc_class = %s")
                    params.append(abc_class)
                
                where_clause = " AND ".join(where_conditions)
                
                sql = f"""
                    SELECT * FROM {TABLE_NAME}
                    WHERE {where_clause}
                    ORDER BY 
                        CASE abc_class 
                            WHEN 'A' THEN 1 
                            WHEN 'B' THEN 2 
                            WHEN 'C' THEN 3 
                        END,
                        available_stock ASC
                    LIMIT %s
                """
                params.append(limit)
                
                cursor.execute(sql, params)
                return cursor.fetchall()
                
        finally:
            conn.close()
    
    @staticmethod
    def delete_old_data(keep_days: int = 30) -> int:
        """
        清理历史数据
        
        Args:
            keep_days: 保留最近多少天的数据
            
        Returns:
            删除的记录数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cutoff_date = (datetime.now() - timedelta(days=keep_days)).strftime('%Y-%m-%d')
                sql = f"DELETE FROM {TABLE_NAME} WHERE calc_date < %s"
                cursor.execute(sql, (cutoff_date,))
                deleted = cursor.rowcount
                conn.commit()
                return deleted
        finally:
            conn.close()
