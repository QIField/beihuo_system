# -*- coding:utf-8 -*-
"""
WMS 库存操作自动推送定时任务

运行时间从 beihuo_system_config 表读取（key: wms_inventory_operation_schedule_times），
页面 /web/wms_inventory_operation/ 可配置，默认每天 10:00、20:00 各执行一次。

流程：
1. 采购入库自动推送（type=5, status=0/1）-> addPurchaseToInventory
2. 采购移除自动推送（type=3, status=0/1）-> removePurchaseFromInventory
"""

import os
from datetime import datetime

from app.services.wms_inventory_operation_service import run_wms_inventory_operation
from app.utils.logger_config import get_task_logger


logger = get_task_logger('wms_inventory_operation')

# job_id 前缀
JOB_ID_PREFIX = 'wms_inventory_operation_task_'


def run_wms_inventory_operation_task():
    """
    执行 WMS 库存操作自动推送定时任务
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"[定时任务] WMS库存操作自动推送开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 80}")

    try:
        result = run_wms_inventory_operation('fsbbr', logger=logger)
        logger.info(f"[定时任务] WMS库存操作自动推送完成：{result}")
    except Exception as e:
        logger.exception(f"[定时任务] WMS库存操作自动推送失败: {e}")
        raise

    logger.info(f"\n{'=' * 80}")
    logger.info(f"[定时任务] WMS库存操作自动推送结束 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 80}\n")


def register_wms_inventory_operation_jobs(task_manager):
    """
    按当前配置的运行时间注册 job（不做启用开关检查，可被外部复用）
    """
    from app.services.wms_inventory_operation_service.task_control_service import get_schedule_times

    for time_text in get_schedule_times():
        hour, minute = time_text.split(":")
        job_id = f'{JOB_ID_PREFIX}{int(hour):02d}{int(minute):02d}'
        task_manager.schedule(
            run_wms_inventory_operation_task,
            'cron',
            job_id,
            hour=int(hour),
            minute=int(minute),
            replace_existing=True,
        )
        logger.info(f"[WMS库存操作自动推送] 定时任务已注册（每天{int(hour):02d}:{int(minute):02d}）")


def register_wms_inventory_operation_tasks(task_manager):
    """
    注册 WMS 库存操作自动推送定时任务

    运行时间从配置表读取，页面可动态修改
    """
    auto_start = os.environ.get('AUTO_START_WMS_INVENTORY_OPERATION', 'true').lower() != 'false'
    if not auto_start:
        logger.info("[WMS库存操作自动推送] 已禁用")
        return

    try:
        register_wms_inventory_operation_jobs(task_manager)
    except Exception as e:
        logger.error(f"[WMS库存操作自动推送] 注册失败: {e}")
