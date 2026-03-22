"""
定时清理任务和销量同步任务
任务已整合到统一的任务管理器中

原独立调度器已移除，所有任务通过 task_manager 调度
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def sales_history_sync_task():
    """
    CRM销量明细同步任务
    每天凌晨2:35执行（在CRM全量爬取完成后）
    串行执行开思询价次数统计服务
    """
    from app.services.sales_history_service import SalesHistorySyncService
    from app.services.quote_count_service import QuoteCountSyncService

    try:
        # 1. 执行销量服务
        service = SalesHistorySyncService()
        result = service.sync_recent_days(days=30)

        # 2. 销量服务完成后，串行执行开思询价次数统计
        quote_service = QuoteCountSyncService()
        quote_result = quote_service.sync_recent_two_months()

    except:
        pass


def register_cleanup_tasks(task_manager):
    """
    注册清理任务到统一的任务管理器
    
    Args:
        task_manager: LightweightTaskManager 实例
    """
    pass


# 兼容旧接口，但不再创建独立调度器
def start_scheduler():
    """【已废弃】原独立调度器启动函数"""
    pass


def stop_scheduler():
    """【已废弃】原独立调度器停止函数"""
    pass
