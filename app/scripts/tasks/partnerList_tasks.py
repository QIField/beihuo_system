# -*- coding:utf-8 -*-
# @Time    : 2026/4/25 11:01
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : partnerList_tasks.py
# @Software: PyCharm

import os
from datetime import datetime

from app.scripts.spiders.spiders_services.partnerList import partnerList_service


def partner_list_task():
    """
    合作伙伴列表定时任务
    每星期二2:00执行一次
    """
    print(f"\n[定时任务] 合作伙伴列表自动拉取任务开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "=" * 100)
    partnerList_service()
    print(f"\n[定时任务] 合作伙伴列表自动拉取任务完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "=" * 100)


def partner_list_register(task_manager):
    """
    注册合作伙伴列表定时任务

    Args:
        task_manager: 任务管理器实例
    """
    auto_start = os.environ.get('AUTO_START_PARTNER_LIST', 'true').lower() != 'false'
    if not auto_start:
        print("[合作伙伴列表] 已禁用")
        return

    # mon 周一
    # tue 周二
    # wed周三
    # thu 周四
    # fri 周五
    # sat 周六
    # sun 周日




    try:
        task_manager.schedule(
            partner_list_task,
            'cron',
            'partner_list_task',
            day_of_week='tue',  # 星期二
            hour=7,
            minute=00,
            replace_existing=True
        )
        print("[合作伙伴列表] 定时任务已注册（每星期二7:00执行）")

    except Exception as e:
        print(f"[合作伙伴列表] 注册失败: {e}")

