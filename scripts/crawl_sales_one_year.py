"""
销量数据明细爬取脚本 - 最近一年
调用 SalesHistorySyncService 模块，爬取最近一年的销量数据

使用方法:
    python scripts/crawl_sales_one_year.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime
from app.services.sales_history_service.data_sync_service import SalesHistorySyncService


def crawl_sales_one_year():
    """
    爬取最近一年的销量明细数据
    """
    print("\n" + "="*80)
    print("📊 销量数据明细爬取 - 最近一年")
    print("="*80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*80)
    
    # 创建服务实例
    service = SalesHistorySyncService()
    
    # 同步最近365天的数据
    days = 365
    print(f"🎯 目标: 同步最近 {days} 天的销量明细数据\n")
    
    try:
        result = service.sync_recent_days(days=days)
        
        print("\n" + "="*80)
        print("✅ 爬取完成!")
        print("="*80)
        print(f"📈 总页数: {result.get('total_pages', 0)}")
        print(f"📋 总条目: {result.get('total_items', 0)}")
        print(f"💾 保存记录: {result.get('saved', 0)}")
        print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        return result
        
    except Exception as e:
        print(f"\n❌ 爬取过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


if __name__ == '__main__':
    crawl_sales_one_year()
