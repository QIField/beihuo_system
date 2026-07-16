# -*- coding: utf-8 -*-
"""
CRM 产品价格同步定时任务
每天凌晨 03:00 执行
"""

import os
from datetime import datetime

from app.services.crm_price_sync_service import sync_crm_prices
from app.utils.logger_config import get_task_logger


logger = get_task_logger('crm_price_sync')


def run_crm_price_sync():
    """执行 CRM 产品价格同步定时任务。"""
    logger.info("\n" + "=" * 80)
    logger.info(f"[定时任务] CRM产品价格同步开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    sync_crm_prices()

    logger.info("\n" + "=" * 80)
    logger.info(f"[定时任务] CRM产品价格同步完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80 + "\n")


def register_crm_price_sync_tasks(task_manager):
    """
    注册 CRM 产品价格同步定时任务

    :param task_manager: 任务管理器实例（来自 app.core.task_manager）
    """
    auto_start = os.environ.get('AUTO_START_CRM_PRICE_SYNC', 'true').lower() != 'false'
    if not auto_start:
        logger.info("[CRM产品价格同步] 已禁用")
        return

    try:
        task_manager.schedule(
            run_crm_price_sync,
            'cron',
            'crm_price_sync',
            hour=3,
            minute=0,
            replace_existing=True
        )
        logger.info("[CRM产品价格同步] 定时任务已注册（每天03:00）")
    except Exception as e:
        logger.error(f"[CRM产品价格同步] 定时任务注册失败: {e}")
