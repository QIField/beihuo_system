# -*- coding:utf-8 -*-
# @Time    : 2026/10/28
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : matcher.py

"""
oe-only 匹配逻辑（复刻自采购历史比对 query_compare_summary_rows 重构版）

匹配规则（不区分品牌，两条路径均为全等比对）：
- 主OE：crmapp_compare_summary.oe == oe
- 替换号：replace_number 按中英文逗号拆分后包含 oe

CRM 侧对应"直接命中"：number == oe 或 oe ∈ display_number。
注意：CRM numberlist 接口按产品组返回，组内兄弟产品与 oe 无直接号关系，
不属于匹配结果（线上实测：直接命中口径与数据库匹配 20/20 一致）。
"""

import re
from typing import Dict, List

import pymysql

from app.utils.database_connection import get_db_connection
from app.utils.replace_number.crm_api_client import search_products_by_numberlist


def split_numbers(replace_number) -> List[str]:
    """替换号串按中英文逗号拆分，逐个去首尾空格，去空"""
    if not replace_number:
        return []
    return [n.strip() for n in re.split(r'[，,]', str(replace_number)) if n.strip()]


def match_oe_rows(company: str, oe: str) -> List[Dict]:
    """
    数据库侧：只按 oe 匹配 crmapp_compare_summary，返回命中行

    SQL 粗筛（oe 相等 OR replace_number LIKE）缩小范围，
    Python 精滤（主OE全等 / 替换号拆分全等）消除子串误命中。

    Returns:
        [{'product_id', 'oe', 'brand', 'replace_number'}, ...]
    """
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT product_id, oe, brand, replace_number FROM crmapp_compare_summary "
                "WHERE company = %s AND (oe = %s OR replace_number LIKE %s)",
                (company, oe, f"%{oe}%"),
            )
            rows = cursor.fetchall()
    finally:
        conn.close()

    return [
        row for row in rows
        if (row.get('oe') or '').strip() == oe
        or oe in split_numbers(row.get('replace_number'))
    ]


def match_oe_product_ids(company: str, oe: str) -> List[str]:
    """数据库侧匹配行的 product_id 列表"""
    return [str(row.get('product_id') or '').strip()
            for row in match_oe_rows(company, oe)
            if str(row.get('product_id') or '').strip()]


def crm_direct_hits(company: str, oe: str) -> List[Dict]:
    """
    CRM 侧：numberlist 搜索结果中与 oe 直接命中的产品

    直接命中 = child.number == oe 或 oe 出现在 child.display_number 中

    Returns:
        [{'product_id', 'number', 'brand_name'}, ...]
    """
    api_data = search_products_by_numberlist(company, oe)
    hits = []
    if not api_data:
        return hits

    for group in api_data.get('data', []):
        for child in group.get('child', []):
            hit = str(child.get('number', '')).strip() == oe
            if not hit:
                for item in child.get('display_number') or []:
                    if isinstance(item, dict) and str(item.get('number', '')).strip() == oe:
                        hit = True
                        break
            if hit:
                hits.append({
                    'product_id': str(child.get('product_id', '')),
                    'number': str(child.get('number', '')).strip(),
                    'brand_name': str(child.get('brand_name', '')).strip(),
                })
    return hits


def compare_oe_with_crm(company: str, oe: str) -> Dict:
    """
    对比数据库匹配与 CRM 直接命中的 product_id 差异

    Returns:
        {'db_ids', 'crm_ids', 'extra', 'missing'}
        extra: 数据库多出（db - crm）；missing: 数据库缺少（crm - db）
    """
    db_ids = set(match_oe_product_ids(company, oe))
    crm_ids = {h['product_id'] for h in crm_direct_hits(company, oe) if h['product_id']}
    return {
        'db_ids': sorted(db_ids),
        'crm_ids': sorted(crm_ids),
        'extra': sorted(db_ids - crm_ids),
        'missing': sorted(crm_ids - db_ids),
    }
