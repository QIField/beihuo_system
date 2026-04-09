"""
每日定时任务入口
串行执行所有爬取与同步任务

执行顺序：
1. CRM全量爬取
2. 采购历史爬取（近5天）+ 聚合到旧表
3. 采购数据同步到比价表（旧表数据同步到比价汇总表）
4. 销量明细爬取（近5天）+ 保存到销量明细表

注：
- 询价次数同步已移至独立的 9:15 定时任务 ks_quote_count_task
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import time
import traceback
from datetime import datetime


def execute_daily_pipeline():
    """每日定时任务入口：串行执行所有爬取与同步任务"""

    start_time = datetime.now()
    print(f"\n{'='*80}")
    print(f"每日定时任务开始执行")
    print(f"任务时间: {start_time}")
    print(f"{'='*80}")

    all_results = {
        'total_synced': 0,
        'total_failed': 0,
        'tasks': {}
    }

    # 1. CRM全量爬取
    try:
        print(f"\n{'='*60}")
        print(f"1. 开始CRM全量爬取")
        print(f"{'='*60}")

        from app.services.procurement_service.crawl_service import CRMDataCrawlService
        service = CRMDataCrawlService()
        crm_result = service.crawl_all()

        all_results['tasks']['crm_crawl'] = crm_result
        all_results['total_synced'] += crm_result.get('saved', 0)
        all_results['total_failed'] += crm_result.get('failed', 0)

        print(f"\n[CRM全量爬取] 结束:")
        print(f"  - 总记录数: {crm_result.get('total', 0)}")
        print(f"  - 成功保存: {crm_result.get('saved', 0)}")
        print(f"  - 失败: {crm_result.get('failed', 0)}")

    except Exception as e:
        print(f"\n[CRM全量爬取] 出现异常: {e}")
        traceback.print_exc()
        all_results['tasks']['crm_crawl'] = {'error': str(e)}
        all_results['total_failed'] += 1

    # 2. 采购历史爬取（近5天）+ 聚合到旧表
    try:
        print(f"\n{'='*60}")
        print(f"2. 开始采购历史爬取（近5天）+ 聚合到旧表")
        print(f"{'='*60}")

        from app.services.procurement_service.purchase_history_main import run
        purchase_history_result = run(company='fsbbr', days=5)

        all_results['tasks']['purchase_history'] = purchase_history_result
        
        # 统计爬取和聚合结果
        crawl_result = purchase_history_result.get('crawl', {})
        aggregate_result = purchase_history_result.get('aggregate', {})
        all_results['total_synced'] += crawl_result.get('saved', 0)

        print(f"\n[采购历史爬取] 结束:")
        print(f"  [爬取结果]:")
        print(f"    - 处理记录数: {crawl_result.get('total_processed', 0)}")
        print(f"    - 保存记录: {crawl_result.get('saved', 0)}")
        print(f"  [聚合结果]:")
        print(f"    - 聚合记录数: {aggregate_result.get('aggregated_count', 0)}")
        print(f"    - 保存记录: {aggregate_result.get('saved', 0)}")

    except Exception as e:
        print(f"\n[采购历史爬取] 出现异常: {e}")
        traceback.print_exc()
        all_results['tasks']['purchase_history'] = {'error': str(e)}
        all_results['total_failed'] += 1

    # 3. 采购数据同步到比价表
    try:
        print(f"\n{'='*60}")
        print(f"3. 开始采购数据同步到比价表")
        print(f"{'='*60}")

        from app.services.procurement_service.purchase_sync_service import PurchaseSyncService
        service = PurchaseSyncService()
        sync_result = service.sync_to_compare_summary(company='fsbbr')

        all_results['tasks']['purchase_sync'] = sync_result
        all_results['total_synced'] += sync_result.get('saved', 0)

        print(f"\n[采购数据同步] 结束:")
        print(f"  - 同步记录数: {sync_result.get('saved', 0)}")
        print(f"  - 重复记录: {sync_result.get('duplicate', 0)}")

    except Exception as e:
        print(f"\n[采购数据同步] 出现异常: {e}")
        traceback.print_exc()
        all_results['tasks']['purchase_sync'] = {'error': str(e)}
        all_results['total_failed'] += 1

    # 4. 销量明细爬取（近5天）
    try:
        print(f"\n{'='*60}")
        print(f"4. 开始销量明细爬取（近5天）")
        print(f"{'='*60}")

        from app.services.sales_history_service.data_sync_service import SalesHistorySyncService
        service = SalesHistorySyncService()
        sales_result = service.sync_recent_days(days=5)

        all_results['tasks']['sales_sync'] = sales_result
        all_results['total_synced'] += sales_result.get('saved', 0)

        print(f"\n[销量明细爬取] 结束:")
        print(f"  - 总页数: {sales_result.get('total_pages', 0)}")
        print(f"  - 总条目: {sales_result.get('total_items', 0)}")
        print(f"  - 保存记录: {sales_result.get('saved', 0)}")

    except Exception as e:
        print(f"\n[销量明细爬取] 出现异常: {e}")
        traceback.print_exc()
        all_results['tasks']['sales_sync'] = {'error': str(e)}
        all_results['total_failed'] += 1

    # 输出最终执行报告
    end_time = datetime.now()
    duration = end_time - start_time

    print(f"\n{'='*80}")
    print(f"每日定时任务执行报告")
    print(f"开始时间: {start_time}")
    print(f"结束时间: {end_time}")
    print(f"总耗时: {duration}")
    print(f"{'='*80}")

    print(f"\n📊 总同步记录数: {all_results['total_synced']}")
    print(f"❌ 总失败数: {all_results['total_failed']}")

    if all_results['total_failed'] > 0:
        print("\n⚠️  检测到部分任务失败，详见上方错误日志。")

    print(f"\n{'='*80}")
    print(f"每日定时任务执行完毕")
    print(f"{'='*80}")

    return all_results


if __name__ == '__main__':
    execute_daily_pipeline()
