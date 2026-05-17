"""
定时任务模块
包含系统定时任务的定义和执行逻辑
"""

from .daily_crawl_pipeline import execute_daily_pipeline
from .beihuo_tasks import register_beihuo_tasks
from .data_gzbbr_token_task import data_gzbbr_token_register
from .crm_data_sync_task import register_crm_data_sync_tasks
from app.services.ks_merchant_service.task_registration import register_ks_merchant_tasks


def register_all_tasks(task_manager):
    """
    注册所有定时任务（统一入口）
    
    Args:
        task_manager: 任务管理器实例（来自 app.core.task_manager）
    """
    # 1. 注册备货数据定时任务
    register_beihuo_tasks(task_manager)
    
    # 2. 注册 B2B Token 刷新定时任务
    data_gzbbr_token_register(task_manager)
    
    # 3. 注册开思商家数据同步定时任务
    register_ks_merchant_tasks()
    
    # 4. 注册CRM数据同步定时任务（每月1日 00:00）
    register_crm_data_sync_tasks(task_manager)
    
    # 5. 注册安全库存定时任务（每小时，仅fsbbr）
    register_safety_stock_tasks(task_manager)


__all__ = ['execute_daily_pipeline', 'register_all_tasks']
