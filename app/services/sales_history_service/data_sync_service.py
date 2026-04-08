"""
CRM销量明细数据同步服务（简化版）
用于从CRM系统爬取销量数据并保存到本地数据库
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

from app.utils.session_manager import SessionManager
from app.utils.database_connection import get_db_connection, db_cursor


class SalesHistorySyncService:
    """
    CRM销量明细同步服务（简化版）

    功能：
    1. 从CRM API爬取销量明细数据
    2. 保存明细到 crmapp_sales_history_detail 表
    """

    API_URL = "https://crm.gzbbr.com/api/Crm.Orders/salesOrderHistory"
    LIMIT = 500
    COMPANY = 'fsbbr'
    MAX_RETRY = 3
    RETRY_DELAY = 2

    def __init__(self):
        self.session = SessionManager.get_session()
        self.total_synced = 0
        self.total_failed = 0

    def _get_date_range(self, days: int = 5) -> Tuple[int, int]:
        """
        获取日期范围的时间戳（毫秒）

        Args:
            days: 取多少天的数据（默认5天）

        Returns:
            (start_timestamp, end_timestamp) 单位毫秒
        """
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
        start_date = (end_date - timedelta(days=days-1)).replace(hour=0, minute=0, second=0)
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

    def sync_recent_days(self, days: int = 5) -> Dict[str, Any]:
        """
        同步近N天的销量明细数据

        Args:
            days: 同步天数（默认5天）

        Returns:
            dict: 同步结果统计
        """
        print(f"\n{'='*60}")
        print(f"开始同步近{days}天销量明细数据")
        print(f"{'='*60}")

        start_ts, end_ts = self._get_date_range(days)
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
        print(f"{'='*60}\n")

        return {
            'total_pages': last_page,
            'total_items': total_items,
            'saved': total_saved
        }
