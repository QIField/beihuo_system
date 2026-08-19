# -*- coding:utf-8 -*-
# @Time    : 2026/08/12
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_tasks.py
# @Software: trae-cn

"""
库存安全体系定时任务

每日全流程（每日凌晨 4:00 执行）：
  Step 1: 计算安全库存 (stock_safe)

每日销售订单爬取（每天凌晨 5:00 执行）：
  Step 1: 爬取销售订单历史数据 → 更新最近 3 天

销售&退货+销量表刷新的独立流程（每月 1/10/20 号凌晨 3:00 执行，先于每日全流程）：
  Step 1: 爬取销售订单历史数据 (sales_order_history) —— 兜底更新最近 10 天
  Step 2: 退货订单匹配 (stock_safe_refund_ref)
  Step 3: 构建OE零件销量表 (oe_parts_sales) — 月维度计算，每月刷新一次即可

注册方式：
    from app.scripts.tasks.stock_safe_tasks import (
        stock_safe_daily_register,
        stock_safe_sales_refund_register,
        stock_safe_daily_sales_crawl_register,
    )
    stock_safe_daily_register(task_manager)
    stock_safe_sales_refund_register(task_manager)
    stock_safe_daily_sales_crawl_register(task_manager)
"""

import os
import time
from datetime import datetime, timedelta

from app.scripts.spiders.spiders_services.log import get_stock_safe_logger

logger = get_stock_safe_logger()


def _stock_safe_daily_pipeline() -> dict:
    """
    库存安全体系每日全流程主入口（每日凌晨 4:00 执行）

    执行流程：
      [Step 1] 计算安全库存 → 全量刷新 stock_safe

    Notes:
        Step 1/2/3（销售爬取、退货匹配、销量表构建）已迁移至每月 1/10/20 号独立流程
        `_stock_safe_sales_refund_pipeline` 中执行，每日仅需计算安全库存。

    Returns:
        全流程执行结果摘要
    """
    total_start = time.time()
    results = {}

    logger.info("[库存安全全流程] ====== 开始执行 ======")

    # ── Step 1: 计算安全库存 ──
    logger.info("[Step 1/1] 计算安全库存")
    try:
        from app.services.stock_safe_service.stock_safe_compute_service import run_compute
        r1 = run_compute()
        logger.info("[Step 1/1] 完成: %s", r1)
        results['step1_compute_safe'] = {'status': 'completed', **r1}
    except Exception as e:
        logger.error("[Step 1/1] 失败: %s", e, exc_info=True)
        results['step1_compute_safe'] = {'status': 'failed', 'error': str(e)}

    total_elapsed = round(time.time() - total_start, 2)
    completed = sum(1 for v in results.values() if v.get('status') == 'completed')
    logger.info("[库存安全全流程] ====== 完成: %d/1 步成功, 耗时 %.2fs ======", completed, total_elapsed)

    results['_meta'] = {
        'total_elapsed_time': total_elapsed,
        'completed_steps': completed,
        'timestamp': int(time.time()),
    }
    return results




def stock_safe_daily_register(task_manager) -> None:
    """
    注册库存安全体系每日全流程定时任务（每日凌晨 4:00 执行）

    Args:
        task_manager: LightweightTaskManager 实例
    """

    try:
        task_manager.schedule(
            _stock_safe_daily_pipeline,
            'interval',
            'stock_safe_daily_pipeline',
            hours=1,
            replace_existing=True,
        )
        print("[库存安全全流程] 定时任务已注册（每小时执行一次）")
    except Exception as e:
        print(f"[库存安全全流程] 注册失败: {e}")



def _crawl_and_store_sales_order_history() -> dict:
    """
    每日独立任务：爬取销售订单历史数据（每天凌晨 5:00 执行，只更新最近 3 天）

    Returns:
        执行结果摘要
    """
    total_start = time.time()
    results = {}

    logger.info("[每日销售订单爬取] ====== 开始执行 ======")

    try:
        from app.scripts.spiders.spiders_services.sales_order_history_crawler import (
            crawl_and_store_sales_order_history,
        )
        pre_3day = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        r = crawl_and_store_sales_order_history(start_date=pre_3day)  # pyright: ignore[reportArgumentType]
        logger.info("[每日销售订单爬取] 完成: 入库 %d 条", r)
        results['crawl_sales_daily'] = {'status': 'completed', 'inserted': r, 'start_date': pre_3day}
    except Exception as e:
        logger.error("[每日销售订单爬取] 失败: %s", e, exc_info=True)
        results['crawl_sales_daily'] = {'status': 'failed', 'error': str(e)}

    total_elapsed = round(time.time() - total_start, 2)
    completed = sum(1 for v in results.values() if v.get('status') == 'completed')
    logger.info("[每日销售订单爬取] ====== 完成: %d/1 步成功, 耗时 %.2fs ======", completed, total_elapsed)

    results['_meta'] = {
        'total_elapsed_time': total_elapsed,
        'completed_steps': completed,
        'timestamp': int(time.time()),
    }
    return results


