# -*- coding:utf-8 -*-
"""
OE军备统计月度汇总定时任务

每日凌晨重算上月+当月的两张汇总表：
  ks_inquiry_oe_monthly_summary / ks_inquiry_customer_by_oe_monthly_summary
"""

from datetime import datetime

from app.services.ks_inquiry_service.oe_monthly_summary_service import refresh_recent_months


def ks_inquiry_oe_summary_task():
    """每日凌晨重算上月+当月的OE汇总数据"""
    print(f"\n[定时任务] OE军备统计月度汇总任务开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    refresh_recent_months()
    print(f"[定时任务] OE军备统计月度汇总任务结束\n")


def register_ks_inquiry_summary_tasks(task_manager):
    """
    注册OE军备统计月度汇总定时任务

    Args:
        task_manager: 任务管理器实例
    """
    import os

    auto_start = os.environ.get('AUTO_START_KS_INQUIRY_SUMMARY', 'true').lower() != 'false'
    if not auto_start:
        print("[OE汇总] 自动任务已禁用")
        return

    try:
        task_manager.schedule(
            ks_inquiry_oe_summary_task,
            'cron',
            'ks_inquiry_oe_summary',
            hour=2,
            minute=30,
            replace_existing=True
        )
        print("[OE汇总] 月度汇总定时任务已注册（每天02:30执行）")
    except Exception as e:
        print(f"[OE汇总] 注册定时任务失败: {e}")
