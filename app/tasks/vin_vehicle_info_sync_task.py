#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VIN 车辆信息补全定时任务
每天 19:00 执行，先整合数据源再爬虫补全，每个 key 最多处理 100 条
"""

import logging

from app.services.vin_vehicle_info_service import run_vin_vehicle_info_sync


logger = logging.getLogger('vin_vehicle_info_sync')

TASK_ID = 'vin_vehicle_info_sync'


def vin_vehicle_info_sync_task():
    """VIN 车辆信息补全任务入口"""
    try:
        run_vin_vehicle_info_sync(limit=100)
    except Exception:
        logger.exception("[VIN车辆信息补全] 任务执行失败")
        raise


def register_vin_vehicle_info_sync_tasks(task_manager):
    """注册 VIN 车辆信息补全定时任务"""
    task_manager.schedule(
        vin_vehicle_info_sync_task,
        'cron',
        TASK_ID,
        hour=19,
        minute=0,
        replace_existing=True
    )
    logger.info("[VIN车辆信息补全] 定时任务已注册（每天19:00，先整合再补全，每个key最多100条）")
