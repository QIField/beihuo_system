"""
开思询价次数统计服务
用于从开思平台爬取询价数据并按(年月, OE, 品牌)统计询价次数

处理逻辑：
    - 按自然月批次处理数据
    - 先爬取上一个月和当月的数据
    - 每个月独立爬取、汇总、保存（覆盖模式）
    - 支持登录状态失效重试和网络重试机制
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

from app.utils.session_manager import SessionManager
from app.utils.database_connection import db_cursor


class QuoteCountSyncService:
    """
    开思询价次数统计服务

    功能：
    1. 从开思平台爬取询价订单列表
    2. 遍历每个订单获取询价明细（OE号、品牌）
    3. 按(年月, OE, 品牌)统计询价次数
    4. 保存到 crmapp_quote_count_ks 表（覆盖模式）
    """

    # 开思平台API地址
    QUOTATION_LIST_URL = "https://www.cassmall.com/inquiry/seller/quote/list/v1"
    QUOTATION_DETAIL_URL_TEMPLATE = "https://www.cassmall.com/inquiryWeb/quotation/{}/quoting/items"

    # 请求配置
    PAGE_SIZE = 500  # 订单列表分页大小
    DETAIL_PAGE_SIZE = 50  # 订单明细分页大小
    MAX_RETRY = 3  # 最大重试次数
    RETRY_DELAY = 2  # 重试间隔（秒）
    COMPANY = 'fsbbr'  # 默认公司

    def __init__(self):
        self.session = SessionManager.get_session()
        self.total_orders = 0  # 总订单数
        self.total_items = 0   # 总明细条目数
        self.failed_orders = 0  # 失败订单数

    def _get_month_range(self, year: int, month: int) -> Tuple[int, int]:
        """
        获取指定月份的起止时间戳（毫秒）

        Args:
            year: 年份
            month: 月份

        Returns:
            (start_timestamp, end_timestamp) 单位毫秒
        """
        # 当月第一天 00:00:00
        start_date = datetime(year, month, 1, 0, 0, 0)

        # 下个月第一天 00:00:00，再减1秒得到当月最后一天 23:59:59
        if month == 12:
            next_month = datetime(year + 1, 1, 1, 0, 0, 0)
        else:
            next_month = datetime(year, month + 1, 1, 0, 0, 0)
        end_date = next_month - timedelta(seconds=1)

        # 转换为毫秒时间戳
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)

        return start_ts, end_ts

    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        """
        带重试机制的HTTP请求

        Args:
            method: 请求方法 ('get' 或 'post')
            url: 请求URL
            **kwargs: 其他请求参数

        Returns:
            响应JSON数据，失败返回None
        """
        for attempt in range(self.MAX_RETRY):
            try:
                if method.lower() == 'get':
                    response = self.session.get(url, timeout=30, **kwargs)
                else:
                    response = self.session.post(url, timeout=30, **kwargs)

                response.raise_for_status()
                result = response.json()

                # 检查是否登录失效
                if result.get('code') == 401 or result.get('msg') == '登录已过期':
                    print(f"[请求] 登录状态失效，尝试刷新session...")
                    # 清除当前session，下次会重新创建
                    self.session = SessionManager.get_session()
                    if attempt < self.MAX_RETRY - 1:
                        time.sleep(self.RETRY_DELAY)
                        continue
                    else:
                        print(f"[请求] 登录失效，重试次数耗尽")
                        return None

                return result

            except Exception as e:
                print(f"[请求][{attempt+1}/{self.MAX_RETRY}] 请求失败: {e}")
                if attempt < self.MAX_RETRY - 1:
                    time.sleep(self.RETRY_DELAY)
                    # 刷新session
                    self.session = SessionManager.get_session()
                    continue
                else:
                    print(f"[请求] 请求失败，重试次数耗尽")
                    return None

        return None

    def _fetch_quotation_list(self, start_ts: int, end_ts: int) -> List[str]:
        """
        获取指定时间范围内的所有订单ID列表

        Args:
            start_ts: 开始时间戳（毫秒）
            end_ts: 结束时间戳（毫秒）

        Returns:
            订单ID列表
        """
        order_ids = []
        page = 1

        while True:
            payload = {
                "endDate": end_ts,
                "pageSize": self.PAGE_SIZE,
                "startDate": start_ts
            }

            result = self._make_request_with_retry(
                'post',
                self.QUOTATION_LIST_URL,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )

            if not result:
                print(f"[订单列表] 第{page}页请求失败，跳过")
                break

            if result.get('code') != 200:
                print(f"[订单列表] API返回错误: {result.get('msg')}")
                break

            data = result.get('data', {})
            quotation_list = data.get('quotationList', [])

            if not quotation_list:
                break

            # 提取订单ID
            for item in quotation_list:
                order_id = item.get('id')
                if order_id:
                    order_ids.append(order_id)

            print(f"[订单列表] 第{page}页获取 {len(quotation_list)} 条订单")

            # 检查是否还有下一页
            total_elements = data.get('totalElements', 0)
            if len(order_ids) >= total_elements or len(quotation_list) < self.PAGE_SIZE:
                break

            page += 1
            # 短暂暂停，避免请求过快
            time.sleep(0.5)

        print(f"[订单列表] 共获取 {len(order_ids)} 个订单ID")
        return order_ids

    def _fetch_quotation_detail(self, order_id: str) -> List[Tuple[str, str]]:
        """
        获取指定订单的询价明细

        Args:
            order_id: 订单ID

        Returns:
            [(partsNum, brandName), ...] 列表
        """
        url = self.QUOTATION_DETAIL_URL_TEMPLATE.format(order_id)
        items = []

        payload = {
            "isViewPage": True,
            "listHistoryQuoteResult": False,
            "onlyUnquote": False,
            "userNeedsItemPositiveOrder": False,
            "page": 1,
            "size": self.DETAIL_PAGE_SIZE
        }

        result = self._make_request_with_retry(
            'post',
            url,
            json=payload,
            headers={'Content-Type': 'application/json'}
        )

        if not result:
            print(f"[订单明细] 订单 {order_id} 请求失败")
            self.failed_orders += 1
            return items

        if result.get('code') != 200:
            print(f"[订单明细] 订单 {order_id} API返回错误: {result.get('msg')}")
            self.failed_orders += 1
            return items

        data = result.get('data', {})
        content_list = data.get('content', [])

        for content in content_list:
            store_quote_item_results = content.get('storeQuoteItemResults', [])

            # 如果为空则跳过
            if not store_quote_item_results:
                continue

            for item in store_quote_item_results:
                parts_num = item.get('partsNum', '').strip().upper()
                brand_name = item.get('brandName', '').strip()

                if parts_num and brand_name:
                    items.append((parts_num, brand_name))

        return items

    def _save_monthly_data(self, year_month: str, quote_data: Dict[Tuple[str, str], int]) -> int:
        """
        保存单月的询价统计数据到数据库（覆盖模式）

        Args:
            year_month: 年月字符串，如 "2025-03"
            quote_data: {(oe, brand): count} 统计字典

        Returns:
            保存的记录数
        """
        if not quote_data:
            print(f"[保存] {year_month}: 无数据需要保存")
            return 0

        with db_cursor() as cursor:
            # 1. 先删除该年月、该公司的已有数据
            cursor.execute("""
                DELETE FROM crmapp_quote_count_ks
                WHERE year_month = %s AND company = %s
            """, (year_month, self.COMPANY))
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"[保存] 已删除 {year_month} 旧数据 {deleted} 条")

            # 2. 插入新数据
            sql = """
                INSERT INTO crmapp_quote_count_ks
                (year_month, oe, brand, quote_count, company, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """

            values = [
                (year_month, oe, brand, count, self.COMPANY)
                for (oe, brand), count in quote_data.items()
            ]

            cursor.executemany(sql, values)
            return len(values)

    def sync_month(self, year: int, month: int) -> Dict[str, Any]:
        """
        同步指定月份的询价数据

        Args:
            year: 年份
            month: 月份

        Returns:
            同步结果统计
        """
        year_month = f"{year}-{month:02d}"
        print(f"\n{'='*60}")
        print(f"[同步] 开始处理 {year_month} 的询价数据")
        print(f"{'='*60}")

        # 1. 获取时间范围
        start_ts, end_ts = self._get_month_range(year, month)
        print(f"[同步] 时间范围: {start_ts} ~ {end_ts}")

        # 2. 获取订单列表
        order_ids = self._fetch_quotation_list(start_ts, end_ts)
        if not order_ids:
            print(f"[同步] {year_month} 无订单数据")
            return {'orders': 0, 'items': 0, 'saved': 0, 'failed': 0}

        self.total_orders = len(order_ids)

        # 3. 遍历订单获取明细并统计
        quote_stats = defaultdict(int)
        self.total_items = 0
        self.failed_orders = 0

        for idx, order_id in enumerate(order_ids, 1):
            items = self._fetch_quotation_detail(order_id)
            self.total_items += len(items)

            for oe, brand in items:
                quote_stats[(oe, brand)] += 1

            # 每处理100个订单打印一次进度
            if idx % 100 == 0:
                print(f"[进度] 已处理 {idx}/{len(order_ids)} 个订单，"
                      f"获取 {self.total_items} 条明细")

            # 短暂暂停，避免请求过快
            time.sleep(0.2)

        print(f"[统计] 共处理 {len(order_ids)} 个订单，"
              f"获取 {self.total_items} 条明细，"
              f"失败 {self.failed_orders} 个订单")
        print(f"[统计] 共 {len(quote_stats)} 个(OE,品牌)组合")

        # 4. 保存到数据库
        saved = self._save_monthly_data(year_month, dict(quote_stats))
        print(f"[保存] {year_month}: 保存 {saved} 条记录")

        return {
            'orders': len(order_ids),
            'items': self.total_items,
            'saved': saved,
            'failed': self.failed_orders
        }

    def cleanup_old_data(self, keep_months: int = 37) -> int:
        """
        清理N个月前的历史数据

        Args:
            keep_months: 保留最近多少个月的数据（默认37个月）

        Returns:
            删除的记录数
        """
        # 计算截止日期（37个月前的年月）
        now = datetime.now()
        cutoff_year = now.year
        cutoff_month = now.month - keep_months

        # 处理月份跨年
        while cutoff_month <= 0:
            cutoff_year -= 1
            cutoff_month += 12

        cutoff_year_month = f"{cutoff_year}-{cutoff_month:02d}"

        with db_cursor() as cursor:
            sql = """
                DELETE FROM crmapp_quote_count_ks
                WHERE year_month < %s AND company = %s
            """
            cursor.execute(sql, (cutoff_year_month, self.COMPANY))
            deleted = cursor.rowcount
            print(f"[清理] 已删除 {deleted} 条 {keep_months} 个月前的历史数据（{cutoff_year_month}之前）")
            return deleted

    def sync_recent_two_months(self) -> Dict[str, Any]:
        """
        同步上一个月和当月的询价数据
        每天凌晨执行的主入口

        Returns:
            同步结果统计
        """
        print(f"\n{'='*70}")
        print(f"开思询价次数统计服务")
        print(f"开始时间: {datetime.now()}")
        print(f"{'='*70}")

        # 1. 先清理37个月前的历史数据
        print("[清理] 开始清理过期历史数据...")
        self.cleanup_old_data(keep_months=37)

        now = datetime.now()
        current_year = now.year
        current_month = now.month

        # 计算上一个月
        if current_month == 1:
            last_year = current_year - 1
            last_month = 12
        else:
            last_year = current_year
            last_month = current_month - 1

        all_results = {
            'months': [],
            'total_orders': 0,
            'total_items': 0,
            'total_saved': 0,
            'total_failed': 0
        }

        # 先处理上一个月，再处理当月
        months_to_sync = [
            (last_year, last_month),
            (current_year, current_month)
        ]

        for year, month in months_to_sync:
            result = self.sync_month(year, month)

            all_results['months'].append(f"{year}-{month:02d}")
            all_results['total_orders'] += result['orders']
            all_results['total_items'] += result['items']
            all_results['total_saved'] += result['saved']
            all_results['total_failed'] += result['failed']

            # 月份之间暂停一下
            time.sleep(2)

        print(f"\n{'='*70}")
        print(f"询价次数统计完成!")
        print(f"处理月份: {', '.join(all_results['months'])}")
        print(f"总订单数: {all_results['total_orders']}")
        print(f"总明细数: {all_results['total_items']}")
        print(f"保存记录: {all_results['total_saved']}")
        print(f"失败订单: {all_results['total_failed']}")
        print(f"{'='*70}")

        return all_results
