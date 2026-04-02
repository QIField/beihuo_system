from app.services.procurement_service.purchase_history_service import PurchaseHistoryService
from app.services.procurement_service.purchase_history_aggregate_service import PurchaseHistoryAggregateService


def run(company='fsbbr', days=5):
    """
    主入口：爬取采购历史数据并聚合更新

    Args:
        company: 公司代码
        days: 爬取近N天数据

    Returns:
        dict: 包含爬取和聚合结果的字典
    """
    print(f"[PurchaseHistoryMain] 开始执行采购历史数据同步, company={company}, days={days}")

    # 第1步: 爬取近N天数据到新表
    print(f"[PurchaseHistoryMain] 第1步: 爬取近{days}天数据...")
    crawl_result = PurchaseHistoryService().crawl_recent_days(days)
    print(f"[PurchaseHistoryMain] 爬取完成: {crawl_result}")

    # 第2步: 聚合并更新旧表
    print(f"[PurchaseHistoryMain] 第2步: 聚合数据并更新旧表...")
    aggregate_result = PurchaseHistoryAggregateService().aggregate_and_update(company)
    print(f"[PurchaseHistoryMain] 聚合完成: {aggregate_result}")

    result = {
        'crawl': crawl_result,
        'aggregate': aggregate_result
    }
    print(f"[PurchaseHistoryMain] 执行完成: {result}")
    return result


if __name__ == '__main__':
    run()
