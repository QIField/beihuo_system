#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙虚拟库存导入定时任务
生成 Excel 后上传到汽配龙 importProduct 接口
"""

import logging

from app.services.qpl_virtual_inventory.config import CRON_HOUR, CRON_MINUTE
from app.services.qpl_virtual_inventory.import_service import run_import

logger = logging.getLogger('qpl_virtual_inventory')
TASK_ID = 'qpl_virtual_inventory_import'


def qpl_virtual_inventory_import_task():
    """
    定时任务入口：生成并上传虚拟库存导入文件
    """
    try:
        result = run_import()
        if result['success'] and result['rows'] > 0:
            logger.info(
                f"[虚拟库存定时任务] 执行成功，导入 {result['rows']} 行"
            )
        elif not result['success']:
            logger.error(
                f"[虚拟库存定时任务] 执行失败: {result['message']}"
            )
    except Exception as e:
        logger.error(f"[虚拟库存定时任务] 执行异常: {e}", exc_info=True)


def register_qpl_virtual_inventory_import_tasks(task_manager):
    """
    注册汽配龙虚拟库存导入定时任务

    Args:
        task_manager: 任务管理器实例
    """
    task_manager.schedule(
        qpl_virtual_inventory_import_task,
        'cron',
        TASK_ID,
        hour=CRON_HOUR,
        minute=CRON_MINUTE,
        replace_existing=True
    )
    logger.info(
        f"[虚拟库存定时任务] 已注册（每天 {CRON_HOUR:02d}:{CRON_MINUTE:02d}）"
    )
