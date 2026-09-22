# -*- coding:utf-8 -*-
"""
商机体系定时任务

每日凌晨 2:00 执行：
  Step 1: 爬取 OE 搜索日志（前 3 天，含昨天）
  Step 2: 计算并刷新 niche_opportunity 商机表

注册方式：
    from app.scripts.tasks.niche_task import niche_daily_register
    niche_daily_register(task_manager)
"""

import time
from datetime import datetime, timedelta

from app.utils.logger_config import get_task_logger

logger = get_task_logger('niche')


def _niche_daily_pipeline() -> None:
    """
    商机体系每日全流程

    先爬取前 3 天 OE 搜索日志，再全量刷新商机评分。
    """
    total_start = time.time()
    logger.info("[商机每日流程] ====== 开始执行 ======")

    # Step 1: 爬取 OE 搜索日志（最近 3 天，含昨天）
    logger.info("[Step 1/2] 爬取 OE 搜索日志")
    try:
        from app.services.niche_services.oe_search_log import crawl_and_store_oe_search_log

        start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        r1 = crawl_and_store_oe_search_log(
            store='fs',
            start_date=start_date,
            end_date=end_date,
            clear_before_write=True,
        )
        logger.info("[Step 1/2] 完成: 入库 %d 条", r1)
    except Exception as e:
        logger.error("[Step 1/2] 失败: %s", e, exc_info=True)

    # Step 2: 刷新商机表
    logger.info("[Step 2/2] 计算并刷新 niche_opportunity")
    try:
        from app.services.niche_services.opportunity_compute_service import run_compute

        r2 = run_compute()
        logger.info("[Step 2/2] 完成: %s", r2)
    except Exception as e:
        logger.error("[Step 2/2] 失败: %s", e, exc_info=True)

    logger.info(
        "[商机每日流程] ====== 完成, 耗时 %.2fs ======",
        round(time.time() - total_start, 2),
    )


def niche_daily_register(task_manager) -> None:
    """注册商机体系每日定时任务（每天凌晨 2:00 执行）"""
    try:
        task_manager.schedule(
            _niche_daily_pipeline,
            'cron',
            'niche_daily_pipeline',
            hour=2,
            minute=0,
            replace_existing=True,
        )
        print("[商机每日流程] 定时任务已注册（每天凌晨 2:00 执行）")
    except Exception as e:
        print(f"[商机每日流程] 注册失败: {e}")
