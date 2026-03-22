"""
手动历史数据爬取脚本
用于补录 2024年1月 到 2026年当前月份 的所有采购历史数据

使用方法:
    python scripts/manual_purchase_history_crawler.py
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import time
import traceback
from datetime import datetime

# 初始化 SessionManager，设置 CRM session 工厂函数
from app.utils.session_manager import SessionManager
from config import create_crm_session
SessionManager.set_session_factory(create_crm_session)

from app.services.procurement_service.purchase_history_service import PurchaseHistoryService


def get_months_range(start_year: int, start_month: int, end_year: int, end_month: int):
    """
    获取指定时间范围内的所有年月组合

    Args:
        start_year: 开始年份
        start_month: 开始月份
        end_year: 结束年份
        end_month: 结束月份

    Returns:
        List[Tuple[int, int]]: [(year, month), ...]
    """
    months = []
    year, month = start_year, start_month

    while (year < end_year) or (year == end_year and month <= end_month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1

    return months


def execute_manual_crawl():
    """
    手动执行历史数据爬取
    爬取 2024年1月 到 2026年当前月份 的所有数据
    """
    start_time = datetime.now()
    print(f"\n{'='*80}")
    print(f"手动历史数据爬取任务开始")
    print(f"开始时间: {start_time}")
    print(f"{'='*80}")

    # 定义时间范围
    start_year, start_month = 2024, 1
    now = datetime.now()
    end_year, end_month = now.year, now.month

    print(f"\n爬取时间范围: {start_year}年{start_month}月 至 {end_year}年{end_month}月")

    # 获取所有月份列表
    months_list = get_months_range(start_year, start_month, end_year, end_month)
    print(f"共需处理 {len(months_list)} 个月份")

    # 统计结果
    all_results = {
        'months': [],
        'total_processed': 0,
        'total_saved': 0,
        'total_failed': 0,
        'errors': []
    }

    # 创建服务实例
    service = PurchaseHistoryService()

    # 循环遍历每个月份
    for idx, (year, month) in enumerate(months_list, 1):
        month_str = f"{year}-{month:02d}"
        print(f"\n{'='*60}")
        print(f"[{idx}/{len(months_list)}] 开始处理 {month_str}")
        print(f"{'='*60}")

        try:
            # 爬取该月份数据
            result = service.crawl_month(year, month)

            # 记录结果
            all_results['months'].append(month_str)
            all_results['total_processed'] += result['processed']
            all_results['total_saved'] += result['saved']
            all_results['total_failed'] += result['failed']

            print(f"\n{month_str} 处理完成:")
            print(f"  - 处理记录数: {result['processed']}")
            print(f"  - 保存记录数: {result['saved']}")
            print(f"  - 失败数: {result['failed']}")

        except Exception as e:
            error_msg = f"{month_str} 处理失败: {str(e)}"
            print(f"\n❌ {error_msg}")
            traceback.print_exc()
            all_results['errors'].append(error_msg)
            all_results['total_failed'] += 1

        # 月份之间暂停1秒，避免请求过快
        if idx < len(months_list):
            print(f"\n⏸️  暂停1秒后继续...")
            time.sleep(1)

    # 输出最终执行报告
    end_time = datetime.now()
    duration = end_time - start_time

    print(f"\n{'='*80}")
    print(f"手动历史数据爬取任务执行报告")
    print(f"{'='*80}")
    print(f"开始时间: {start_time}")
    print(f"结束时间: {end_time}")
    print(f"总耗时: {duration}")
    print(f"{'='*80}")

    print(f"\n📊 统计信息:")
    print(f"  - 处理月份数: {len(all_results['months'])}")
    print(f"  - 月份列表: {', '.join(all_results['months'])}")
    print(f"  - 总处理记录数: {all_results['total_processed']}")
    print(f"  - 总保存记录数: {all_results['total_saved']}")
    print(f"  - 总失败数: {all_results['total_failed']}")

    if all_results['errors']:
        print(f"\n⚠️  错误记录 ({len(all_results['errors'])} 条):")
        for error in all_results['errors']:
            print(f"  - {error}")

    print(f"\n{'='*80}")
    print(f"手动历史数据爬取任务执行完毕")
    print(f"{'='*80}")

    return all_results


if __name__ == '__main__':
    execute_manual_crawl()
