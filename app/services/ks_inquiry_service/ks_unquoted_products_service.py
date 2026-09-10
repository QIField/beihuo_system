# -*- coding:utf-8 -*-
"""
开思询价未报价产品计算服务
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Set, List, Tuple

from app.utils.database_connection import db_cursor
from app.utils.logger_config import get_task_logger

logger = get_task_logger('ks_quote_count')


class KsUnquotedProductsService:
    """计算 crmapp_ks_inquiry_detail 的未报价产品并写回"""

    SPLIT_PATTERN = re.compile(r'[,，/|;；\s]+')

    @staticmethod
    def split_oe_values(value: str) -> Set[str]:
        if not value:
            return set()
        return {item.strip() for item in KsUnquotedProductsService.SPLIT_PATTERN.split(str(value)) if item.strip()}

    @staticmethod
    def calculate_recent_days(days: int = 5) -> Dict[str, int]:
        begin_date = (datetime.now().date() - timedelta(days=days - 1)).strftime('%Y-%m-%d')
        logger.info(f"[未报价产品计算] 开始，范围近{days}天，开始日期={begin_date}")

        with db_cursor() as cursor:
            cursor.execute(
                """
                SELECT company, partsNum, brandNormalized
                FROM crmapp_ks_inquiry_detail
                WHERE quote_date >= %s
                  AND partsNum IS NOT NULL AND partsNum != ''
                """,
                (begin_date,)
            )
            inquiry_rows = cursor.fetchall()
            logger.info(f"[未报价产品计算] 查询到 {len(inquiry_rows)} 条询价记录")

            quoted_map: Dict[Tuple[str, str], Set[str]] = {}
            parts_by_company: Dict[str, Set[str]] = {}

            for row in inquiry_rows:
                company = row.get('company') if isinstance(row, dict) else row[0]
                parts_num = row.get('partsNum') if isinstance(row, dict) else row[1]
                brand = row.get('brandNormalized') if isinstance(row, dict) else row[2]

                if not company or not parts_num:
                    continue

                key = (company, str(parts_num).strip())
                quoted_map.setdefault(key, set())
                parts_by_company.setdefault(company, set()).add(key[1])

                if brand:
                    quoted_map[key].add(str(brand).strip())

            if not quoted_map:
                logger.info("[未报价产品计算] 无有效询价记录，跳过")
                return {'matched_parts': 0, 'updated_rows': 0}

            cursor.execute(
                """
                SELECT company, oe, `替换号`, `品牌`, `库存数量`
                FROM crmapp_beihuo
                WHERE `库存数量` > 0
                  AND company IS NOT NULL AND company != ''
                  AND `品牌` IS NOT NULL AND `品牌` != ''
                """
            )
            stock_rows = cursor.fetchall()

            unquoted_map: Dict[Tuple[str, str], List[str]] = {key: [] for key in quoted_map.keys()}
            seen_map: Dict[Tuple[str, str], Set[str]] = {key: set() for key in quoted_map.keys()}

            for row in stock_rows:
                if isinstance(row, dict):
                    company = row.get('company')
                    oe = row.get('oe')
                    replace_number = row.get('替换号')
                    brand = row.get('品牌')
                else:
                    company, oe, replace_number, brand, _ = row

                if not company or company not in parts_by_company or not brand:
                    continue

                candidate_oes = KsUnquotedProductsService.split_oe_values(oe)
                candidate_oes.update(KsUnquotedProductsService.split_oe_values(replace_number))
                if not candidate_oes:
                    continue

                brand_text = str(brand).strip()
                display_oe = str(oe).strip() if oe else ''

                for parts_num in parts_by_company[company].intersection(candidate_oes):
                    key = (company, parts_num)
                    if brand_text in quoted_map.get(key, set()):
                        continue

                    display_text = f"{display_oe}+{brand_text}" if display_oe else f"{parts_num}+{brand_text}"
                    if display_text not in seen_map[key]:
                        seen_map[key].add(display_text)
                        unquoted_map[key].append(display_text)

            update_params = []
            for (company, parts_num), products in unquoted_map.items():
                update_params.append(('，'.join(products), company, parts_num, begin_date))

            updated_rows = 0
            if update_params:
                cursor.executemany(
                    """
                    UPDATE crmapp_ks_inquiry_detail
                    SET unquoted_products = %s
                    WHERE company = %s
                      AND partsNum = %s
                      AND quote_date >= %s
                    """,
                    update_params
                )
                updated_rows = cursor.rowcount

            matched_parts = sum(1 for products in unquoted_map.values() if products)
            logger.info(f"[未报价产品计算] 完成: 范围近{days}天, 匹配OE数={matched_parts}, 更新行数={updated_rows}")

            return {'matched_parts': matched_parts, 'updated_rows': updated_rows}
