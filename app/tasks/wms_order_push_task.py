# -*- coding:utf-8 -*-
"""
WMS 订单推送定时任务
每天 07:00、14:00、15:00、16:00、17:00、18:00、19:00 各执行一次
"""

import os
from datetime import datetime

from app.services.wms_order_push_service.wms_order_push_service import run_wms_order_push
from app.utils.logger_config import get_task_logger


logger = get_task_logger('wms_order_push')


# 定时任务执行时间点（小时，分钟）
SCHEDULE_TIMES = [
    (7, 0),
    (14, 0),
    (15, 0),
    (16, 0),
    (17, 0),
    (18, 0),
    (19, 0),
]


def run_wms_order_push_task():
    """
    执行 WMS 订单推送定时任务
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"[定时任务] WMS订单推送开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 80}")

    try:
        result = run_wms_order_push('fsbbr', logger=logger)
        logger.info(f"[定时任务] WMS订单推送完成：{result}")
    except Exception as e:
        logger.exception(f"[定时任务] WMS订单推送失败: {e}")
        raise

    logger.info(f"\n{'=' * 80}")
    logger.info(f"[定时任务] WMS订单推送结束 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 80}\n")


def register_wms_order_push_tasks(task_manager):
    """
    注册 WMS 订单推送定时任务

    每天 07:00、14:00-19:00 每小时执行一次

    :param task_manager: 任务管理器实例（来自 app.core.task_manager）
    """
    auto_start = os.environ.get('AUTO_START_WMS_ORDER_PUSH', 'true').lower() != 'false'
    if not auto_start:
        logger.info("[WMS订单推送] 已禁用")
        return

    try:
        for hour, minute in SCHEDULE_TIMES:
            job_id = f'wms_order_push_task_{hour:02d}{minute:02d}'
            task_manager.schedule(
                run_wms_order_push_task,
                'cron',
                job_id,
                hour=hour,
                minute=minute,
                replace_existing=True
            )
            logger.info(f"[WMS订单推送] 定时任务已注册（每天{hour:02d}:{minute:02d}）")

    except Exception as e:
        logger.error(f"[WMS订单推送] 注册失败: {e}")
