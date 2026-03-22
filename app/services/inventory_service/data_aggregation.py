# -*- coding: utf-8 -*-
"""
数据聚合模块
从多个数据源查询并聚合安全库存计算所需的数据
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import statistics
from app.utils.database_connection import get_db_connection


class InventoryDataAggregator:
    """库存数据聚合器"""
    
    def __init__(self):
        self.conn = None
    
    def _get_connection(self):
        """获取数据库连接"""
        if not self.conn:
            self.conn = get_db_connection()
        return self.conn
    
    def _close_connection(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def get_sales_stats(self, sku: str, months: int = 12) -> Dict[str, float]:
        """
        从crmapp_sales_history统计销量数据
        
        Args:
            sku: SKU编码
            months: 统计月份数（默认12个月）
            
        Returns:
            dict: 包含日均需求、峰值、标准差等统计信息
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # 计算起始日期
                end_date = datetime.now()
                start_date = end_date - timedelta(days=months * 30)
                
                # 查询每日销量
                sql = """
                    SELECT 
                        DATE(sale_date) as sale_day,
                        SUM(quantity) as daily_qty
                    FROM crmapp_sales_history
                    WHERE sku = %s 
                      AND sale_date BETWEEN %s AND %s
                    GROUP BY DATE(sale_date)
                    ORDER BY sale_day
                """
                cursor.execute(sql, (sku, start_date, end_date))
                results = cursor.fetchall()
                
                if not results:
                    return {'demand_avg': 0, 'demand_max': 0, 'demand_std': 0, 'total_days': 0}
                
                # 提取每日销量
                daily_quantities = [row[1] for row in results]
                
                # 计算统计值
                demand_avg = sum(daily_quantities) / len(daily_quantities)
                demand_max = max(daily_quantities)
                
                # 计算标准差（至少2个数据点）
                if len(daily_quantities) > 1:
                    demand_std = statistics.stdev(daily_quantities)
                else:
                    demand_std = 0
                
                return {
                    'demand_avg': round(demand_avg, 2),
                    'demand_max': round(demand_max, 2),
                    'demand_std': round(demand_std, 2),
                    'total_days': len(daily_quantities),
                    'total_qty': sum(daily_quantities)
                }
        finally:
            self._close_connection()
    
    def get_purchase_stats(self, sku: str, months: int = 12) -> Dict[str, float]:
        """
        从crmapp_purchase_history统计补货周期
        
        Args:
            sku: SKU编码
            months: 统计月份数
            
        Returns:
            dict: 包含平均交货期、最长交货期等
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=months * 30)
                
                # 查询采购记录及交货期
                sql = """
                    SELECT 
                        order_date,
                        receive_date,
                        DATEDIFF(receive_date, order_date) as lead_time
                    FROM crmapp_purchase_history
                    WHERE sku = %s 
                      AND order_date BETWEEN %s AND %s
                      AND receive_date IS NOT NULL
                      AND receive_date > order_date
                """
                cursor.execute(sql, (sku, start_date, end_date))
                results = cursor.fetchall()
                
                if not results:
                    # 没有采购记录，使用默认值
                    return {'lead_time_avg': 7, 'lead_time_max': 14, 'count': 0}
                
                # 提取交货期
                lead_times = [row[2] for row in results]
                
                # 计算统计值
                lead_time_avg = sum(lead_times) / len(lead_times)
                lead_time_max = max(lead_times)
                
                # 使用95分位数作为最长交货期（排除极端异常）
                lead_times_sorted = sorted(lead_times)
                p95_index = int(len(lead_times_sorted) * 0.95)
                lead_time_p95 = lead_times_sorted[min(p95_index, len(lead_times_sorted) - 1)]
                
                return {
                    'lead_time_avg': round(lead_time_avg, 1),
                    'lead_time_max': round(lead_time_p95, 1),
                    'count': len(lead_times)
                }
        finally:
            self._close_connection()
    
    def get_inquiry_stats(self, sku: str) -> Dict[str, int]:
        """
        从crmapp_quote_count统计询价数据
        
        Args:
            sku: SKU编码
            
        Returns:
            dict: 包含近1个月、近3个月询价量
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # 近1个月
                sql_1m = """
                    SELECT COUNT(*) 
                    FROM crmapp_quote_count
                    WHERE sku = %s 
                      AND inquiry_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
                """
                cursor.execute(sql_1m, (sku,))
                inquiry_1m = cursor.fetchone()[0] or 0
                
                # 近3个月（目前可能数据不足，预留）
                sql_3m = """
                    SELECT COUNT(*) 
                    FROM crmapp_quote_count
                    WHERE sku = %s 
                      AND inquiry_date >= DATE_SUB(NOW(), INTERVAL 3 MONTH)
                """
                cursor.execute(sql_3m, (sku,))
                inquiry_3m = cursor.fetchone()[0] or 0
                
                return {
                    'inquiry_1m': inquiry_1m,
                    'inquiry_3m': inquiry_3m
                }
        finally:
            self._close_connection()
    
    def get_current_stock(self, sku: str) -> float:
        """
        从crmapp_beihuo获取当前库存
        
        Args:
            sku: SKU编码
            
        Returns:
            float: 当前库存数量
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 库存数量
                    FROM crmapp_beihuo
                    WHERE oe = %s
                    LIMIT 1
                """
                cursor.execute(sql, (sku,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    return float(result[0])
                return 0
        finally:
            self._close_connection()
    
    def get_sku_name(self, sku: str) -> str:
        """
        从crmapp_beihuo获取产品名称
        
        Args:
            sku: SKU编码
            
        Returns:
            str: 产品名称
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 物料名称
                    FROM crmapp_beihuo
                    WHERE oe = %s
                    LIMIT 1
                """
                cursor.execute(sql, (sku,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    return result[0]
                return ''
        finally:
            self._close_connection()
    
    def get_pilot_skus(self, limit: int = 10) -> List[Dict]:
        """
        自动筛选试点SKU
        
        筛选条件：
        1. 有库存
        2. 近12个月有销量
        3. 按销量排序取前limit个
        
        Args:
            limit: 数量限制
            
        Returns:
            list: SKU列表
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # 从crmapp_beihuo筛选有库存且有销量的SKU
                sql = """
                    SELECT 
                        oe as sku,
                        物料名称 as sku_name,
                        库存数量 as stock,
                        近12个月月均销量 as avg_sales
                    FROM crmapp_beihuo
                    WHERE 库存数量 > 0
                      AND 近12个月月均销量 > 0
                    ORDER BY 近12个月月均销量 DESC
                    LIMIT %s
                """
                cursor.execute(sql, (limit,))
                results = cursor.fetchall()
                
                return [
                    {
                        'sku': row[0],
                        'sku_name': row[1],
                        'current_stock': float(row[2]) if row[2] else 0,
                        'avg_sales': float(row[3]) if row[3] else 0
                    }
                    for row in results
                ]
        finally:
            self._close_connection()
    
    def get_all_active_skus(self, offset: int = 0, limit: int = 100) -> List[Dict]:
        """
        获取所有活跃SKU（分页）
        
        Args:
            offset: 偏移量
            limit: 数量限制
            
        Returns:
            list: SKU列表
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        oe as sku,
                        物料名称 as sku_name,
                        库存数量 as stock
                    FROM crmapp_beihuo
                    WHERE 库存数量 > 0
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (limit, offset))
                results = cursor.fetchall()
                
                return [
                    {
                        'sku': row[0],
                        'sku_name': row[1],
                        'current_stock': float(row[2]) if row[2] else 0
                    }
                    for row in results
                ]
        finally:
            self._close_connection()
    
    def aggregate_sku_data(self, sku: str) -> Dict:
        """
        聚合单个SKU的所有数据
        
        Args:
            sku: SKU编码
            
        Returns:
            dict: 包含所有计算所需数据的字典
        """
        # 并行获取各类数据
        sales_stats = self.get_sales_stats(sku)
        purchase_stats = self.get_purchase_stats(sku)
        inquiry_stats = self.get_inquiry_stats(sku)
        current_stock = self.get_current_stock(sku)
        sku_name = self.get_sku_name(sku)
        
        return {
            'sku': sku,
            'sku_name': sku_name,
            'sales': sales_stats,
            'purchase': purchase_stats,
            'inquiry': inquiry_stats,
            'current_stock': current_stock
        }
