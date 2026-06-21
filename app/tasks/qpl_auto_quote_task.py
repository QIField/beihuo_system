#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价定时任务
每2分钟运行一次，后台线程串行处理
支持多组织循环运行
"""

from threading import Thread
from datetime import datetime
from app.services.qpl_quote_service import process_and_save_quotes_for_all_companies


def qpl_auto_quote_task():
    """启动后台线程执行任务（支持多组织循环）

    运行时段：每天 08:00 - 20:00
    晚上 20:00 至次日 08:00 不执行（完全静默，不输出日志）
    """
    now_hour = datetime.now().hour
    if now_hour < 8 or now_hour >= 20:
        return
    thread = Thread(target=process_and_save_quotes_for_all_companies, daemon=True)
    thread.start()


def register_qpl_auto_quote_tasks(task_manager):
    """
    注册汽配龙自动报价定时任务
    APS调度，后台线程运行
    """
    task_manager.schedule(
        qpl_auto_quote_task,
        'interval',
        'qpl_auto_quote',
        minutes=2,
        next_run_time=datetime.now(),
        replace_existing=True
    )
    print("[汽配龙自动报价] 定时任务已注册（每2分钟执行，支持多组织循环）")