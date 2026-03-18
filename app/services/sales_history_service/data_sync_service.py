"""
CRM销量明细数据同步服务
用于从CRM系统爬取销量数据并保存到本地数据库

处理逻辑：
    - 按天批次处理数据
    - 每批独立爬取、汇总、保存
    - 保存时如有重复直接覆盖
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from collections import defaultdict

from app.utils.session_manager import SessionManager
from app.utils.database_connection import get_db_connection, db_cursor


class SalesHistorySyncService:
    """
    CRM销量明细同步服务
    
    功能：
    1. 从CRM API爬取销量明细数据
    2. 按天汇总存储到 crmapp_sales_history 表
    3. 更新 crmapp_compare_summary 表的销量统计字段
    """
    
    API_URL = "https://crm.gzbbr.com/api/Crm.Orders/salesOrderHistory"
    LIMIT = 500
    COMPANY = 'fsbbr'  # 默认公司
    MAX_RETRY = 3
    RETRY_DELAY = 2
    
    def __init__(self):
        self.session = SessionManager.get_session()
        self.total_synced = 0
        self.total_failed = 0
    
    def _get_date_range_by_offset(self, offset_days: int, days: int) -> Tuple[int, int]:
        """
        根据偏移量获取日期范围的时间戳（毫秒）
        
        Args:
            offset_days: 从昨天往前偏移多少天开始（0表示从昨天开始）
            days: 取多少天的数据
            
        Returns:
            (start_timestamp, end_timestamp) 单位毫秒
        """
        # 基准时间：昨天 23:59:59
        base_end = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
        
        # 结束时间：基准时间往前推 offset_days
        end_date = base_end - timedelta(days=offset_days)
        # 开始时间：结束时间往前推 days-1 天，回到当天的 00:00:00
        start_date = end_date.replace(hour=0, minute=0, second=0) - timedelta(days=days-1)
        
        # 转换为毫秒时间戳
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        return start_ts, end_ts
    
    def _timestamp_to_date(self, ts: int) -> str:
        """时间戳转日期字符串 YYYY-MM-DD"""
        if ts > 1000000000000:  # 毫秒时间戳
            ts = ts // 1000
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
    
    def cleanup_old_data(self, keep_days: int = 365) -> int:
        """清理N天前的历史数据"""
        cutoff_date = (datetime.now() - timedelta(days=keep_days)).strftime('%Y-%m-%d')
        
        with db_cursor() as cursor:
            sql = "DELETE FROM crmapp_sales_history WHERE sales_date < %s"
            cursor.execute(sql, (cutoff_date,))
            deleted = cursor.rowcount
            print(f"[清理] 已删除 {deleted} 条 {keep_days} 天前的历史数据")
            return deleted
    
    def _fetch_page(self, page: int, start_ts: int, end_ts: int) -> Tuple[List[Dict], int]:
        """获取指定页的数据"""
        params = [
            ('page', page),
            ('limit', self.LIMIT),
            ('create_date[]', start_ts),
            ('create_date[]', end_ts),
        ]
        
        for attempt in range(self.MAX_RETRY):
            try:
                response = self.session.get(self.API_URL, params=params, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                if result.get('status') == 200 or result.get('msg') == '操作成功':
                    data = result.get('data', {})
                    items = data.get('data', [])
                    last_page = data.get('last_page', 1)
                    return items, last_page
                else:
                    print(f"[第{page}页] API返回错误: {result.get('msg')}")
                    
            except Exception as e:
                print(f"[第{page}页][{attempt+1}/{self.MAX_RETRY}] 请求失败: {e}")
                if attempt < self.MAX_RETRY - 1:
                    time.sleep(self.RETRY_DELAY)
                    self.session = SessionManager.get_session()
                    continue
                    
        return [], 1
    
    def _save_daily_sales(self, date_str: str, sales_data: Dict[Tuple[str, str], int]) -> int:
        """
        保存单天的销量数据到数据库（覆盖模式）
        
        先删除该日期已有数据，再插入新数据，确保数据准确
        """
        if not sales_data:
            return 0
        
        with db_cursor() as cursor:
            # 1. 先删除该日期、该公司的已有数据
            cursor.execute("""
                DELETE FROM crmapp_sales_history 
                WHERE sales_date = %s AND company = %s
            """, (date_str, self.COMPANY))
            
            # 2. 插入新数据
            sql = """
                INSERT INTO crmapp_sales_history 
                (oe, brand, company, quantity, sales_date)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            values = [
                (oe, brand, self.COMPANY, qty, date_str)
                for (oe, brand), qty in sales_data.items()
            ]
            
            cursor.executemany(sql, values)
            return len(values)
    
    def sync_by_offset(self, offset_days: int = 0, days: int = 5) -> Dict[str, int]:
        """
        按偏移量同步指定天数的销量数据
        
        Args:
            offset_days: 从昨天往前偏移多少天开始（0表示从昨天开始）
            days: 同步多少天的数据
            
        Returns:
            {'total_pages': 总页数, 'total_items': 总条目, 'saved': 保存记录数}
        """
        start_ts, end_ts = self._get_date_range_by_offset(offset_days, days)
        start_date = self._timestamp_to_date(start_ts)
        end_date = self._timestamp_to_date(end_ts)
        
        print(f"\n[同步] 日期范围: {start_date} 至 {end_date} ({days}天)")
        
        # 获取第1页，确定总页数
        items, last_page = self._fetch_page(1, start_ts, end_ts)
        if not items:
            print(f"[同步] 未获取到数据")
            return {'total_pages': 0, 'total_items': 0, 'saved': 0}
        
        print(f"[同步] 总页数: {last_page}")
        
        # 按日期汇总数据
        sales_by_date = defaultdict(lambda: defaultdict(int))
        
        # 处理第1页
        for item in items:
            oe = item.get('number', '').strip().upper()
            brand = item.get('brand_name', '').strip()
            quantity = int(item.get('quantity', 0))
            date_str = self._timestamp_to_date(item.get('create_date', 0))
            
            if oe and brand:
                sales_by_date[date_str][(oe, brand)] += quantity
        
        # 获取剩余页面
        for page in range(2, last_page + 1):
            items, _ = self._fetch_page(page, start_ts, end_ts)
            if not items:
                continue
                
            for item in items:
                oe = item.get('number', '').strip().upper()
                brand = item.get('brand_name', '').strip()
                quantity = int(item.get('quantity', 0))
                date_str = self._timestamp_to_date(item.get('create_date', 0))
                
                if oe and brand:
                    sales_by_date[date_str][(oe, brand)] += quantity
        
        # 按日期保存数据（先删后插，覆盖模式）
        total_saved = 0
        for date_str in sorted(sales_by_date.keys()):
            daily_data = sales_by_date[date_str]
            saved = self._save_daily_sales(date_str, daily_data)
            total_saved += saved
            print(f"[保存] {date_str}: {saved} 条记录")
        
        total_items = sum(len(v) for v in sales_by_date.values())
        print(f"[同步完成] 共{last_page}页, {total_items}条汇总记录")
        
        return {
            'total_pages': last_page,
            'total_items': total_items,
            'saved': total_saved
        }
    
    def sync_recent_days(self, days: int = 30, batch_days: int = 5) -> Dict[str, Any]:
        """
        同步近N天的销量数据（按天批次处理）
        
        Args:
            days: 同步多少天的数据
            batch_days: 每批处理多少天
            
        Returns:
            同步结果统计
        """
        print(f"\n{'='*60}")
        print(f"开始同步近{days}天销量数据（每{batch_days}天一批）")
        print(f"{'='*60}")
        
        all_results = {
            'total_pages': 0,
            'total_items': 0,
            'total_saved': 0,
            'batches': 0
        }
        
        # 从近到远分批处理
        for offset in range(0, days, batch_days):
            current_batch_days = min(batch_days, days - offset)
            
            result = self.sync_by_offset(
                offset_days=offset,
                days=current_batch_days
            )
            
            all_results['total_pages'] += result['total_pages']
            all_results['total_items'] += result['total_items']
            all_results['total_saved'] += result['saved']
            all_results['batches'] += 1
            
            # 批次间短暂暂停
            if offset + batch_days < days:
                time.sleep(1)
        
        # 更新汇总表
        self.update_summary_table()
        
        print(f"\n{'='*60}")
        print(f"全部同步完成!")
        print(f"批次: {all_results['batches']}, 页数: {all_results['total_pages']}")
        print(f"条目: {all_results['total_items']}, 保存: {all_results['total_saved']}")
        print(f"{'='*60}\n")
        
        return all_results
    
    def update_summary_table(self) -> int:
        """更新 crmapp_compare_summary 表的销量字段"""
        print("[更新] 开始更新汇总表销量数据...")
        
        with db_cursor() as cursor:
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            day_before_yesterday = today - timedelta(days=2)
            
            # 1. 更新 yesterday_sales（前天）
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT oe, brand, SUM(quantity) as qty
                    FROM crmapp_sales_history
                    WHERE sales_date = %s AND company = %s
                    GROUP BY oe, brand
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.yesterday_sales = COALESCE(h.qty, 0)
            """, (day_before_yesterday, self.COMPANY))
            
            # 2. 更新 today_sales（昨天）
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT oe, brand, SUM(quantity) as qty
                    FROM crmapp_sales_history
                    WHERE sales_date = %s AND company = %s
                    GROUP BY oe, brand
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.today_sales = COALESCE(h.qty, 0)
            """, (yesterday, self.COMPANY))
            
            # 3. 更新 sales_7d（近7天）
            seven_days_ago = yesterday - timedelta(days=6)
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT oe, brand, SUM(quantity) as qty
                    FROM crmapp_sales_history
                    WHERE sales_date BETWEEN %s AND %s AND company = %s
                    GROUP BY oe, brand
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.sales_7d = COALESCE(h.qty, 0)
            """, (seven_days_ago, yesterday, self.COMPANY))
            
            # 4. 更新 month_sales（近30天）
            thirty_days_ago = yesterday - timedelta(days=29)
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT oe, brand, SUM(quantity) as qty
                    FROM crmapp_sales_history
                    WHERE sales_date BETWEEN %s AND %s AND company = %s
                    GROUP BY oe, brand
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.month_sales = COALESCE(h.qty, 0)
            """, (thirty_days_ago, yesterday, self.COMPANY))
            
            # 5. 更新 avg_sales_6m（近6个月月均）
            six_months_ago = yesterday - timedelta(days=180)
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT oe, brand, ROUND(SUM(quantity) / 6) as avg_qty
                    FROM crmapp_sales_history
                    WHERE sales_date BETWEEN %s AND %s AND company = %s
                    GROUP BY oe, brand
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.avg_sales_6m = COALESCE(h.avg_qty, 0)
            """, (six_months_ago, yesterday, self.COMPANY))
            
            # 6. 更新 avg_sales_12m（近12个月月均）
            twelve_months_ago = yesterday - timedelta(days=365)
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT oe, brand, ROUND(SUM(quantity) / 12) as avg_qty
                    FROM crmapp_sales_history
                    WHERE sales_date BETWEEN %s AND %s AND company = %s
                    GROUP BY oe, brand
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.avg_sales_12m = COALESCE(h.avg_qty, 0)
            """, (twelve_months_ago, yesterday, self.COMPANY))
            
            print(f"[更新] 汇总表销量数据更新完成")
            return cursor.rowcount
