# -*- coding:utf-8 -*-
"""data.gzbbr.com 自动登录更新 Cookie 定时任务"""

import os
import sys
from typing import Tuple

# 确保直接运行脚本时能找到项目根目录
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.scripts.spiders.spiders_services.data_gzbbr_login_service import (
    DataGzbbrLoginService,
)
from app.utils.logger_config import get_task_logger

logger = get_task_logger("data_gzbbr_login")


def data_gzbbr_login_daily_task(config_key: str = "data_gzbbr_com_fs") -> Tuple[bool, str]:
    """
    data.gzbbr.com 每日登录更新 Cookie 任务

    Args:
        config_key: 保存 Cookie 的配置键，默认 data_gzbbr_com_fs

    Returns:
        (是否成功, Cookie 字符串或错误信息)
    """
    logger.info("=" * 60)
    logger.info("[定时任务] data.gzbbr.com 每日登录更新 Cookie 开始")
    logger.info("=" * 60)

    try:
        service = DataGzbbrLoginService(config_key=config_key)
        success, cookie = service.run()

        if success:
            logger.info("[定时任务] 执行成功")
        else:
            logger.error("[定时任务] 执行失败")

        return success, cookie

    except Exception as e:
        logger.exception(f"[定时任务] 执行异常: {e}")
        return False, ""


def register_data_gzbbr_login_tasks(task_manager):
    """注册 data.gzbbr.com 每日登录更新 Cookie 定时任务（每天 7:00）"""
    auto_start = os.environ.get('AUTO_START_DATA_GZBBR_LOGIN', 'true').lower() != 'false'
    if not auto_start:
        print("[data.gzbbr 登录] 已禁用")
        return

    task_manager.schedule(
        data_gzbbr_login_daily_task,
        'cron',
        'data_gzbbr_login_daily',
        hour=7,
        minute=0,
        replace_existing=True
    )
    print("[data.gzbbr 登录] 定时任务已注册（每天 7:00）")


if __name__ == '__main__':
    data_gzbbr_login_daily_task()
