"""
采购历史数据聚合脚本
用于从明细表 crmapp_procurement_history_detail 聚合数据到旧表 crmapp_procurement_history

使用方法:
    python scripts/aggregate_purchase_history.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime
from app.services.procurement_service.purchase_history_aggregate_service import PurchaseHistoryAggregateService
from app.core.session_init import init_session_manager


def aggregate_purchase_history():
    """
    执行采购历史数据聚合
    """
    print("\n" + "="*80)
    print("📊 采购历史数据聚合")
    print("="*80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*80)

    # 初始化 SessionManager
    print("🔑 初始化 CRM Session...")
    init_session_manager()
    print("✅ CRM Session 初始化完成\n")

    # 创建聚合服务实例
    aggregate_service = PurchaseHistoryAggregateService()
    company = 'fsbbr'

    try:
        # 执行聚合
        print(f"🎯 目标: 聚合公司 {company} 的采购历史数据")
        print("="*80)
        aggregate_result = aggregate_service.aggregate_and_update(company)

        # 结果输出
        print("\n" + "="*80)
        print("✅ 数据聚合完成!")
        print("="*80)
        print(f"🗑️  删除旧记录: {aggregate_result.get('deleted', 0)}")
        print(f"💾 插入新记录: {aggregate_result.get('inserted', 0)}")

        print("\n" + "="*80)
        print("🎉 采购历史数据聚合全部完成!")
        print("="*80)
        print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        return aggregate_result

    except Exception as e:
        print(f"\n❌ 聚合过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


if __name__ == '__main__':
    aggregate_purchase_history()
