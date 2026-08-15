# -*- coding:utf-8 -*-
# @Time    : 2026/08/12
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : log.py
# @Software: trae-cn

"""
stock_safe 模块统一日志入口

所有 stock_safe 相关的服务/爬虫/任务文件统一从此模块获取 logger，
确保日志级别和输出目标一致，避免各文件重复配置。

用法：
    from app.scripts.spiders.spiders_services.log import get_stock_safe_logger

    logger = get_stock_safe_logger()
    logger.info("xxx")
"""

import logging

from app.utils.logger_config import get_task_logger


def get_stock_safe_logger():
    """
    获取 stock_safe 模块统一的 logger 实例。

    日志级别固定为 INFO，输出到：
      - logs/task_log/stock_safe/stock_safe.log  (INFO及以上)
      - logs/task_log/errors.log                 (ERROR及以上)

    Returns:
        logging.Logger: 配置好的 stock_safe logger 实例
    """
    logger = get_task_logger('stock_safe')
    logger.setLevel(logging.INFO)
    return logger
