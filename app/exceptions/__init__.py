# -*- coding:utf-8 -*-
# @Time    : 2026/6/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software : PyCharm
# 自定义异常类模块
# =====================================================================

from app.exceptions.base import BeihuoBaseException, ParameterError, BusinessError
from app.exceptions.crawler_exceptions import (
    CrawlerError,
    CrawlerRequestError,
    CrawlerResponseEmptyError,
    CrawlerCookieInvalidError,
)
from app.exceptions.data_exceptions import (
    DataError,
    DataParseError,
    DataNotFoundError,
    DataFormatError,
    DataPersistenceError,
)

__all__ = [
    # 基础异常
    "BeihuoBaseException",
    "ParameterError",
    "BusinessError",
    # 爬虫异常
    "CrawlerError",
    "CrawlerRequestError",
    "CrawlerResponseEmptyError",
    "CrawlerCookieInvalidError",
    # 数据异常
    "DataError",
    "DataParseError",
    "DataNotFoundError",
    "DataFormatError",
    "DataPersistenceError",
]
