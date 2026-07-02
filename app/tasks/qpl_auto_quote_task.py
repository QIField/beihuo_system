#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价定时任务
任务同步执行，完成后通过 remove + add 安排 2 分钟后再次触发
支持多组织循环运行
"""

from datetime import datetime, timedelta
from app.services.qpl_quote_service import process_and_save_quotes_for_all_companies


TASK_ID = 'qpl_auto_quote'


def qpl_auto_quote_task():
    """同步执行任务（支持多组织循环）

    运行时段：每天 08:00 - 20:00
    晚上 20:00 至次日 08:00 不执行（完全静默，不输出日志）
    """
    now_hour = datetime.now().hour
    if 8 <= now_hour < 20:
        process_and_save_quotes_for_all_companies()

    _schedule_next_run()


def _schedule_next_run():
    """安排 2 分钟后再次执行（删除旧 job 后重新添加）。"""
    from app.core.task_manager import task_manager
    next_run_time = datetime.now() + timedelta(minutes=2)

    try:
        task_manager._scheduler.remove_job(TASK_ID)
    except Exception:
        pass

    task_manager._scheduler.add_job(
        func=qpl_auto_quote_task,
        trigger='date',
        id=TASK_ID,
        name=qpl_auto_quote_task.__name__,
        run_date=next_run_time,
        replace_existing=True
    )
    print(f"[汽配龙自动报价] 已安排下次执行时间: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")


def register_qpl_auto_quote_tasks(task_manager):
    """
    注册汽配龙自动报价定时任务
    首次立即执行，之后由任务自身重新调度
    """
    try:
        task_manager._scheduler.remove_job(TASK_ID)
    except Exception:
        pass

    task_manager._scheduler.add_job(
        func=qpl_auto_quote_task,
        trigger='date',
        id=TASK_ID,
        name=qpl_auto_quote_task.__name__,
        run_date=datetime.now(),
        replace_existing=True
    )
    print("[汽配龙自动报价] 定时任务已注册（同步执行，完成后2分钟再次触发）")
