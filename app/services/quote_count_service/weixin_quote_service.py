"""
微信解码结果询价解析服务
用于从 weixin_decoding_result 表解析询价数据并保存到数据库

处理逻辑：
    - 从 weixin_decoding_result 表读取 result 字段
    - 解析 VIN、OE号、品牌
    - 跳过无效数据（= 0 或无品牌）
    - 保存到 crmapp_weixin_inquiry_detail 表
    - 支持按日期范围解析
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import re
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.utils.database_connection import db_cursor


class WeixinQuoteParserService:
    """
    微信询价解析服务

    功能：
    1. 从 weixin_decoding_result 表读取数据
    2. 解析 result 字段提取 OE+品牌
    3. 保存到 crmapp_weixin_inquiry_detail 表
    """

    COMPANY = 'fsbbr'

    # 正则表达式：匹配 (OE号)
    OE_PATTERN = re.compile(r'\(([^)]+)\)')

    def __init__(self):
        pass

    def _parse_result_content(self, content: str, creation_date: datetime) -> List[Dict[str, Any]]:
        """
        解析单条 result 内容，提取 OE+品牌

        Args:
            content: result 字段内容
            creation_date: 记录创建时间

        Returns:
            解析结果列表，每项包含 oe、brand 和 creation_date
        """
        results = []
        if not content:
            return results

        # 按行分割
        lines = content.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 跳过 VIN 行（没有 = 号）
            if '=' not in line:
                continue

            # 分割内容和品牌部分
            parts = line.split('=', 1)
            if len(parts) < 2:
                continue

            content_part = parts[0].strip()
            brand_part = parts[1].strip()

            # 跳过 = 0 或空的情况
            if brand_part == '0' or not brand_part:
                continue

            # 提取 OE 号
            oe_match = self.OE_PATTERN.search(content_part)
            if not oe_match:
                continue

            oe = oe_match.group(1).strip().upper().replace(' ', '')
            if not oe:
                continue

            # 解析品牌列表
            brand_items = brand_part.split('/')
            for brand_item in brand_items:
                brand_item = brand_item.strip()
                if not brand_item:
                    continue

                # 提取品牌名（取空格前的部分）
                brand = brand_item.split()[0].strip()

                # 去除括号及内容，如 "马勒(副水壶盖)" → "马勒"
                brand = re.sub(r'\([^)]*\)', '', brand).strip()

                if brand:
                    results.append({
                        'oe': oe,
                        'brand': brand,
                        'creation_date': creation_date
                    })

        return results

    def _fetch_weixin_records(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        从数据库获取指定日期范围的微信解码记录

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            记录列表
        """
        records = []

        # 字段映射配置：数据库字段名 -> 程序字段名
        # 同时支持元组索引和字典键名访问
        FIELD_MAPPING = [
            {'db_key': 'id', 'idx': 0, 'app_key': 'id'},
            {'db_key': 'creation_date', 'idx': 1, 'app_key': 'creation_date'},
            {'db_key': 'groupname', 'idx': 2, 'app_key': 'groupname'},
            {'db_key': 'nickname', 'idx': 3, 'app_key': 'nickname'},
            {'db_key': 'content', 'idx': 4, 'app_key': 'content'},
            {'db_key': 'result', 'idx': 5, 'app_key': 'result'},
        ]

        with db_cursor() as cursor:
            sql = """
                SELECT id, creation_date, groupname, nickname, content, result
                FROM weixin_decoding_result
                WHERE DATE(creation_date) >= %s
                  AND DATE(creation_date) <= %s
                  AND result IS NOT NULL
                  AND result != ''
                ORDER BY creation_date
            """
            cursor.execute(sql, (start_date, end_date))
            rows = cursor.fetchall()

            for row in rows:
                # 使用字段映射获取数据，自动适配元组或字典格式
                record = {}
                is_dict = isinstance(row, dict)
                
                for mapping in FIELD_MAPPING:
                    if is_dict:
                        # 字典格式：使用数据库字段名
                        record[mapping['app_key']] = row.get(mapping['db_key'])
                    else:
                        # 元组格式：使用索引
                        record[mapping['app_key']] = row[mapping['idx']]
                
                records.append(record)

        return records

    def _save_weixin_inquiry_details(self, items: List[Dict[str, Any]]) -> int:
        """
        批量保存微信询价明细到数据库

        Args:
            items: 解析结果列表，每项包含 oe、brand 和 creation_date

        Returns:
            保存数量
        """
        if not items:
            return 0

        with db_cursor() as cursor:
            insert_sql = """
                INSERT INTO crmapp_weixin_inquiry_detail
                (oe, brand, creation_date, company, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                    updated_at = NOW()
            """

            values = []
            for item in items:
                creation_date = item.get('creation_date')
                # 如果是 datetime 类型，直接使用；否则转换
                if isinstance(creation_date, datetime):
                    date_val = creation_date
                else:
                    date_val = datetime.now()

                row = (
                    item.get('oe', ''),
                    item.get('brand', ''),
                    date_val,
                    self.COMPANY
                )
                values.append(row)

            cursor.executemany(insert_sql, values)
            return len(values)

    def parse_date_range(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        解析指定日期范围的微信询价数据

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            处理结果统计
        """
        print(f"\n{'='*70}")
        print(f"微信询价解析服务")
        print(f"日期范围: {start_date} ~ {end_date}")
        print(f"{'='*70}")

        # 1. 获取记录
        print(f"\n[1/3] 获取微信解码记录...")
        records = self._fetch_weixin_records(start_date, end_date)
        print(f"[结果] 获取 {len(records)} 条记录")

        if not records:
            return {
                'success': True,
                'record_count': 0,
                'parsed_count': 0,
                'saved_count': 0
            }

        # 2. 解析内容
        print(f"\n[2/3] 解析询价数据...")
        all_items = []
        for idx, record in enumerate(records, 1):
            items = self._parse_result_content(record['result'], record['creation_date'])
            all_items.extend(items)

            if idx % 100 == 0:
                print(f"  [进度] 已处理 {idx}/{len(records)} 条记录，解析 {len(all_items)} 条明细")

        print(f"[结果] 共解析 {len(all_items)} 条询价明细")

        # 3. 保存到数据库
        print(f"\n[3/3] 保存到数据库...")
        saved = self._save_weixin_inquiry_details(all_items)
        print(f"[结果] 保存 {saved} 条明细")

        # 统计信息
        brand_stats = {}
        for item in all_items:
            brand = item.get('brand', '未知')
            brand_stats[brand] = brand_stats.get(brand, 0) + 1

        print(f"\n{'='*70}")
        print(f"微信询价解析完成!")
        print(f"记录数: {len(records)}")
        print(f"解析数: {len(all_items)}")
        print(f"保存数: {saved}")
        print(f"\n品牌分布(Top 10):")
        for brand, count in sorted(brand_stats.items(), key=lambda x: -x[1])[:10]:
            print(f"  - {brand}: {count} 条")
        print(f"{'='*70}\n")

        return {
            'success': True,
            'record_count': len(records),
            'parsed_count': len(all_items),
            'saved_count': saved,
            'brand_stats': brand_stats
        }

    def parse_recent_days(self, days: int = 5) -> Dict[str, Any]:
        """
        解析近N天的微信询价数据

        Args:
            days: 天数，默认5天

        Returns:
            处理结果统计
        """
        today = datetime.now().date()
        start_date = (today - timedelta(days=days - 1)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

        return self.parse_date_range(start_date, end_date)
