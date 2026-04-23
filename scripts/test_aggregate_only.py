"""
测试聚合任务脚本
仅用于测试采购历史聚合功能，不执行爬取
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime
from app.services.procurement_service.purchase_history_aggregate_service import PurchaseHistoryAggregateService
from app.services.procurement_service.purchase_sync_service import PurchaseSyncService
from app.core.session_init import init_session_manager


def test_aggregate():
    """测试聚合任务"""
    print("=" * 80)
    print("🧪 测试采购历史聚合任务")
    print("=" * 80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 初始化CRM Session（虽然聚合不需要，但同步服务可能需要）
    print("[1/3] 初始化环境...")
    try:
        init_session_manager()
        print("✅ 环境初始化完成\n")
    except Exception as e:
        print(f"⚠️ 环境初始化警告: {e}")
        print("继续执行...\n")

    company = 'fsbbr'

    # 第1步：聚合三个表数据
    print("[2/3] 执行聚合任务...")
    print(f"目标公司: {company}")
    print("数据源: procurement_detail, price_inquiry, price_inquiry_direct")
    print("-" * 80)

    try:
        aggregate_service = PurchaseHistoryAggregateService()
        aggregate_result = aggregate_service.aggregate_and_update(
            sources=['procurement_detail', 'price_inquiry', 'price_inquiry_direct'],
            company=company
        )

        print("\n" + "=" * 80)
        print("✅ 聚合任务完成!")
        print(f"删除旧记录: {aggregate_result['deleted']} 条")
        print(f"插入新记录: {aggregate_result['inserted']} 条")
        print("=" * 80)

    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ 聚合任务失败!")
        print(f"错误信息: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        sys.exit(1)

    # 第2步：同步到比价表
    print("\n[3/3] 执行同步任务...")
    print("-" * 80)

    try:
        sync_service = PurchaseSyncService()
        sync_result = sync_service.sync_to_compare_summary(company)

        print("\n" + "=" * 80)
        print("✅ 同步任务完成!")
        print(f"同步记录数: {sync_result['saved']}")
        print(f"重复/失败: {sync_result['duplicate']}")
        print("=" * 80)

    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ 同步任务失败!")
        print(f"错误信息: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        sys.exit(1)

    # 最终总结
    print("\n" + "=" * 80)
    print("🎉 所有测试任务完成!")
    print("=" * 80)
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"聚合结果: 删除 {aggregate_result['deleted']} 条, 插入 {aggregate_result['inserted']} 条")
    print(f"同步结果: 成功 {sync_result['saved']} 条, 失败 {sync_result['duplicate']} 条")
    print("=" * 80)


if __name__ == '__main__':
    test_aggregate()
