"""
手动运行版本 - CRM销量明细爬取
用于初始化近1年的销量数据

运行方式:
    python scripts/manual_sales_crawler.py

处理逻辑：
    - 将365天分批次处理（每5天一批）
    - 每批独立爬取、计算、保存
    - 避免跨批次数据累加问题
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.session_init import init_session_manager
from app.services.sales_history_service import SalesHistorySyncService


def main():
    """
    主函数：分批爬取近1年销量数据（每5天一批）
    """
    print("=" * 70)
    print("CRM销量明细手动爬取工具")
    print("=" * 70)
    print("本脚本将分批爬取近1年（365天）的销量数据")
    print("每5天为一批次，独立处理保存")
    print("直接连接线上数据库")
    print("=" * 70)
    
    # 初始化SessionManager
    init_session_manager()
    
    # 创建服务实例
    service = SalesHistorySyncService()
    
    # 分批处理：每5天一批
    BATCH_DAYS = 5
    TOTAL_DAYS = 365
    
    all_results = {
        'total_pages': 0,
        'total_items': 0,
        'total_saved': 0,
        'batches': 0
    }
    
    # 从近到远处理（先处理最近的）
    for batch_start in range(0, TOTAL_DAYS, BATCH_DAYS):
        batch_end = min(batch_start + BATCH_DAYS, TOTAL_DAYS)
        days_in_batch = batch_end - batch_start
        
        print(f"\n{'='*70}")
        print(f"[批次 {batch_start//BATCH_DAYS + 1}/{(TOTAL_DAYS-1)//BATCH_DAYS + 1}] "
              f"处理最近第{batch_start+1}天到第{batch_end}天的数据")
        print(f"{'='*70}")
        
        # 执行同步（指定偏移天数和批次天数）
        result = service.sync_by_offset(
            offset_days=batch_start,
            days=days_in_batch
        )
        
        all_results['total_pages'] += result.get('total_pages', 0)
        all_results['total_items'] += result.get('total_items', 0)
        all_results['total_saved'] += result.get('saved', 0)
        all_results['batches'] += 1
        
        print(f"[批次完成] 页数:{result.get('total_pages', 0)}, "
              f"条目:{result.get('total_items', 0)}, 保存:{result.get('saved', 0)}")
    
    # 最后统一更新汇总表
    print(f"\n{'='*70}")
    print("所有批次爬取完成，更新汇总统计表...")
    service.update_summary_table()
    
    print("\n" + "=" * 70)
    print("爬取完成!")
    print(f"总批次: {all_results['batches']}")
    print(f"总页数: {all_results['total_pages']}")
    print(f"总条目: {all_results['total_items']}")
    print(f"保存记录: {all_results['total_saved']}")
    print("=" * 70)


if __name__ == '__main__':
    main()
