#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开思询价单明细定时爬取脚本

调用 QuoteCountSyncService.sync_date_range() 按天爬取指定日期范围的开思询价单明细，
并保存到 crmapp_ks_inquiry_detail 表，最后更新询价次数统计表。

用法：
    python -m app.scripts.run_ks_inquiry_detail_crawl
    python -m app.scripts.run_ks_inquiry_detail_crawl --begin 2026-06-01 --end 2026-06-25
    python -m app.scripts.run_ks_inquiry_detail_crawl --company fsbbr
"""

import sys
import os
import argparse

# 确保项目根目录在 PYTHONPATH 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.quote_count_service import QuoteCountSyncService


DEFAULT_BEGIN_DATE = "2026-06-01"
DEFAULT_END_DATE = "2026-06-25"


def run_crawl(begin_date: str, end_date: str, company: str = "fsbbr") -> dict:
    """
    执行指定日期范围的开思询价明细爬取与统计更新。

    Args:
        begin_date: 开始日期 (yyyy-MM-dd)
        end_date: 结束日期 (yyyy-MM-dd)
        company: 公司代码，默认 fsbbr

    Returns:
        dict: 爬取结果汇总
    """
    print(f"\n{'='*70}")
    print(f"启动开思询价单明细爬取脚本")
    print(f"日期范围: {begin_date} ~ {end_date}")
    print(f"公司代码: {company}")
    print(f"{'='*70}\n")

    service = QuoteCountSyncService()

    # 按日期范围爬取并保存明细
    crawl_result = service.sync_date_range(begin_date, end_date)

    # 更新统计表（上月+本月）
    print("\n[后续任务] 更新询价次数统计表...")
    stats_result = service.update_stats_from_details()

    final_result = {
        "begin_date": begin_date,
        "end_date": end_date,
        "company": company,
        "crawl": crawl_result,
        "stats": stats_result,
    }

    print(f"\n{'='*70}")
    print(f"脚本执行完成")
    print(f"  处理日期: {', '.join(crawl_result.get('dates', []))}")
    print(f"  总订单数: {crawl_result.get('total_orders', 0)}")
    print(f"  总明细数: {crawl_result.get('total_items', 0)}")
    print(f"  保存记录: {crawl_result.get('saved', 0)}")
    print(f"{'='*70}\n")

    return final_result


def main():
    parser = argparse.ArgumentParser(description="开思询价单明细定时爬取脚本")
    parser.add_argument(
        "--begin",
        type=str,
        default=DEFAULT_BEGIN_DATE,
        help=f"开始日期 (yyyy-MM-dd)，默认 {DEFAULT_BEGIN_DATE}",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=DEFAULT_END_DATE,
        help=f"结束日期 (yyyy-MM-dd)，默认 {DEFAULT_END_DATE}",
    )
    parser.add_argument(
        "--company",
        type=str,
        default="fsbbr",
        help="公司代码，默认 fsbbr",
    )

    args = parser.parse_args()

    run_crawl(args.begin, args.end, args.company)


if __name__ == "__main__":
    main()
