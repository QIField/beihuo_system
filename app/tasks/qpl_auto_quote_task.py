#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价定时任务
每5分钟运行一次，后台线程串行处理
"""

from threading import Thread
from datetime import datetime
from app.utils.qpl_auto_bill.auto_submit_part_quote import main as auto_quote_main


def qpl_auto_quote_task():
    """启动后台线程执行任务"""
    thread = Thread(target=auto_quote_main, daemon=True)
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
        minutes=5,
        next_run_time=datetime.now(),
        replace_existing=True
    )
    print("[汽配龙自动报价] 定时任务已注册（每5分钟执行）")
