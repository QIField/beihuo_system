# -*- coding:utf-8 -*-
# @Time    : 2026/4/10 13:40
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_get_status_orders_tasks.py
# @Software: PyCharm

import os
from datetime import datetime

from app.scripts.spiders.spiders_services.wms_get_status_orders import get_status_orders_complete_by_page


def two_minutes_task():
    """
    WMS状态订单任务
    """
    print(f"\n[定时任务] WMS已完成订单自动拉取任务开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}","="*100)
    get_status_orders_complete_by_page(2)
    print(f"\n[定时任务] WMS已完成订单自动拉取任务完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}","="*100)



def every_day_task():
    """
    WMS状态订单任务
    """
    print(f"\n[定时任务] WMS已完成订单自动拉取任务开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}","="*100)
    get_status_orders_complete_by_page(30)
    print(f"\n[定时任务] WMS已完成订单自动拉取任务完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}","="*100)




def two_minutes_register(task_manager):
    """
    注册WMS状态订单定时任务

    Args:
        task_manager: 任务管理器实例
    """
   
    # auto_start = os.environ.get('AUTO_START_WMS_STATUS_ORDERS', 'true').lower() != 'false'
    auto_start = os.environ.get('AUTO_START_WMS_STATUS_ORDERS_MINUTE', 'true').lower() != 'false'
    if not auto_start:
        print("[WMS状态订单] 已禁用")
        return

    try:
        task_manager.schedule(
            two_minutes_task,
            'interval',
            'wms_status_orders_task',
            minutes=1,
            replace_existing=True
        )
        print("[WMS状态订单] 定时任务已注册（每1分钟执行）")

    except Exception as e:
        print(f"[WMS状态订单] 注册失败: {e}")



def every_day_register(task_manager):
    """
    注册WMS状态订单定时任务

    Args:
        task_manager: 任务管理器实例
    """
    # auto_start = os.environ.get('AUTO_START_WMS_STATUS_ORDERS', 'true').lower() != 'false'
    auto_start = os.environ.get('AUTO_START_WMS_STATUS_ORDERS_DAILY', 'true').lower() != 'false'
    if not auto_start:
        print("[WMS状态订单] 已禁用")
        return

    try:
        task_manager.schedule(
            every_day_task,
            'cron',
            'wms_status_orders_task',
            hour=23,
            minute=30,
            replace_existing=True
        )
        print("[WMS状态订单] 定时任务已注册（每晚23:30执行）")

    except Exception as e:
        print(f"[WMS状态订单] 注册失败: {e}")




