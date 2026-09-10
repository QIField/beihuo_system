# -*- coding:utf-8 -*-
# @Time    : 2026/08/12
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_tasks.py
# @Software: trae-cn

"""
库存安全体系定时任务

每日全流程（每小时执行）：
  Step 1: 计算安全库存 (stock_safe)

每日销售爬取 + 补货清单下载链接生成（每天凌晨 3:00 执行）：
  Step 1: 爬取销售订单历史数据 → 更新最近 3 天（最先执行）
  Step 2: 刷新安全库存表 (stock_safe)
  Step 3: 生成补货清单 Excel 下载链接

销售&退货+销量表刷新（每月 1/10/20 号凌晨 3:00 执行）：
  Step 1: 爬取销售订单历史数据 (sales_order_history) —— 兜底更新最近 20 天
  Step 2: 退货订单匹配 (stock_safe_refund_ref)
  Step 3: 构建OE零件销量表 (oe_parts_sales) — 月维度计算，每月刷新一次即可

注册方式：
    from app.scripts.tasks.stock_safe_tasks import (
        stock_safe_daily_register,
        stock_safe_sales_refund_register,
        stock_safe_crawl_replenish_register,
    )
    stock_safe_daily_register(task_manager)
    stock_safe_sales_refund_register(task_manager)
    stock_safe_crawl_replenish_register(task_manager)
"""

import time
from datetime import datetime, timedelta

from app.scripts.spiders.spiders_services.log import get_stock_safe_logger

logger = get_stock_safe_logger()


def _stock_safe_daily_pipeline() -> None:
    """
    库存安全体系每日全流程（每小时执行）

    计算安全库存 → 全量刷新 stock_safe。
    补货清单下载链接由 `stock_safe_crawl_replenish_register` 每天凌晨 3:00 生成。
    """
    total_start = time.time()
    logger.info("[库存安全全流程] ====== 开始执行 ======")

    logger.info("[Step 1/1] 计算安全库存")
    try:
        from app.services.stock_safe_service.stock_safe_compute_service import run_compute
        r1 = run_compute()
        logger.info("[Step 1/1] 完成: %s", r1)
    except Exception as e:
        logger.error("[Step 1/1] 失败: %s", e, exc_info=True)

    logger.info("[库存安全全流程] ====== 完成, 耗时 %.2fs ======", round(time.time() - total_start, 2))


def stock_safe_daily_register(task_manager) -> None:
    """注册库存安全体系每日全流程定时任务（每小时执行一次）"""
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


def _crawl_and_store_sales_order_history() -> None:
    """爬取销售订单历史数据（每天凌晨 5:00 执行，只更新最近 3 天）"""
    total_start = time.time()
    logger.info("[每日销售订单爬取] ====== 开始执行 ======")

    try:
        from app.scripts.spiders.spiders_services.sales_order_history_crawler import (
            crawl_and_store_sales_order_history,
        )
        pre_3day = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        r = crawl_and_store_sales_order_history(start_date=pre_3day)  # pyright: ignore[reportArgumentType]
        logger.info("[每日销售订单爬取] 完成: 入库 %d 条", r)
    except Exception as e:
        logger.error("[每日销售订单爬取] 失败: %s", e, exc_info=True)

    logger.info("[每日销售订单爬取] ====== 完成, 耗时 %.2fs ======", round(time.time() - total_start, 2))


def _stock_safe_crawl_replenish_pipeline() -> None:
    """
    每日销售爬取 + 补货清单下载链接生成流程（每天凌晨 3:00 执行）

    执行顺序：先爬取销售订单历史数据，再刷新安全库存表，最后生成补货清单下载链接。
    全部步骤执行完后，将各步骤结果汇总通过 message_push 推送到微信
    （参考 region_by_number_query_tasks 的推送方式）。
    """
    total_start = time.time()
    logger.info("[销售爬取+补货链接] ====== 开始执行 ======")

    # 汇总各步骤执行结果，供执行完后推送
    step_results: list = []

    # Step 1: 爬虫最先执行（更新最近 3 天）
    logger.info("[Step 1/3] 爬取销售订单历史数据")
    try:
        _crawl_and_store_sales_order_history()
        step_results.append("Step1 销售爬取：成功")
    except Exception as e:
        logger.error("[Step 1/3] 失败: %s", e, exc_info=True)
        step_results.append(f"Step1 销售爬取：失败({e})")

    # Step 2: 刷新安全库存表
    logger.info("[Step 2/3] 刷新安全库存表")
    try:
        from app.services.stock_safe_service.stock_safe_compute_service import run_compute
        r1 = run_compute()
        logger.info("[Step 2/3] 完成: %s", r1)
        step_results.append("Step2 刷新安全库存：成功")
    except Exception as e:
        logger.error("[Step 2/3] 失败: %s", e, exc_info=True)
        step_results.append(f"Step2 刷新安全库存：失败({e})")

    # Step 3: 生成补货清单 Excel 下载链接
    logger.info("[Step 3/3] 生成补货清单 Excel 下载链接")
    try:
        r2 = _generate_replenish_download_link()
        if r2.get('status') == 'completed':
            download_url = r2.get('download_url')
            step_results.append(f"Step3 补货清单链接：成功({download_url})")
            logger.info("[Step 3/3] 完成: %s", download_url)
        else:
            error = r2.get('error')
            step_results.append(f"Step3 补货清单链接：失败({error})")
            logger.error("[Step 3/3] 失败: %s", error)
    except Exception as e:
        logger.error("[Step 3/3] 失败: %s", e, exc_info=True)
        step_results.append(f"Step3 补货清单链接：失败({e})")

    # 执行完后推送结果汇总
    _push_replenish_pipeline_result(step_results, total_start)

    logger.info("[销售爬取+补货链接] ====== 完成, 耗时 %.2fs ======", round(time.time() - total_start, 2))


