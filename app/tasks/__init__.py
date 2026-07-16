"""
定时任务模块
包含系统定时任务的定义和执行逻辑
"""

from .daily_crawl_pipeline import execute_daily_pipeline
from .beihuo_tasks import register_beihuo_tasks
from .openapi_gzbbr_token_task import openapi_gzbbr_token_register
from .crm_data_sync_task import register_crm_data_sync_tasks
from .safety_stock_tasks import register_safety_stock_tasks
from .qpl_auto_quote_task import register_qpl_auto_quote_tasks
from .qpl_order_status_sync_task import register_qpl_order_status_sync_tasks
from .crm_warehouse_inventory_sync_task import register_crm_warehouse_inventory_sync_tasks
from .vin_vehicle_info_sync_task import register_vin_vehicle_info_sync_tasks
from .wms_order_push_task import register_wms_order_push_tasks
from .wms_return_items_detail_task import register_wms_return_items_detail_tasks
from .crm_price_sync_task import register_crm_price_sync_tasks
from .mercedes_replace_number_sync_task import register_mercedes_replace_number_sync_tasks
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
    openapi_gzbbr_token_register(task_manager)
    
    # 3. 注册开思商家数据同步定时任务
    register_ks_merchant_tasks()
    
    # 4. 注册CRM数据同步定时任务（每月1日 00:00）
    register_crm_data_sync_tasks(task_manager)
    
    # 5. 注册安全库存定时任务（每小时，仅fsbbr）
    register_safety_stock_tasks(task_manager)
    
    # 6. 注册汽配龙自动报价定时任务（每2分钟，08:00-20:00）
    register_qpl_auto_quote_tasks(task_manager)
    
    # 7. 注册汽配龙下单状态同步定时任务（每天11:00）
    register_qpl_order_status_sync_tasks(task_manager)
    
    # 8. 注册CRM仓库库存同步定时任务（每天8:00和20:00）
    register_crm_warehouse_inventory_sync_tasks(task_manager)

    # 9. 注册VIN车辆信息补全定时任务（每天9:00，最多50条）
    register_vin_vehicle_info_sync_tasks(task_manager)

    # 10. 注册WMS订单推送定时任务（每天07:00、14:00-19:00）
    register_wms_order_push_tasks(task_manager)

    # 11. 注册WMS采购入库单明细同步定时任务（按指定字段，每天06:00）
    register_wms_return_items_detail_tasks(task_manager)

    # 12. 注册CRM产品价格同步定时任务（每天03:00）
    register_crm_price_sync_tasks(task_manager)

    # 13. 注册奔驰报价OE替换号自动同步定时任务（每天04:00）
    register_mercedes_replace_number_sync_tasks(task_manager)


__all__ = ['execute_daily_pipeline', 'register_all_tasks']