def stock_safe_daily_sales_crawl_register(task_manager) -> None:
    """
    注册每日销售订单历史数据爬取定时任务（每天凌晨 5:00 执行，只更新最近 3 天）

    Args:
        task_manager: LightweightTaskManager 实例
    """
    try:
        task_manager.schedule(
            _crawl_and_store_sales_order_history,
            'cron',
            'stock_safe_daily_sales_crawl',
            hour=5,
            minute=0,
            replace_existing=True,
        )
        print("[每日销售订单爬取] 定时任务已注册（每天凌晨 5:00 执行，更新最近 3 天）")
    except Exception as e:
        print(f"[每日销售订单爬取] 注册失败: {e}")


def _stock_safe_sales_refund_pipeline() -> dict:
    """
    销售订单 & 退货匹配 & 销量表构建流程（每月 1/10/20 号执行）

    执行流程：
      [Step 1] 爬取销售订单历史数据 → 写入 sales_order_history（兜底更新最近 10 天）
      [Step 2] 退货订单匹配 → 全量刷新 stock_safe_refund_ref
      [Step 3] 构建OE零件销量表 → 全量刷新 oe_parts_sales（月维度计算）

    Returns:
        执行结果摘要
    """
    total_start = time.time()
    results = {}

    logger.info("[销售退货流程] ====== 开始执行 ======")

    # ── Step 1: 爬取销售订单历史数据（兜底更新最近 10 天） ──
    logger.info("[Step 1/3] 爬取销售订单历史数据")
    try:
        from app.scripts.spiders.spiders_services.sales_order_history_crawler import (
            crawl_and_store_sales_order_history,
        )
        pre_10day = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
        r1 = crawl_and_store_sales_order_history(start_date=pre_10day)  # pyright: ignore[reportArgumentType]
        logger.info("[Step 1/3] 完成: 入库 %d 条", r1)
        results['step1_crawl_sales'] = {'status': 'completed', 'inserted': r1}
    except Exception as e:
        logger.error("[Step 1/3] 失败: %s", e, exc_info=True)
        results['step1_crawl_sales'] = {'status': 'failed', 'error': str(e)}

    # ── Step 2: 退货订单匹配 ──
    logger.info("[Step 2/3] 退货订单匹配")
    try:
        from app.services.stock_safe_service.stock_safe_refund_ref_service import run_full_process
        r2 = run_full_process()
        logger.info("[Step 2/3] 完成: %s", r2)
        results['step2_refund_ref'] = {'status': 'completed', 'summary': r2}
    except Exception as e:
        logger.error("[Step 2/3] 失败: %s", e, exc_info=True)
        results['step2_refund_ref'] = {'status': 'failed', 'error': str(e)}

    # ── Step 3: 构建OE零件销量表 ──
    logger.info("[Step 3/3] 构建OE零件销量表")
    try:
        from app.services.stock_safe_service.build_oe_parts_sales_service import run_sync
        r3 = run_sync()
        logger.info("[Step 3/3] 完成: %s", r3)
        results['step3_build_sales'] = {'status': 'completed', **r3}
    except Exception as e:
        logger.error("[Step 3/3] 失败: %s", e, exc_info=True)
        results['step3_build_sales'] = {'status': 'failed', 'error': str(e)}

    total_elapsed = round(time.time() - total_start, 2)
    completed = sum(1 for v in results.values() if v.get('status') == 'completed')
    logger.info("[销售退货流程] ====== 完成: %d/3 步成功, 耗时 %.2fs ======", completed, total_elapsed)

    results['_meta'] = {
        'total_elapsed_time': total_elapsed,
        'completed_steps': completed,
        'timestamp': int(time.time()),
    }
    return results


def stock_safe_sales_refund_register(task_manager) -> None:
    """
    注册销售订单 & 退货匹配 & 销量表构建定时任务（每月 1/10/20 号凌晨 3:00 执行）

    Args:
        task_manager: LightweightTaskManager 实例
    """
    try:
        task_manager.schedule(
            _stock_safe_sales_refund_pipeline,
            'cron',
            'stock_safe_sales_refund_pipeline',
            hour=3,
            minute=0,
            day='1,10,20',
            replace_existing=True,
        )
        print("[销售退货流程] 定时任务已注册（每月 1/10/20 号凌晨 3:00 执行）")
    except Exception as e:
        print(f"[销售退货流程] 注册失败: {e}")


# if __name__ == '__main__':
#     _stock_safe_daily_pipeline()
