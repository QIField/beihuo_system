"""
采购历史记录爬取服务
用于从CRM采购历史接口爬取数据并保存到数据库
"""

import time
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
    """采购历史记录爬取服务类
    
    用于爬取近N天的采购历史数据，保存到 crmapp_procurement_history_detail 表
    """

    def __init__(self):
        self.session = None

    def crawl_recent_days(self, days: int = 5) -> Dict[str, Any]:
        """
        爬取近N天的采购历史数据

        Args:
            days: 天数，默认5天

        Returns:
            {
                'date_range': '2026-03-23 ~ 2026-03-28',
                'total_processed': 总处理数,
                'saved': 成功保存数,
                'failed': 失败数
            }
        """
        now = datetime.now()
        start_date = now - timedelta(days=days)

        # 计算时间戳范围（毫秒级）
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(now.timestamp() * 1000)

        date_range_str = f"{start_date.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
        print(f"\n{'='*60}")
        print(f"开始爬取近 {days} 天的采购历史数据")
        print(f"时间范围: {date_range_str}")
        print(f"时间戳范围: {start_ts} ~ {end_ts}")
        print(f"{'='*60}")

        result = {
            'date_range': date_range_str,
            'total_processed': 0,
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
                    print(f"近 {days} 天无数据")
                break

            # 解析并保存记录
            parsed_records = []
            for record in records:
                try:
                    parsed = self._parse_record_detail(record)
                    if parsed:
                        parsed_records.append(parsed)
                except Exception as e:
                    print(f"解析记录失败: {e}")
                    result['failed'] += 1

            # 批量保存到新表
            if parsed_records:
                saved_count = self._save_records_detail(parsed_records)
                result['saved'] += saved_count
                result['total_processed'] += len(parsed_records)
                print(f"本页解析: {len(parsed_records)} 条, 保存: {saved_count} 条")

            # 检查是否还有更多页
            if not has_more:
                break

            page += 1
            time.sleep(0.5)

        print(f"\n{'='*60}")
        print(f"近 {days} 天采购历史爬取完成!")
        print(f"时间范围: {date_range_str}")
        print(f"总处理数: {result['total_processed']}")
        print(f"保存记录: {result['saved']}")
        print(f"失败数: {result['failed']}")
        print(f"{'='*60}")

        return result

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

    def _parse_record_detail(self, record: Dict) -> Dict[str, Any]:
        """
        解析单条记录的详细信息（包含更多字段）

        Args:
            record: CRM返回的原始记录

        Returns:
            解析后的详细记录字典
        """
        # 提取create_date并转换为datetime
        create_date_ts = record.get('create_date', '0')
        if create_date_ts:
            create_date = datetime.fromtimestamp(int(create_date_ts))
        else:
            create_date = datetime.now()

        # 提取expected_delivery_date并转换为datetime
        expected_delivery_ts = record.get('expected_delivery_date', '0')
        if expected_delivery_ts:
            expected_delivery_date = datetime.fromtimestamp(int(expected_delivery_ts))
        else:
            expected_delivery_date = None

        # 计算year_month字段
        year_month = create_date.strftime('%Y-%m')

        return {
            'order_no': record.get('order_no', '').strip(),
            'fullname': record.get('fullname', '').strip(),
            'l_name_zh_default': record.get('l_name_zh_default', '').strip(),
            'frey_no': record.get('frey_no', '').strip(),
            'number': record.get('number', '').strip(),
            'brand': record.get('brand', '').strip(),
            'l_model_zh': record.get('l_model_zh', '').strip(),
            'purchase_quantity': int(record.get('purchase_quantity', 0)) if record.get('purchase_quantity') else 0,
            'unit_cost': float(record.get('unit_cost', 0)) if record.get('unit_cost') else 0.0,
            'create_date': create_date,
            'expected_delivery_date': expected_delivery_date,
            'year_month': year_month,
            'company': COMPANY
        }

    def _save_records_detail(self, records: List[Dict]) -> int:
        """
        批量保存详细记录到新表 crmapp_procurement_history_detail
        使用 INSERT ... ON DUPLICATE KEY UPDATE 实现去重（以新的为准覆盖）
        唯一键: (order_no, number, brand, company)

        Args:
            records: 详细记录列表

        Returns:
            成功保存的记录数
        """
        if not records:
            return 0

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO crmapp_procurement_history_detail
                    (order_no, fullname, l_name_zh_default, frey_no, number, brand,
                     l_model_zh, purchase_quantity, unit_cost, create_date,
                     expected_delivery_date, `year_month`, company)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        fullname = VALUES(fullname),
                        l_name_zh_default = VALUES(l_name_zh_default),
                        frey_no = VALUES(frey_no),
                        l_model_zh = VALUES(l_model_zh),
                        purchase_quantity = VALUES(purchase_quantity),
                        unit_cost = VALUES(unit_cost),
                        create_date = VALUES(create_date),
                        expected_delivery_date = VALUES(expected_delivery_date),
                        `year_month` = VALUES(`year_month`)
                """

                values = []
                for record in records:
                    values.append((
                        record['order_no'],
                        record['fullname'],
                        record['l_name_zh_default'],
                        record['frey_no'],
                        record['number'],
                        record['brand'],
                        record['l_model_zh'],
                        record['purchase_quantity'],
                        record['unit_cost'],
                        record['create_date'],
                        record['expected_delivery_date'],
                        record['year_month'],
                        record['company']
                    ))

                cursor.executemany(sql, values)
                conn.commit()

                return len(records)

        except Exception as e:
            conn.rollback()
            print(f"批量保存详细记录失败: {e}")
            return 0
        finally:
            conn.close()
