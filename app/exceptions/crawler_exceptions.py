# -*- coding:utf-8 -*-
# @Time    : 2026/6/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crawler_exceptions.py
# @Software : PyCharm
# 爬虫相关异常类
# =====================================================================

from app.exceptions.base import BusinessError


class CrawlerError(BusinessError):
    """
    爬虫异常基类 —— 所有爬虫相关异常的父类
    便于调用方统一捕获爬虫层的所有异常。

    用法：
        try:
            response = spider.get_stock_check(oe)
        except CrawlerError as e:
            print(f"爬虫出错: {e}")
    """
    pass


class CrawlerRequestError(CrawlerError):
    """
    爬虫请求失败 —— response 为 None、网络超时、DNS 解析失败等

    用法：
        if response is None:
            raise CrawlerRequestError("请求失败（可能是 curl_cffi 未安装或网络错误）")
    """
    pass


class CrawlerResponseEmptyError(CrawlerError):
    """
    爬虫响应为空 —— response.text 为空或长度为 0

    用法：
        if not response.text:
            raise CrawlerResponseEmptyError("响应为空（可能 Cookie 已失效）")
    """
    pass


class CrawlerCookieInvalidError(CrawlerError):
    """
    Cookie 失效/无效 —— 专门用于 Cookie 相关的异常场景

    用法：
        if is_logged_out(response):
            raise CrawlerCookieInvalidError("Cookie 已失效，请重新登录")
    """
    pass
