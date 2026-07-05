#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙下单状态同步定时任务
每天 11:00 执行，同步前天和大前天（today-2、today-3）的状态为3的询价单。
"""

from datetime import datetime, timedelta

from app.utils.qpl_auto_bill.order_status_sync import sync_order_status
from app.utils.qpl_auto_bill.qpl_config import get_supported_companies, logger

TASK_ID = 'qpl_order_status_sync'


def run_qpl_order_status_sync():
    """
    执行汽配龙下单状态同步。
    查询 today-3 和 today-2 两天的状态=3询价单，按 item 更新 order_status。
    """
    today = datetime.now().date()
    target_dates = [
        (today - timedelta(days=3)).strftime('%Y-%m-%d'),
        (today - timedelta(days=2)).strftime('%Y-%m-%d'),
    ]

    companies = get_supported_companies()
    summary = []

    for company in companies:
        for target_date in target_dates:
            try:
                result = sync_order_status(target_date, company=company)
                summary.append(result)
            except Exception as e:
                logger.error(
                    f"[汽配龙下单状态同步] {target_date} {company} 执行异常: {e}",
                    exc_info=True
                )

    updated_total = sum(item['updated'] for item in summary)
    logger.info(
        f"[汽配龙下单状态同步] 本次共更新 {updated_total} 条，"
        f"日期范围 {target_dates[0]} ~ {target_dates[1]}"
    )


def register_qpl_order_status_sync_tasks(task_manager):
    """
    注册汽配龙下单状态同步定时任务

    Args:
        task_manager: 任务管理器实例
    """
    task_manager.schedule(
        run_qpl_order_status_sync,
        'cron',
        TASK_ID,
        hour=11,
        minute=0,
        replace_existing=True
    )
    logger.info("[汽配龙下单状态同步] 定时任务已注册（每天 11:00）")
