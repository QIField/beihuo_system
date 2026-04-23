from app.services.procurement_service.purchase_history_service import PurchaseHistoryService
from app.services.procurement_service.purchase_history_aggregate_service import PurchaseHistoryAggregateService
from app.services.procurement_service.purchase_sync_service import PurchaseSyncService


def run(company='fsbbr', days=5):
    """
    主入口：爬取采购历史数据、聚合更新、同步到比价表

    Args:
        company: 公司代码
        days: 爬取近N天数据

    Returns:
        dict: 包含爬取、聚合和同步结果的字典
    """
    print(f"[PurchaseHistoryMain] 开始执行采购历史数据同步, company={company}, days={days}")

    # 第1步: 爬取近N天数据到明细表
    print(f"[PurchaseHistoryMain] 第1步: 爬取近{days}天数据...")
    crawl_result = PurchaseHistoryService().crawl_recent_days(days)
    print(f"[PurchaseHistoryMain] 爬取完成: {crawl_result}")

    # 第2步: 聚合三个表数据到 procurement_history
    print(f"[PurchaseHistoryMain] 第2步: 聚合数据...")
    aggregate_result = PurchaseHistoryAggregateService().aggregate_and_update(
        sources=['procurement_detail', 'price_inquiry', 'price_inquiry_direct'],
        company=company
    )
    print(f"[PurchaseHistoryMain] 聚合完成: {aggregate_result}")

    # 第3步: 同步到比价汇总表
    print(f"[PurchaseHistoryMain] 第3步: 同步到比价表...")
    sync_result = PurchaseSyncService().sync_to_compare_summary(company)
    print(f"[PurchaseHistoryMain] 同步完成: {sync_result}")

    result = {
        'crawl': crawl_result,
        'aggregate': aggregate_result,
        'sync': sync_result
    }
    print(f"[PurchaseHistoryMain] 执行完成: {result}")
    return result


if __name__ == '__main__':
    run()
