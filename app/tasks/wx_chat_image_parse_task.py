# -*- coding: utf-8 -*-
"""
微信群聊图片解析定时任务
每天凌晨 03:00 执行
"""

import os
from datetime import datetime

from app.services.ai_image_recognition.image_parse_service import parse_wx_chat_images
from app.utils.logger_config import get_task_logger


logger = get_task_logger('wx_chat_image_parse_task')


def run_wx_chat_image_parse():
    """执行微信群聊图片解析定时任务。"""
    logger.info("\n" + "=" * 80)
    logger.info(f"[定时任务] 微信群聊图片解析开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    parse_wx_chat_images()

    logger.info("\n" + "=" * 80)
    logger.info(f"[定时任务] 微信群聊图片解析完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80 + "\n")


def register_wx_chat_image_parse_tasks(task_manager):
    """
    注册微信群聊图片解析定时任务

    :param task_manager: 任务管理器实例（来自 app.core.task_manager）
    """
    auto_start = os.environ.get('AUTO_START_WX_CHAT_IMAGE_PARSE', 'true').lower() != 'false'
    if not auto_start:
        logger.info("[微信群聊图片解析] 已禁用")
        return

    try:
        task_manager.schedule(
            run_wx_chat_image_parse,
            'cron',
            'wx_chat_image_parse_daily',
            hour=3,
            minute=0,
            replace_existing=True
        )
        logger.info("[微信群聊图片解析] 定时任务已注册（每天03:00）")
    except Exception as e:
        logger.error(f"[微信群聊图片解析] 定时任务注册失败: {e}")
