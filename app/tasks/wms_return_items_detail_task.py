# -*- coding:utf-8 -*-
# @Time    : 2026/7/10
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_return_items_detail_task.py
# @Software: PyCharm
# @Desc    : WMS 采购入库单明细同步定时任务（每天早上6点执行）

import os
from datetime import datetime

from app.services.wms_return_items_service import sync_wms_return_items_detail
from app.utils.logger_config import get_task_logger


logger = get_task_logger('wms_return_items_detail')


def run_wms_return_items_detail_task():
    """
    执行 WMS 采购入库单明细同步定时任务
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"[定时任务] WMS采购入库单明细同步开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 80}")

    try:
        # 最多爬取 20 页订单，同时遇到数据库已存在的订单会立即停止
        result = sync_wms_return_items_detail(page_num=20, logger=logger)
        logger.info(f"[定时任务] WMS采购入库单明细同步完成：{result}")
    except Exception as e:
        logger.exception(f"[定时任务] WMS采购入库单明细同步失败: {e}")
        raise

    logger.info(f"\n{'=' * 80}")
    logger.info(f"[定时任务] WMS采购入库单明细同步结束 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 80}\n")


def register_wms_return_items_detail_tasks(task_manager):
    """
    注册 WMS 采购入库单明细同步定时任务

    每天早上 06:00 执行一次

    :param task_manager: 任务管理器实例（来自 app.core.task_manager）
    """
    auto_start = os.environ.get('AUTO_START_WMS_RETURN_ITEMS_DETAIL', 'true').lower() != 'false'
    if not auto_start:
        logger.info("[WMS采购入库单明细同步] 已禁用")
        return

    try:
        task_manager.schedule(
            run_wms_return_items_detail_task,
            'cron',
            'wms_return_items_detail_task',
            hour=6,
            minute=0,
            replace_existing=True
        )
        logger.info("[WMS采购入库单明细同步] 定时任务已注册（每天06:00执行）")

    except Exception as e:
        logger.error(f"[WMS采购入库单明细同步] 注册失败: {e}")
