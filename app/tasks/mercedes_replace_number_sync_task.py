# -*- coding: utf-8 -*-
"""
奔驰报价 OE 替换号自动同步定时任务
每天凌晨 04:00 执行
"""

import os
from datetime import date, timedelta

from app.services.mercedes_replace_number_service import run_mercedes_replace_number_sync
from app.utils.logger_config import get_task_logger
from app.utils.mercedes_replace_number.config import (
    DATE_OFFSET_DAYS,
    SCHEDULE_HOUR,
    SCHEDULE_MINUTE,
    TASK_NAME,
)


logger = get_task_logger(TASK_NAME)


def run_mercedes_replace_number_sync_task():
    """定时任务执行入口。"""
    logger.info(f"[定时任务] {TASK_NAME} 开始")
    try:
        yesterday = date.today() - timedelta(days=DATE_OFFSET_DAYS)
        run_mercedes_replace_number_sync(target_date=yesterday)
    except Exception:
        logger.exception(f"[定时任务] {TASK_NAME} 失败")
        raise
    logger.info(f"[定时任务] {TASK_NAME} 完成")


def register_mercedes_replace_number_sync_tasks(task_manager):
    """
    注册奔驰报价 OE 替换号自动同步定时任务。

    Args:
        task_manager: app.core.task_manager 实例
    """
    auto_start = os.environ.get('AUTO_START_QUOTE_REPLACE_NUMBER_SYNC', 'true').lower() != 'false'
    if not auto_start:
        logger.info(f"[{TASK_NAME}] 已禁用")
        return

    try:
        task_manager.schedule(
            run_mercedes_replace_number_sync_task,
            'cron',
            TASK_NAME,
            hour=SCHEDULE_HOUR,
            minute=SCHEDULE_MINUTE,
            replace_existing=True,
        )
        logger.info(
            f"[{TASK_NAME}] 定时任务已注册（每天{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}）"
        )
    except Exception as e:
        logger.error(f"[{TASK_NAME}] 定时任务注册失败: {e}")
