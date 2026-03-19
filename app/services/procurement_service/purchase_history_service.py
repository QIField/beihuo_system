"""
采购历史记录爬取服务
用于从CRM采购历史接口爬取数据并保存到数据库
"""

import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

from app.utils.session_manager import SessionManager
from app.utils.database_connection import get_db_connection


# 配置参数
LIMIT = 500
MAX_RETRY = 3
RETRY_DELAY = 2
COMPANY = 'fsbbr'
CRM_PURCHASE_HISTORY_URL = 'https://crm.gzbbr.com/api/Crm.PurchaseOrder/PurchaseHistory'


class PurchaseHistoryService:
    """采购历史记录爬取服务类"""

    def __init__(self):
        self.session = None
        self.total_saved = 0
        self.total_processed = 0

    def crawl_last_and_current_month(self) -> Dict[str, Any]:
        """
        爬取上个月和本月的数据
        主入口方法，每日定时任务调用

        Returns:
            {
                'months': ['2026-02', '2026-03'],
                'total_processed': 总处理数,
                'saved': 成功保存数,
                'failed': 失败数
            }
        """
        now = datetime.now()
        current_year = now.year
        current_month = now.month

        # 计算上个月
        if current_month == 1:
            last_year = current_year - 1
            last_month = 12
        else:
            last_year = current_year
            last_month = current_month - 1

        all_results = {
            'months': [],
            'total_processed': 0,
            'saved': 0,
            'failed': 0
        }

        # 先处理上个月，再处理当月
        months_to_crawl = [
            (last_year, last_month),
            (current_year, current_month)
        ]

        for year, month in months_to_crawl:
            month_str = f"{year}-{month:02d}"
            print(f"\n{'='*60}")
            print(f"开始爬取 {month_str} 的采购历史数据")
            print(f"{'='*60}")

            result = self.crawl_month(year, month)

            all_results['months'].append(month_str)
            all_results['total_processed'] += result['processed']
            all_results['saved'] += result['saved']
            all_results['failed'] += result['failed']

            # 月份之间暂停一下
            time.sleep(2)

        print(f"\n{'='*60}")
        print(f"采购历史爬取完成!")
        print(f"处理月份: {', '.join(all_results['months'])}")
        print(f"总处理数: {all_results['total_processed']}")
        print(f"保存记录: {all_results['saved']}")
        print(f"失败数: {all_results['failed']}")
        print(f"{'='*60}")

        return all_results

    def crawl_month(self, year: int, month: int) -> Dict[str, int]:
        """
        爬取指定月份的所有数据

        Args:
            year: 年份
            month: 月份

        Returns:
            {'processed': 处理数, 'saved': 保存数, 'failed': 失败数}
        """
        # 计算时间戳范围
        start_ts, end_ts = self._get_month_timestamp(year, month)
        year_month = f"{year}-{month:02d}"

        print(f"时间范围: {start_ts} ~ {end_ts}")

        result = {
            'processed': 0,
            'saved': 0,
            'failed': 0
        }

        page = 1
        while True:
            print(f"\n正在获取第 {page} 页数据...")

            # 获取页面数据
            records, has_more = self._fetch_page(page, start_ts, end_ts)

            if not records:
                if page == 1:
                    print(f"{year_month} 无数据")
                break

            # 解析并保存记录
            parsed_records = []
            for record in records:
                try:
                    parsed = self._parse_record(record)
                    if parsed:
                        parsed_records.append(parsed)
                except Exception as e:
                    print(f"解析记录失败: {e}")
                    result['failed'] += 1

            # 批量保存
            if parsed_records:
                saved_count = self._save_records(parsed_records, year_month)
                result['saved'] += saved_count
                result['processed'] += len(parsed_records)
                print(f"本页解析: {len(parsed_records)} 条, 保存: {saved_count} 条")

            # 检查是否还有更多页
            if not has_more:
                break

            page += 1
            time.sleep(0.5)

        return result

    def _get_month_timestamp(self, year: int, month: int) -> Tuple[int, int]:
        """
        获取指定月份的开始和结束时间戳（毫秒级）

        Args:
            year: 年份
            month: 月份

        Returns:
            (开始时间戳, 结束时间戳)
        """
        # 月份开始时间
        start_date = datetime(year, month, 1)
        start_ts = int(start_date.timestamp() * 1000)

        # 月份结束时间
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
        end_ts = int(end_date.timestamp() * 1000)

        return start_ts, end_ts

    def _fetch_page(self, page: int, start_ts: int, end_ts: int) -> Tuple[List[Dict], bool]:
        """
        调用CRM接口获取单页数据

        Args:
            page: 页码
            start_ts: 开始时间戳
            end_ts: 结束时间戳

        Returns:
            (记录列表, 是否还有更多页)
        """
        session = SessionManager.get_session()

        payload = {
            "limit": LIMIT,
            "orderdate": [start_ts, end_ts],
            "page": page
        }

        for attempt in range(MAX_RETRY):
            try:
                response = session.post(
                    CRM_PURCHASE_HISTORY_URL,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()

                if result.get('status') == 200 or result.get('msg') == '操作成功':
                    data = result.get('data', {})
                    list_data = data.get('list', {})
                    records = list_data.get('data', [])

                    # 判断是否还有更多页
                    current_page = int(list_data.get('current_page', page))
                    last_page = int(list_data.get('last_page', page))
                    has_more = current_page < last_page

                    return records, has_more
                else:
                    print(f"API返回错误: {result.get('msg')}")

            except Exception as e:
                print(f"[{attempt + 1}/{MAX_RETRY}] 请求失败: {e}")
                if attempt < MAX_RETRY - 1:
                    time.sleep(RETRY_DELAY)
                    continue

        return [], False

    def _parse_record(self, record: Dict) -> Dict[str, Any]:
        """
        解析单条记录

        Args:
            record: CRM返回的原始记录

        Returns:
            解析后的记录字典
        """
        # 提取create_date并转换为日期
        create_date_ts = record.get('create_date', '0')
        if create_date_ts:
            # Unix秒级时间戳转日期
            purchase_date = datetime.fromtimestamp(int(create_date_ts)).strftime('%Y-%m-%d')
        else:
            purchase_date = datetime.now().strftime('%Y-%m-%d')

        return {
            'purchase_date': purchase_date,
            'supplier_name': record.get('fullname', '').strip(),
            'oe': record.get('number', '').strip(),
            'brand': record.get('brand', '').strip(),
            'unit_price': float(record.get('unit_cost', 0)) if record.get('unit_cost') else 0.0
        }

    def _save_records(self, records: List[Dict], year_month: str) -> int:
        """
        批量保存记录到数据库
        使用 INSERT ... ON DUPLICATE KEY UPDATE 实现去重

        Args:
            records: 记录列表
            year_month: 年月字符串 (YYYY-MM)

        Returns:
            成功保存的记录数
        """
        if not records:
            return 0

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO crmapp_procurement_history 
                    (year_month, purchase_date, supplier_name, oe, brand, unit_price, company)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        purchase_date = VALUES(purchase_date)
                """

                values = []
                for record in records:
                    values.append((
                        year_month,
                        record['purchase_date'],
                        record['supplier_name'],
                        record['oe'],
                        record['brand'],
                        record['unit_price'],
                        COMPANY
                    ))

                cursor.executemany(sql, values)
                conn.commit()

                return len(records)

        except Exception as e:
            conn.rollback()
            print(f"批量保存失败: {e}")
            return 0
        finally:
            conn.close()
