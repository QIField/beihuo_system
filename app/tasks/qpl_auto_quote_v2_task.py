#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价定时任务（V2 · PAGE_QUOTE 全链路）
使用 APScheduler interval 触发器，每 2 分钟触发一次
运行时段：每天 08:00 - 20:00

注意：新版任务与旧版 app/tasks/qpl_auto_quote_task.py 互斥——
切换时在任务注册处二选一，避免新旧流程同时处理同一批订单。
"""

from datetime import datetime

from app.services.qpl_auto_quote.runner import run_all_companies
from app.utils.qpl_auto_bill.qpl_config import logger
from app.utils.round_lock import RoundLock

TASK_ID = 'qpl_auto_quote_v2'

# 轮次互斥锁：调度器每 2 分钟触发一次，但一轮实际可能超过 2 分钟；
# 必须在任务入口自行加锁，防止多轮并行重复处理同一批订单
_round_lock = RoundLock('qpl_auto_quote_v2_round')


def qpl_auto_quote_v2_task():
    """同步执行任务（支持多组织循环）

    运行时段：每天 08:00 - 20:00
    晚上 20:00 至次日 08:00 不执行（完全静默，不输出日志）
    上一轮未结束时本轮直接跳过（非阻塞锁，绝不排队等待）
    """
    now_hour = datetime.now().hour
    if not (8 <= now_hour < 20):
        return

    if not _round_lock.acquire():
        logger.info("[汽配龙自动报价V2] 上一轮仍在执行，本轮跳过")
        return

    try:
        run_all_companies()
    except Exception as e:
        logger.error(f"[汽配龙自动报价V2] 执行异常: {e}", exc_info=True)
    finally:
        _round_lock.release()


def register_qpl_auto_quote_v2_tasks(task_manager):
    """
    注册汽配龙自动报价 V2 定时任务
    每 2 分钟触发一次，首次立即执行
    """
    task_manager.schedule(
        qpl_auto_quote_v2_task,
        'interval',
        TASK_ID,
        minutes=2,
        next_run_time=datetime.now(),
        replace_existing=True
    )
    logger.info("[汽配龙自动报价V2] 定时任务已注册（每 2 分钟，08:00-20:00 运行）")
