"""
采购历史明细爬取脚本 - 最近一年
调用 PurchaseHistoryService 模块，爬取最近一年的采购历史数据

使用方法:
    python scripts/crawl_purchase_history_one_year.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime
from app.services.procurement_service.purchase_history_service import PurchaseHistoryService
from app.services.procurement_service.purchase_history_aggregate_service import PurchaseHistoryAggregateService


def crawl_purchase_history_one_year():
    """
    爬取最近一年的采购历史明细数据
    """
    print("\n" + "="*80)
    print("📦 采购历史明细爬取 - 最近一年")
    print("="*80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*80)
    
    # 创建服务实例
    crawl_service = PurchaseHistoryService()
    aggregate_service = PurchaseHistoryAggregateService()
    
    # 同步最近365天的数据
    days = 365
    company = 'fsbbr'
    print(f"🎯 目标: 同步最近 {days} 天的采购历史明细数据")
    print(f"🏢 公司: {company}\n")
    
    try:
        # 第1步: 爬取近一年数据到明细表
        print("="*80)
        print("第1步: 爬取采购历史明细数据...")
        print("="*80)
        crawl_result = crawl_service.crawl_recent_days(days=days)
        
        print("\n" + "="*80)
        print("✅ 明细数据爬取完成!")
        print("="*80)
        print(f"📅 时间范围: {crawl_result.get('date_range', 'N/A')}")
        print(f"📋 总处理数: {crawl_result.get('total_processed', 0)}")
        print(f"💾 保存记录: {crawl_result.get('saved', 0)}")
        print(f"❌ 失败数: {crawl_result.get('failed', 0)}")
        
        # 第2步: 聚合并更新到旧表
        print("\n" + "="*80)
        print("第2步: 聚合数据并更新旧表...")
        print("="*80)
        aggregate_result = aggregate_service.aggregate_and_update(company)
        
        print("\n" + "="*80)
        print("✅ 数据聚合完成!")
        print("="*80)
        print(f"🗑️  删除旧记录: {aggregate_result.get('deleted', 0)}")
        print(f"💾 插入新记录: {aggregate_result.get('inserted', 0)}")
        
        # 最终结果
        print("\n" + "="*80)
        print("🎉 采购历史一年数据爬取全部完成!")
        print("="*80)
        print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        return {
            'crawl': crawl_result,
            'aggregate': aggregate_result
        }
        
    except Exception as e:
        print(f"\n❌ 爬取过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


if __name__ == '__main__':
    crawl_purchase_history_one_year()
