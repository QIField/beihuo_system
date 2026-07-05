# -*- coding:utf-8 -*-
"""
CRM 仓库库存同步定时任务
每天 8:00 和 20:00 执行
串行处理每个门店
"""

import os
from datetime import datetime

from app.services.crm_inventory.crm_warehouse_inventory_sync import (
    sync_company_inventory,
    SHOP_MAPPING,
)
from app.utils.logger_config import get_task_logger


logger = get_task_logger('crm_warehouse_inventory_sync')


def run_crm_warehouse_inventory_sync():
    """
    执行 CRM 仓库库存同步（串行）
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"[定时任务] CRM仓库库存同步开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 80}")

    for company in SHOP_MAPPING.keys():
        logger.info(f"\n[定时任务] 正在同步门店: {company}")
        sync_company_inventory(company)
        logger.info(f"[定时任务] 门店 {company} 同步完成")

    logger.info(f"\n{'=' * 80}")
    logger.info(f"[定时任务] CRM仓库库存同步完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 80}\n")


def register_crm_warehouse_inventory_sync_tasks(task_manager):
    """
    注册 CRM 仓库库存同步定时任务
    每天 8:00 和 20:00 各执行一次

    :param task_manager: 任务管理器实例（来自 app.core.task_manager）
    """
    auto_start = os.environ.get('AUTO_START_WAREHOUSE_INVENTORY_SYNC', 'true').lower() != 'false'
    if not auto_start:
        logger.info("[CRM仓库库存同步] 已禁用")
        return

    try:
        # 上午 8:00
        task_manager.schedule(
            run_crm_warehouse_inventory_sync,
            'cron',
            'crm_warehouse_inventory_sync_am',
            hour=8,
            minute=0,
            replace_existing=True
        )
        logger.info("[CRM仓库库存同步] 上午任务已注册（每天8:00）")

        # 晚上 20:00
        task_manager.schedule(
            run_crm_warehouse_inventory_sync,
            'cron',
            'crm_warehouse_inventory_sync_pm',
            hour=20,
            minute=0,
            replace_existing=True
        )
        logger.info("[CRM仓库库存同步] 晚上任务已注册（每天20:00）")

    except Exception as e:
        logger.error(f"[CRM仓库库存同步] 注册失败: {e}")
