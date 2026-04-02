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
    2. 保存明细到 crmapp_sales_history_detail 表
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
    
    def _get_date_range_by_offset(self, offset_days: int = 0, days: int = 5) -> Tuple[int, int]:
        """
        获取日期范围的时间戳（毫秒）
        改为当天往前推（不再是昨天）
        
        Args:
            offset_days: 偏移天数（默认0）
            days: 取多少天的数据（默认5天）
            
        Returns:
            (start_timestamp, end_timestamp) 单位毫秒
        """
        # 结束时间：今天 23:59:59
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
        
        # 开始时间：往前推 days-1 天，00:00:00
        start_date = (end_date - timedelta(days=days-1)).replace(hour=0, minute=0, second=0)
        
        # 转换为毫秒时间戳
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        return start_ts, end_ts
    
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
    
    def _save_daily_sales(self, items: List[Dict]) -> int:
        """
        保存销量明细数据到 crmapp_sales_history_detail
        唯一键：ddno + frey_no + company，冲突时覆盖更新
        """
        if not items:
            return 0

        with db_cursor() as cursor:
            sql = """
                INSERT INTO crmapp_sales_history_detail
                (ddno, create_date, fullname, pdname, brand_name, l_model_zh,
                 frey_no, number, quantity, sfqty, price, total_price, sfje,
                 remark, warehouse, return_policy, company)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                create_date=VALUES(create_date),
                fullname=VALUES(fullname),
                pdname=VALUES(pdname),
                brand_name=VALUES(brand_name),
                l_model_zh=VALUES(l_model_zh),
                number=VALUES(number),
                quantity=VALUES(quantity),
                sfqty=VALUES(sfqty),
                price=VALUES(price),
                total_price=VALUES(total_price),
                sfje=VALUES(sfje),
                remark=VALUES(remark),
                warehouse=VALUES(warehouse),
                return_policy=VALUES(return_policy),
                updated_time=NOW()
            """

            values = []
            for item in items:
                # 秒级时间戳转datetime
                ts = item.get('create_date', 0)
                if ts > 1000000000000:
                    ts = ts // 1000
                create_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

                values.append((
                    item.get('ddno', ''),
                    create_date,
                    item.get('fullname', ''),
                    item.get('pdname', ''),
                    item.get('brand_name', ''),
                    item.get('l_model_zh', ''),
                    item.get('frey_no', ''),
                    item.get('number', '').strip().upper(),
                    int(item.get('quantity', 0) or 0),
                    int(item.get('sfqty', 0) or 0),
                    float(item.get('price', 0) or 0),
                    float(item.get('total_price', 0) or 0),
                    float(item.get('sfje', 0) or 0),
                    item.get('remark') or '',
                    item.get('warehouse', ''),
                    item.get('return_policy') or '',
                    self.COMPANY
                ))

            cursor.executemany(sql, values)
            return len(values)
    
    def sync_by_offset(self, offset_days: int = 0, days: int = 5) -> Dict[str, int]:
        """
        同步销量明细数据
        直接保存明细到 crmapp_sales_history_detail，不再按天汇总
        """
        start_ts, end_ts = self._get_date_range_by_offset(offset_days, days)

        start_date_str = datetime.fromtimestamp(start_ts / 1000).strftime('%Y-%m-%d')
        end_date_str = datetime.fromtimestamp(end_ts / 1000).strftime('%Y-%m-%d')

        print(f"\n[同步] 日期范围: {start_date_str} 至 {end_date_str} ({days}天)")

        # 获取第1页，确定总页数
        items, last_page = self._fetch_page(1, start_ts, end_ts)
        if not items:
            print(f"[同步] 未获取到数据")
            return {'total_pages': 0, 'total_items': 0, 'saved': 0}

        print(f"[同步] 总页数: {last_page}")

        # 保存第1页
        total_saved = self._save_daily_sales(items)
        total_items = len(items)
        print(f"[保存] 第1页: {total_saved} 条")

        # 获取剩余页面并保存
        for page in range(2, last_page + 1):
            items, _ = self._fetch_page(page, start_ts, end_ts)
            if items:
                saved = self._save_daily_sales(items)
                total_items += len(items)
                print(f"[保存] 第{page}/{last_page}页: {saved} 条")

            # 每10页暂停
            if page % 10 == 0:
                time.sleep(2)

        print(f"[同步完成] 共{last_page}页, {total_items}条, 保存{total_saved}条")

        return {
            'total_pages': last_page,
            'total_items': total_items,
            'saved': total_saved
        }
    
    def sync_recent_days(self, days: int = 5) -> Dict[str, Any]:
        """
        同步近N天的销量明细数据
        一次性处理，不再分批
        """
        print(f"\n{'='*60}")
        print(f"开始同步近{days}天销量明细数据")
        print(f"{'='*60}")

        # 一次性同步近5天
        result = self.sync_by_offset(offset_days=0, days=days)

        # 更新汇总表
        self.update_summary_table()

        print(f"\n{'='*60}")
        print(f"全部同步完成!")
        print(f"页数: {result['total_pages']}, 条目: {result['total_items']}, 保存: {result['saved']}")
        print(f"{'='*60}\n")

        return result
    
    def update_summary_table(self) -> int:
        """更新 crmapp_compare_summary 表的销量字段（从明细表统计）"""
        print("[更新] 开始从明细表统计销量数据...")

        with db_cursor() as cursor:
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            day_before_yesterday = today - timedelta(days=2)

            # 1. 更新 yesterday_sales（前天）
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT number as oe, brand_name as brand, SUM(quantity) as qty
                    FROM crmapp_sales_history_detail
                    WHERE DATE(create_date) = %s AND company = %s
                    GROUP BY number, brand_name
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.yesterday_sales = COALESCE(h.qty, 0)
            """, (day_before_yesterday, self.COMPANY))

            # 2. 更新 today_sales（昨天）
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT number as oe, brand_name as brand, SUM(quantity) as qty
                    FROM crmapp_sales_history_detail
                    WHERE DATE(create_date) = %s AND company = %s
                    GROUP BY number, brand_name
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.today_sales = COALESCE(h.qty, 0)
            """, (yesterday, self.COMPANY))

            # 3. 更新 sales_7d（近7天）
            seven_days_ago = yesterday - timedelta(days=6)
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT number as oe, brand_name as brand, SUM(quantity) as qty
                    FROM crmapp_sales_history_detail
                    WHERE DATE(create_date) BETWEEN %s AND %s AND company = %s
                    GROUP BY number, brand_name
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.sales_7d = COALESCE(h.qty, 0)
            """, (seven_days_ago, yesterday, self.COMPANY))

            # 4. 更新 month_sales（近30天）
            thirty_days_ago = yesterday - timedelta(days=29)
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT number as oe, brand_name as brand, SUM(quantity) as qty
                    FROM crmapp_sales_history_detail
                    WHERE DATE(create_date) BETWEEN %s AND %s AND company = %s
                    GROUP BY number, brand_name
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.month_sales = COALESCE(h.qty, 0)
            """, (thirty_days_ago, yesterday, self.COMPANY))

            # 5. 更新 avg_sales_6m（近6个月月均）
            six_months_ago = yesterday - timedelta(days=180)
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT number as oe, brand_name as brand, ROUND(SUM(quantity) / 6) as avg_qty
                    FROM crmapp_sales_history_detail
                    WHERE DATE(create_date) BETWEEN %s AND %s AND company = %s
                    GROUP BY number, brand_name
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.avg_sales_6m = COALESCE(h.avg_qty, 0)
            """, (six_months_ago, yesterday, self.COMPANY))

            # 6. 更新 avg_sales_12m（近12个月月均）
            twelve_months_ago = yesterday - timedelta(days=365)
            cursor.execute("""
                UPDATE crmapp_compare_summary s
                LEFT JOIN (
                    SELECT number as oe, brand_name as brand, ROUND(SUM(quantity) / 12) as avg_qty
                    FROM crmapp_sales_history_detail
                    WHERE DATE(create_date) BETWEEN %s AND %s AND company = %s
                    GROUP BY number, brand_name
                ) h ON s.oe = h.oe AND s.brand = h.brand
                SET s.avg_sales_12m = COALESCE(h.avg_qty, 0)
            """, (twelve_months_ago, yesterday, self.COMPANY))

            print(f"[更新] 汇总表销量数据更新完成")
            return cursor.rowcount
