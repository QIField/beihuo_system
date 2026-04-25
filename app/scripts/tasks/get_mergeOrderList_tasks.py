# -*- coding:utf-8 -*-
# @Time    : 2026/4/25 11:01
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : get_mergeOrderList_tasks.py
# @Software: PyCharm

import os
from datetime import datetime

from app.scripts.spiders.spiders_services.get_mergeOrderList import get_mergeOrderList_service


def merge_order_list_task():
    """
    合并订单列表定时任务
    每星期二2:00执行一次
    """
    print(f"\n[定时任务] 合并订单列表自动拉取任务开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "=" * 100)
    get_mergeOrderList_service()
    print(f"\n[定时任务] 合并订单列表自动拉取任务完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "=" * 100)


def merge_order_list_register(task_manager):
    """
    注册合并订单列表定时任务

    Args:
        task_manager: 任务管理器实例
    """
    auto_start = os.environ.get('AUTO_START_MERGE_ORDER_LIST', 'true').lower() != 'false'
    if not auto_start:
        print("[合并订单列表] 已禁用")
        return

    try:
        task_manager.schedule(
            merge_order_list_task,
            'cron',
            'merge_order_list_task',
            day_of_week='tue',  # 星期二
            hour=7,
            minute=0,
            replace_existing=True
        )
        print("[合并订单列表] 定时任务已注册（每星期二7:00执行）")

    except Exception as e:
        print(f"[合并订单列表] 注册失败: {e}")