def _push_replenish_pipeline_result(step_results: list, total_start: float) -> None:
    """
    推送销售爬取 + 补货清单流程执行结果到微信

    参考 region_by_number_query_tasks.information_push 的推送方式，
    汇总各步骤执行结果后通过 message_push 推送。

    Args:
        step_results: 各步骤结果摘要列表
        total_start: 流程开始时间戳（time.time()）
    """
    try:
        from app.utils.common_util_module.server_push import message_push

        time_data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cost = round(time.time() - total_start, 2)
        message = (
            f"===【库存智能补货任务】测试===\n"
            f"提醒时间：{time_data}\n"
            f"总耗时：{cost}s\n"
            + "\n".join(step_results)
        )

        message_push(type="库存智能补货", message=message)
        logger.info("[库存智能补货] 结果推送完成")
    except Exception as e:
        logger.error("[库存智能补货] 结果推送失败: %s", e, exc_info=True)


def stock_safe_crawl_replenish_register(task_manager) -> None:
    """注册每日销售爬取 + 补货清单下载链接生成定时任务（每天凌晨 3:00 执行）"""
    try:
        task_manager.schedule(
            _stock_safe_crawl_replenish_pipeline,
            'cron',
            'stock_safe_crawl_replenish_pipeline',
            hour=3,
            minute=0,
            replace_existing=True,
        )
        print("[销售爬取+补货链接] 定时任务已注册（每天凌晨 3:00 执行）")
    except Exception as e:
        print(f"[销售爬取+补货链接] 注册失败: {e}")


def _generate_replenish_download_link() -> dict:
    """
    生成补货清单 Excel 下载链接

    调用 replenish 服务的 generate_replenish_download_url() 生成补货清单 Excel，
    并返回完整下载链接，供微信推送等场景使用。

    Returns:
        dict: 执行结果摘要（status + download_url / file_path / error 等）
    """
    try:
        from app.services.stock_safe_service.replenish import generate_replenish_download_url

        r = generate_replenish_download_url()
        if not r.get('success'):
            logger.error("[补货清单链接] 生成失败: %s", r.get('msg'))
            return {'status': 'failed', 'error': r.get('msg')}

        logger.info("[补货清单链接] 生成成功: %s", r.get('download_url'))
        return {
            'status': 'completed',
            'download_url': r.get('download_url'),
            'file_path': r.get('file_path'),
            'file_name': r.get('file_name'),
        }
    except Exception as e:
        logger.error("[补货清单链接] 生成失败: %s", e, exc_info=True)
        return {'status': 'failed', 'error': str(e)}


def _stock_safe_sales_refund_pipeline() -> None:
    """
    销售订单 & 退货匹配 & 销量表构建流程（每月 1/10/20 号执行）

    [Step 1] 爬取销售订单历史数据 → 写入 sales_order_history（兜底更新最近 20 天）
    [Step 2] 退货订单匹配 → 全量刷新 stock_safe_refund_ref
    [Step 3] 构建OE零件销量表 → 全量刷新 oe_parts_sales（月维度计算）
    """
    total_start = time.time()
    logger.info("[销售退货流程] ====== 开始执行 ======")

    logger.info("[Step 1/3] 爬取销售订单历史数据")
    try:
        from app.scripts.spiders.spiders_services.sales_order_history_crawler import (
            crawl_and_store_sales_order_history,
        )
        pre_start = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
        r1 = crawl_and_store_sales_order_history(start_date=pre_start)  # pyright: ignore[reportArgumentType]
        logger.info("[Step 1/3] 完成: 入库 %d 条", r1)
    except Exception as e:
        logger.error("[Step 1/3] 失败: %s", e, exc_info=True)

    logger.info("[Step 2/3] 退货订单匹配")
    try:
        from app.services.stock_safe_service.stock_safe_refund_ref_service import run_full_process
        r2 = run_full_process()
        logger.info("[Step 2/3] 完成: %s", r2)
    except Exception as e:
        logger.error("[Step 2/3] 失败: %s", e, exc_info=True)

    logger.info("[Step 3/3] 构建OE零件销量表")
    try:
        from app.services.stock_safe_service.build_oe_parts_sales_service import run_sync
        r3 = run_sync()
        logger.info("[Step 3/3] 完成: %s", r3)
    except Exception as e:
        logger.error("[Step 3/3] 失败: %s", e, exc_info=True)

    logger.info("[销售退货流程] ====== 完成, 耗时 %.2fs ======", round(time.time() - total_start, 2))


def stock_safe_sales_refund_register(task_manager) -> None:
    """注册销售订单 & 退货匹配 & 销量表构建定时任务（每月 1/10/20 号凌晨 3:00 执行）"""
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


if __name__ == "__main__":
    _stock_safe_crawl_replenish_pipeline()
