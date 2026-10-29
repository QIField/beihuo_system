# -*- coding:utf-8 -*-
# @Time    : 2026/10/29
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : scan_service.py
# @Desc    : OE替换号差异扫描：全量内存匹配计算 + 差异判定 + 极简 Excel 导出
#
#            匹配规则复用 oe_match_service（主oe全等 ∪ 替换号拆分全等包含）。
#            差异判定：匹配行的 replace_number 拆成号码集合与并集比较，
#            多一个/少一个号即差异（不比较顺序，不剔除 brand_code）。
#            全程不走 CRM 接口，一次读表 + 内存计算，万级 oe 秒级完成。

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pymysql
from openpyxl import Workbook

from app.services.oe_match_service import split_numbers
from app.services.oe_diff_scan_service import db_service
from app.utils.database_connection import get_db_connection

# Excel 文件分类名，遵循通用下载路由 static/exports/{category}_{company}_{date}.xlsx 命名约定
EXPORT_CATEGORY = 'oe_replace_diff'


def evaluate_oe(oe: str, rows: List[Dict]) -> Dict:
    """对单个 oe 的匹配行做替换号差异判定，返回一条扫描结果记录"""
    number_sets = [set(split_numbers(row.get('replace_number'))) for row in rows]
    union = set().union(*number_sets) if number_sets else set()

    if not rows:
        status = '未匹配'
    elif len(rows) == 1:
        status = '单行'
    elif any(nums != union for nums in number_sets):
        status = '有差异'
    else:
        status = '一致'

    return {
        'oe': oe,
        'matched_count': len(rows),
        'status': status,
        'scanned_time': datetime.now(),
    }


def compute_scan_results(rows: List[Dict], pending_oes: List[str]) -> List[Dict]:
    """
    全量内存计算：主oe索引 + 替换号倒排索引，
    对每个待扫描 oe 聚合匹配行（两路匹配、按行去重）后判定差异
    """
    primary_index = defaultdict(list)         # oe -> [row]
    replace_number_index = defaultdict(list)  # 号码 -> [row]
    for row in rows:
        primary_index[(row.get('oe') or '').strip()].append(row)
        for number in split_numbers(row.get('replace_number')):
            replace_number_index[number].append(row)

    results = []
    for oe in pending_oes:
        matched = list(primary_index.get(oe, []))
        seen = {id(r) for r in matched}
        for row in replace_number_index.get(oe, []):
            if id(row) not in seen:
                matched.append(row)
        results.append(evaluate_oe(oe, matched))
    return results


def _load_summary_rows(company: str) -> List[Dict]:
    """一次性读入匹配计算所需的全表字段"""
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT product_id, oe, brand, replace_number "
                "FROM crmapp_compare_summary WHERE company = %s AND oe <> ''",
                (company,),
            )
            return cursor.fetchall()
    finally:
        conn.close()


def export_diff_excel(company: str, oes: List[str]) -> str:
    """
    生成当日发放批次的极简 Excel（单 Sheet 单列：oe）
    文件名遵循通用下载路由约定，可直接通过 /download_excel/<category>/<company>/<date> 下载
    """
    export_dir = Path(__file__).resolve().parents[3] / 'static' / 'exports'
    export_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime('%Y%m%d')
    file_path = export_dir / f'{EXPORT_CATEGORY}_{company}_{date_str}.xlsx'

    wb = Workbook()
    ws = wb.active
    ws.title = '替换号差异'
    ws.append(['oe'])
    for oe in oes:
        ws.append([oe])
    wb.save(file_path)
    return str(file_path)


def run_daily_scan(company: str = 'fsbbr') -> dict:
    """
    扫描当日未计算的 oe 并写结果表（已扫描过的永不重算），返回扫描量与差异池统计
    """
    db_service.ensure_table()
    pending = db_service.fetch_unscanned_oes(company)

    scanned = 0
    if pending:
        results = compute_scan_results(_load_summary_rows(company), pending)
        db_service.upsert_scan_results(company, results)
        scanned = len(results)

    return {
        'company': company,
        'scanned': scanned,
        'pool': db_service.fetch_pool_stats(company),
    }
