# -*- coding:utf-8 -*-
"""
微信日报报价明细数据定时任务

每日凌晨 1:00 执行：
  从 weixin_decoding_result 表刷新最近 3 天（含昨天）数据到 wechat_daily_quote_detail 表

注册方式：
    from app.scripts.tasks.wx_task import wx_daily_quote_detail_register
    wx_daily_quote_detail_register(task_manager)
"""

import time
import traceback
from datetime import datetime, timedelta

def _wx_daily_quote_detail_pipeline() -> None:
    """
    微信日报报价明细每日刷新流程

    调用 weixin_decoding_result_clear.fetch_data_and_save_to_database 处理最近 3 天数据。
    """
    total_start = time.time()
    print("[微信日报报价明细每日流程] ====== 开始执行 ======")

    try:
        from app.services.report_wx_quote_data_services.weixin_decoding_result_clear import (
            fetch_data_and_save_to_database,
        )

        start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        print(f"[Step 1/1] 刷新日期范围: {start_date} 至 {end_date}")
        fetch_data_and_save_to_database(start_date=start_date, end_date=end_date)
        print("[Step 1/1] 完成")
    except Exception as e:
        print(f"[Step 1/1] 失败: {e}")
        traceback.print_exc()

    print(
        f"[微信日报报价明细每日流程] ====== 完成, 耗时 {round(time.time() - total_start, 2)}s ======"
    )



def wx_daily_quote_detail_register(task_manager) -> None:
    """注册微信日报报价明细每日刷新定时任务（每天凌晨 1:00 执行）"""
    try:
        task_manager.schedule(
            _wx_daily_quote_detail_pipeline,
            'cron',
            'wx_daily_quote_detail_pipeline',
            hour=1,
            minute=0,
            replace_existing=True,
        )
        print("[微信日报报价明细每日流程] 定时任务已注册（每天凌晨 1:00 执行）")
    except Exception as e:
        print(f"[微信日报报价明细每日流程] 注册失败: {e}")
