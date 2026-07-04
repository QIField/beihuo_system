#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价定时任务
使用 APScheduler interval 触发器，每 2 分钟触发一次
运行时段：每天 08:00 - 20:00
"""

import logging
from datetime import datetime

from app.services.qpl_quote_service import process_and_save_quotes_for_all_companies


logger = logging.getLogger(__name__)

TASK_ID = 'qpl_auto_quote'


def qpl_auto_quote_task():
    """同步执行任务（支持多组织循环）

    运行时段：每天 08:00 - 20:00
    晚上 20:00 至次日 08:00 不执行（完全静默，不输出日志）
    """
    now_hour = datetime.now().hour
    if not (8 <= now_hour < 20):
        return

    try:
        process_and_save_quotes_for_all_companies()
    except Exception as e:
        logger.error(f"[汽配龙自动报价] 执行异常: {e}", exc_info=True)


def register_qpl_auto_quote_tasks(task_manager):
    """
    注册汽配龙自动报价定时任务
    每 2 分钟触发一次，首次立即执行
    """
    task_manager.schedule(
        qpl_auto_quote_task,
        'interval',
        TASK_ID,
        minutes=2,
        next_run_time=datetime.now(),
        replace_existing=True
    )
    logger.info("[汽配龙自动报价] 定时任务已注册（每 2 分钟，08:00-20:00 运行）")
