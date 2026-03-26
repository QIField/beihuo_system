"""
开思询价次数统计服务
用于从开思平台爬取询价数据并按(年月, 品牌, OE)统计询价次数

处理逻辑：
    - 按自然月批次处理数据
    - 先爬取上一个月和当月的数据
    - 每个月独立爬取、汇总、保存（覆盖模式）
    - 支持登录状态失效重试和网络重试机制
    - 使用API接口获取开思平台cookie进行认证
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import time
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

from app.utils.database_connection import db_cursor



def get_ks_cookies_from_api() -> dict:
    """
    从API接口获取开思平台的cookie

    Returns:
        dict: 包含cookie信息的字典
    """
    url = "http://113.45.176.129:8001/md_ks.get_cookies?md=fs"
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    data = response.json()
    # 接口返回格式：{'cookie': {...}}
    if 'cookie' in data:
        return data['cookie']
    else:
        # 直接返回整个响应作为cookie字典
        return data


class QuoteCountSyncService:
    """
    开思询价次数统计服务

    功能：
    1. 从开思平台爬取询价订单列表
    2. 遍历每个订单获取询价明细（OE号、品牌）
    3. 按(年月, 品牌, OE)统计询价次数
    4. 保存到 crmapp_quote_count_ks 表（覆盖模式）
    """

    # 开思平台API地址
    QUOTATION_LIST_URL = "https://www.cassmall.com/inquiry/seller/quote/list/v1"
    QUOTATION_DETAIL_URL_TEMPLATE = "https://www.cassmall.com/archiveinquiry/quotation/{}/quoting/items"

    # 请求配置
    PAGE_SIZE = 500  # 订单列表分页大小
    DETAIL_PAGE_SIZE = 50  # 订单明细分页大小
    MAX_RETRY = 3  # 最大重试次数
    RETRY_DELAY = 2  # 重试间隔（秒）
    COMPANY = 'fsbbr'  # 默认公司

    def __init__(self):
        self.session = None
        self.session_source = None  # 记录session来源
        self.total_orders = 0  # 总订单数
        self.total_items = 0   # 总明细条目数
        self.failed_orders = 0  # 失败订单数
        # 初始化时获取session
        self._init_session()

    def _init_session(self):
        """初始化session，使用API获取cookie"""
        ks_cookies = get_ks_cookies_from_api()
        self.session = self._create_session_from_cookies(ks_cookies)
        self.session_source = 'api_cookie'

    def _refresh_session(self):
        """刷新session"""
        self._init_session()

    def _create_session_from_cookies(self, cookies: dict) -> requests.Session:
        """
        使用cookie字典创建session
        """
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Referer': 'https://www.cassmall.com/seller',
            'Origin': 'https://www.cassmall.com',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        })

        # 将cookie添加到session
        if isinstance(cookies, dict):
            # 同时设置到cookies中
            for key, value in cookies.items():
                if key.lower() not in ['user-agent', 'accept', 'accept-language', 'referer', 'content-type', 'origin', 'cache-control', 'pragma']:
                    session.cookies.set(key, value, domain='.cassmall.com')

        return session

    def _get_month_range(self, year: int, month: int) -> Tuple[int, int]:
        """
        获取指定月份的起止时间戳（毫秒）
        """
        start_date = datetime(year, month, 1, 0, 0, 0)

        if month == 12:
            next_month = datetime(year + 1, 1, 1, 0, 0, 0)
        else:
            next_month = datetime(year, month + 1, 1, 0, 0, 0)
        end_date = next_month - timedelta(seconds=1)

        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)

        return start_ts, end_ts

    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        """
        带重试机制的HTTP请求
        """
        for attempt in range(self.MAX_RETRY):
            try:
                if method.lower() == 'get':
                    response = self.session.get(url, timeout=30, **kwargs)
                else:
                    response = self.session.post(url, timeout=30, **kwargs)

                response.raise_for_status()
                
                try:
                    result = response.json()
                except Exception as json_err:
                    print(f"[请求] JSON解析失败: {json_err}")
                    print(f"[请求] URL: {url}")
                    print(f"[请求] 状态码: {response.status_code}")
                    print(f"[请求] 响应头: {dict(response.headers)}")
                    print(f"[请求] 响应内容: {repr(response.text[:500])}")
                    print(f"[请求] 尝试刷新session...")
                    self._refresh_session()
                    if attempt < self.MAX_RETRY - 1:
                        time.sleep(self.RETRY_DELAY)
                        continue
                    else:
                        print(f"[请求] JSON解析失败，重试次数耗尽")
                        return None

                if result.get('code') == 401 or result.get('msg') == '登录已过期':
                    print(f"[请求] 登录状态失效，尝试刷新cookie...")
                    self._refresh_session()
                    if attempt < self.MAX_RETRY - 1:
                        time.sleep(self.RETRY_DELAY)
                        continue
                    else:
                        print(f"[请求] 登录失效，重试次数耗尽")
                        return None

                return result

            except requests.exceptions.HTTPError as e:
                if '401' in str(e):
                    print(f"[请求][{attempt+1}/{self.MAX_RETRY}] 认证失败(401)，尝试刷新cookie...")
                    try:
                        self._refresh_session()
                        if attempt < self.MAX_RETRY - 1:
                            time.sleep(self.RETRY_DELAY)
                            continue
                    except Exception as refresh_err:
                        print(f"[请求] 刷新cookie失败：{refresh_err}")
                else:
                    print(f"[请求][{attempt+1}/{self.MAX_RETRY}] HTTP错误: {e}")

                if attempt < self.MAX_RETRY - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                else:
                    print(f"[请求] 请求失败，重试次数耗尽")
                    return None

            except Exception as e:
                print(f"[请求][{attempt+1}/{self.MAX_RETRY}] 请求失败: {e}")
                if attempt < self.MAX_RETRY - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                else:
                    print(f"[请求] 请求失败，重试次数耗尽")
                    return None

        return None

    def _fetch_quotation_list(self, start_ts: int, end_ts: int) -> List[str]:
        """
        获取指定时间范围内的所有订单ID列表
        """
        order_ids = []
        page_num = 1

        while True:
            # 使用浏览器抓包得到的完整参数格式
            payload = {
                "inquiryType": "ALL",
                "navTab": "ALL",
                "onlyViewOwner": False,
                "storeId": "ALL",
                "inquiryId": "",
                "statusId": "ALL",
                "garageCompanyId": "",
                "quoteUser": "",
                "quoteType": "ALL",
                "systemQuoteReportStatus": "",
                "quoteScope": "ALL",
                "limitQuoteRange": False,
                "saasGroupLabels": ["ALL"],
                "startDate": start_ts,
                "endDate": end_ts,
                "pageNum": page_num,
                "pageSize": self.PAGE_SIZE,
                "isHighQualityLargeOrder": ""
            }

            result = self._make_request_with_retry(
                'post',
                self.QUOTATION_LIST_URL,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )

            if not result:
                print(f"[订单列表] 第{page_num}页请求失败，跳过")
                break

            if result.get('code') != 200:
                print(f"[订单列表] API返回错误: {result.get('msg')}")
                break

            data = result.get('data', {})
            quotation_list = data.get('quotationList', [])

            if not quotation_list:
                break

            for item in quotation_list:
                order_id = item.get('id')
                if order_id:
                    order_ids.append(order_id)

            print(f"[订单列表] 第{page_num}页获取 {len(quotation_list)} 条订单")

            # 检查是否还有下一页
            total_elements = data.get('totalElements', 0)
            # 计算总页数
            total_pages = (total_elements + self.PAGE_SIZE - 1) // self.PAGE_SIZE
            if page_num >= total_pages or len(quotation_list) < self.PAGE_SIZE:
                break

            page_num += 1
            time.sleep(0.5)

        print(f"[订单列表] 共获取 {len(order_ids)} 个订单ID")
        return order_ids

    def _fetch_quotation_detail(self, order_id: str) -> List[Tuple[str, str]]:
        """
        获取指定订单的询价明细，自动切换接口
        先尝试 inquiryWeb（当前订单接口），再尝试 archiveinquiry（历史订单接口）
        """
        items = []
        # 定义两个接口及其配置
        # inquiryWeb: 当前订单接口，需要请求体
        # archiveinquiry: 历史订单接口，不需要请求体
        url_configs = [
            {
                'url': f"https://www.cassmall.com/inquiryWeb/quotation/{order_id}/quoting/items",
                'json': {"pageNum": 1, "pageSize": 50},  # 需要请求体
                'name': 'inquiryWeb'
            },
            {
                'url': f"https://www.cassmall.com/archiveinquiry/quotation/{order_id}/quoting/items",
                'json': None,  # 不需要请求体
                'name': 'archiveinquiry'
            }
        ]
        
        for i, config in enumerate(url_configs, 1):
            url = config['url']
            json_data = config['json']
            
            # 根据接口类型决定是否发送请求体
            if json_data:
                result = self._make_request_with_retry(
                    'post',
                    url,
                    json=json_data,
                    headers={'Content-Type': 'application/json'}
                )
            else:
                result = self._make_request_with_retry(
                    'post',
                    url,
                    headers={'Content-Type': 'application/json'}
                )

            if not result:
                if i < len(url_configs):
                    # 静默重试，不打印日志
                    continue
                else:
                    # 所有接口都失败，记录失败但不打印详细日志
                    self.failed_orders += 1
                    return items

            if result.get('code') == 404:
                if i < len(url_configs):
                    # 静默重试，不打印日志
                    continue
                else:
                    # 订单不存在（可能已被删除），不算错误
                    return items

            if result.get('code') != 200:
                if i < len(url_configs):
                    # 静默重试，不打印日志
                    continue
                else:
                    # 记录失败但不打印详细日志
                    self.failed_orders += 1
                    return items

            # 成功获取数据，提取明细
            data = result.get('data', {})
            content_list = data.get('content', [])

            for content in content_list:
                store_quote_item_results = content.get('storeQuoteItemResults', [])

                if not store_quote_item_results:
                    continue

                for item in store_quote_item_results:
                    parts_num = item.get('partsNum', '').strip().upper()
                    brand_name = item.get('brandName', '').strip()

                    if parts_num and brand_name:
                        items.append((brand_name, parts_num))

            if items:
                return items
            elif i < len(url_configs):
                # 静默重试，不打印日志
                pass

        # 所有接口都无明细
        return items

    def _save_monthly_data(self, year_month: str, quote_data: Dict[Tuple[str, str], int], incremental: bool = False) -> int:
        """
        保存单月的询价统计数据到数据库
        
        Args:
            year_month: 年月字符串，如 "2023-04"
            quote_data: 统计字典，{(brand, oe): count}
            incremental: 是否为增量保存（True=增量更新，False=覆盖）
        """
        if not quote_data:
            print(f"[保存] {year_month}: 无数据需要保存")
            return 0

        with db_cursor() as cursor:
            if incremental:
                # 增量模式：查询已有数据，累加后更新
                select_sql = "SELECT brand, oe, quote_count FROM crmapp_quote_count_ks WHERE `year_month` = %s AND company = %s"
                cursor.execute(select_sql, (year_month, self.COMPANY))
                existing_rows = cursor.fetchall()
                
                # 构建已有数据的字典
                existing_data = {}
                for row in existing_rows:
                    brand, oe, count = row
                    existing_data[(brand, oe)] = count
                
                # 合并数据（累加）
                merged_data = {}
                all_keys = set(quote_data.keys()) | set(existing_data.keys())
                for key in all_keys:
                    merged_data[key] = quote_data.get(key, 0) + existing_data.get(key, 0)
                
                # 删除旧数据
                delete_sql = "DELETE FROM crmapp_quote_count_ks WHERE `year_month` = %s AND company = %s"
                cursor.execute(delete_sql, (year_month, self.COMPANY))
                
                # 插入合并后的数据
                insert_sql = "INSERT INTO crmapp_quote_count_ks (`year_month`, brand, oe, quote_count, company, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, NOW(), NOW())"
                values = [
                    (year_month, brand, oe, count, self.COMPANY)
                    for (brand, oe), count in merged_data.items()
                ]
                cursor.executemany(insert_sql, values)
                return len(values)
            else:
                # 覆盖模式：先删除再插入（用于整月重新统计）
                delete_sql = "DELETE FROM crmapp_quote_count_ks WHERE `year_month` = %s AND company = %s"
                cursor.execute(delete_sql, (year_month, self.COMPANY))
                deleted = cursor.rowcount
                if deleted > 0:
                    print(f"[保存] 已删除 {year_month} 旧数据 {deleted} 条")

                insert_sql = "INSERT INTO crmapp_quote_count_ks (`year_month`, brand, oe, quote_count, company, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, NOW(), NOW())"
                values = [
                    (year_month, brand, oe, count, self.COMPANY)
                    for (brand, oe), count in quote_data.items()
                ]
                cursor.executemany(insert_sql, values)
                return len(values)

    def sync_month(self, year: int, month: int) -> Dict[str, Any]:
        """
        同步指定月份的询价数据，每5天一段爬取并保存
        每段爬取完成后立即保存到数据库，避免数据丢失
        """
        year_month = f"{year}-{month:02d}"
        print(f"\n{'='*60}")
        print(f"[同步] 开始处理 {year_month} 的询价数据")
        print(f"{'='*60}")

        # 获取月份第一天和当月最后一天
        month_start = datetime(year, month, 1, 0, 0, 0)
        if month == 12:
            next_month = datetime(year + 1, 1, 1, 0, 0, 0)
        else:
            next_month = datetime(year, month + 1, 1, 0, 0, 0)
        month_last_day = next_month - timedelta(days=1)
        
        # 生成每5天一段的时间范围，严格限制在当月内
        time_ranges = []
        current_start = month_start
        while current_start <= month_last_day:
            # 计算结束日期：当前开始+4天（这样是5天），但不能超过当月最后一天
            current_end = current_start + timedelta(days=4)
            if current_end > month_last_day:
                current_end = month_last_day
            
            # 转换为时间戳，注意结束时间是当天的23:59:59
            start_ts = int(current_start.timestamp() * 1000)
            end_ts = int((current_end + timedelta(days=1) - timedelta(seconds=1)).timestamp() * 1000)
            
            # 格式化日期字符串
            start_date_str = current_start.strftime('%Y-%m-%d')
            end_date_str = current_end.strftime('%Y-%m-%d')
            
            time_ranges.append((start_ts, end_ts, start_date_str, end_date_str))
            
            # 下一段从结束日期+1天开始
            current_start = current_end + timedelta(days=1)

        print(f"[同步] 分成 {len(time_ranges)} 个时间段:")
        for i, (_, _, start_date, end_date) in enumerate(time_ranges, 1):
            print(f"  第{i}段: {start_date} ~ {end_date}")

        # 清空该月旧数据（确保重新统计时数据准确）
        with db_cursor() as cursor:
            delete_sql = "DELETE FROM crmapp_quote_count_ks WHERE `year_month` = %s AND company = %s"
            cursor.execute(delete_sql, (year_month, self.COMPANY))
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"[同步] 已清空 {year_month} 旧数据 {deleted} 条，开始重新统计")

        # 累计统计数据
        all_quote_stats = defaultdict(int)
        total_orders = 0
        total_items = 0
        total_failed = 0
        processed_order_ids = set()  # 用于去重

        # 逐段处理，每段爬取完立即保存
        for i, (start_ts, end_ts, start_date, end_date) in enumerate(time_ranges, 1):
            print(f"\n{'='*60}")
            print(f"[同步] 处理第{i}/{len(time_ranges)}段: {start_date} ~ {end_date}")
            print(f"{'='*60}")

            # 1. 获取该时间段的订单列表
            order_ids = self._fetch_quotation_list(start_ts, end_ts)
            if not order_ids:
                print(f"[同步] 第{i}段无订单数据，跳过")
                continue
            
            # 去重：过滤掉已经处理过的订单
            new_order_ids = [oid for oid in order_ids if oid not in processed_order_ids]
            processed_order_ids.update(order_ids)
            
            print(f"[同步] 第{i}段获取 {len(order_ids)} 个订单（新订单 {len(new_order_ids)} 个）")
            
            if not new_order_ids:
                print(f"[同步] 第{i}段所有订单已处理过，跳过")
                continue

            # 2. 获取订单明细并统计
            segment_stats = defaultdict(int)
            segment_items = 0
            segment_failed = 0

            for idx, order_id in enumerate(new_order_ids, 1):
                items = self._fetch_quotation_detail(order_id)
                segment_items += len(items)

                for brand, oe in items:
                    segment_stats[(brand, oe)] += 1

                if idx % 100 == 0:
                    print(f"[进度] 第{i}段已处理 {idx}/{len(new_order_ids)} 个订单，"
                          f"获取 {segment_items} 条明细")

                time.sleep(0.2)

            print(f"[同步] 第{i}段处理完成: {len(new_order_ids)} 个订单, "
                  f"{segment_items} 条明细, 失败 {segment_failed} 个")

            # 3. 合并到总统计
            for key, count in segment_stats.items():
                all_quote_stats[key] += count
            total_orders += len(new_order_ids)
            total_items += segment_items
            total_failed += segment_failed

            # 4. 立即保存当前段数据（增量模式，累加到已有数据）
            if segment_stats:
                saved = self._save_monthly_data(year_month, dict(segment_stats), incremental=True)
                print(f"[保存] 第{i}段完成，新增 {len(segment_stats)} 种(品牌,OE)组合，累计保存 {saved} 条记录")

            # 5. 段与段之间暂停，避免请求过快
            if i < len(time_ranges):
                print(f"[暂停] 等待1秒后继续下一段...")
                time.sleep(1)

        # 最终统计
        print(f"\n{'='*60}")
        print(f"[统计] {year_month} 处理完成")
        print(f"[统计] 共处理 {total_orders} 个订单，"
              f"获取 {total_items} 条明细，"
              f"失败 {total_failed} 个订单")
        print(f"[统计] 共 {len(all_quote_stats)} 个(品牌,OE)组合")
        print(f"{'='*60}")

        return {
            'orders': total_orders,
            'items': total_items,
            'saved': len(all_quote_stats),
            'failed': total_failed
        }

    def cleanup_old_data(self, keep_months: int = 37) -> int:
        """
        清理N个月前的历史数据
        """
        now = datetime.now()
        cutoff_year = now.year
        cutoff_month = now.month - keep_months

        while cutoff_month <= 0:
            cutoff_year -= 1
            cutoff_month += 12

        cutoff_year_month = f"{cutoff_year}-{cutoff_month:02d}"

        with db_cursor() as cursor:
            delete_sql = "DELETE FROM crmapp_quote_count_ks WHERE `year_month` < %s AND company = %s"
            cursor.execute(delete_sql, (cutoff_year_month, self.COMPANY))
            deleted = cursor.rowcount
            print(f"[清理] 已删除 {deleted} 条 {keep_months} 个月前的历史数据（{cutoff_year_month}之前）")
            return deleted

    def sync_recent_two_months(self) -> Dict[str, Any]:
        """
        同步上一个月和当月的询价数据
        """
        print(f"\n{'='*70}")
        print(f"开思询价次数统计服务")
        print(f"开始时间: {datetime.now()}")
        print(f"{'='*70}")

        print("[清理] 开始清理过期历史数据...")
        self.cleanup_old_data(keep_months=37)

        now = datetime.now()
        current_year = now.year
        current_month = now.month

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
