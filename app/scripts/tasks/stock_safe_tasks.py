# -*- coding:utf-8 -*-
# @Time    : 2026/08/12
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_tasks.py
# @Software: trae-cn

"""
库存安全体系每日全流程定时任务

业务流程（每日凌晨4:00 执行，统一入口）：
  Step 1: 爬取销售订单历史数据 (sales_order_history)
  Step 2: 退货订单匹配 (stock_safe_refund_ref)
  Step 3: 构建OE零件销量表 (oe_parts_sales)
  Step 4: 计算安全库存 (stock_safe)

注册方式：
    from app.scripts.tasks.stock_safe_tasks import stock_safe_daily_register
    stock_safe_daily_register(task_manager)
"""

import os
import time
from datetime import datetime, timedelta

from app.scripts.spiders.spiders_services.log import get_stock_safe_logger

logger = get_stock_safe_logger()


def _stock_safe_daily_pipeline() -> dict:
    """
    库存安全体系每日全流程主入口

    执行流程：
      [Step 1] 爬取销售订单历史数据 → 写入 sales_order_history
      [Step 2] 退货订单匹配 → 全量刷新 stock_safe_refund_ref
      [Step 3] 构建OE零件销量表 → 全量刷新 oe_parts_sales
      [Step 4] 计算安全库存 → 全量刷新 stock_safe

    每个步骤独立 try-except，单步失败不影响后续步骤执行，
    最终汇总各步骤结果返回。

    Returns:
        全流程执行结果摘要
    """
    total_start = time.time()
    results = {}

    logger.info("[库存安全全流程] ====== 开始执行 ======")

    # ── Step 1: 爬取销售订单历史数据 ──
    logger.info("[Step 1/4] 爬取销售订单历史数据")
    try:
        from app.scripts.spiders.spiders_services.sales_order_history_crawler import (
            crawl_and_store_sales_order_history,
        )
        pre_10day = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        r1 = crawl_and_store_sales_order_history(start_date=pre_10day)  # pyright: ignore[reportArgumentType]
        logger.info("[Step 1/4] 完成: 入库 %d 条", r1)
        results['step1_crawl_sales'] = {'status': 'completed', 'inserted': r1}
    except Exception as e:
        logger.error("[Step 1/4] 失败: %s", e, exc_info=True)
        results['step1_crawl_sales'] = {'status': 'failed', 'error': str(e)}

    # ── Step 2: 退货订单匹配 ──
    logger.info("[Step 2/4] 退货订单匹配")
    try:
        from app.services.stock_safe_service.stock_safe_refund_ref_service import run_full_process
        r2 = run_full_process()
        logger.info("[Step 2/4] 完成: %s", r2)
        results['step2_refund_ref'] = {'status': 'completed', 'summary': r2}
    except Exception as e:
        logger.error("[Step 2/4] 失败: %s", e, exc_info=True)
        results['step2_refund_ref'] = {'status': 'failed', 'error': str(e)}

    # ── Step 3: 构建OE零件销量表 ──
    logger.info("[Step 3/4] 构建OE零件销量表")
    try:
        from app.services.stock_safe_service.build_oe_parts_sales_service import run_sync
        r3 = run_sync()
        logger.info("[Step 3/4] 完成: %s", r3)
        results['step3_build_sales'] = {'status': 'completed', **r3}
    except Exception as e:
        logger.error("[Step 3/4] 失败: %s", e, exc_info=True)
        results['step3_build_sales'] = {'status': 'failed', 'error': str(e)}

    # ── Step 4: 计算安全库存 ──
    logger.info("[Step 4/4] 计算安全库存")
    try:
        from app.services.stock_safe_service.stock_safe_compute_service import run_compute
        r4 = run_compute()
        logger.info("[Step 4/4] 完成: %s", r4)
        results['step4_compute_safe'] = {'status': 'completed', **r4}
    except Exception as e:
        logger.error("[Step 4/4] 失败: %s", e, exc_info=True)
        results['step4_compute_safe'] = {'status': 'failed', 'error': str(e)}

    total_elapsed = round(time.time() - total_start, 2)
    completed = sum(1 for v in results.values() if v.get('status') == 'completed')
    logger.info("[库存安全全流程] ====== 完成: %d/4 步成功, 耗时 %.2fs ======", completed, total_elapsed)

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
            'cron',
            'stock_safe_daily_pipeline',
            hour=4,
            minute=0,
            replace_existing=True,
        )
        print("[库存安全全流程] 定时任务已注册（每日凌晨 4:00 执行）")
    except Exception as e:
        print(f"[库存安全全流程] 注册失败: {e}")




# if __name__ == '__main__':
#     _stock_safe_daily_pipeline()