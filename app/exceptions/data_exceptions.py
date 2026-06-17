# -*- coding:utf-8 -*-
# @Time    : 2026/6/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : data_exceptions.py
# @Software : PyCharm
# 数据处理相关异常类
# =====================================================================

from app.exceptions.base import BusinessError


class DataError(BusinessError):
    """
    数据异常基类 —— 所有数据清洗/解析/格式化 相关异常的父类
    便于调用方统一捕获数据处理层的所有异常。

    用法：
        try:
            data = clean_stock_html(html, oe)
        except DataError as e:
            print(f"数据处理出错: {e}")
    """
    pass


class DataParseError(DataError):
    """
    数据解析失败 —— HTML 结构异常、字段缺失、格式不符合预期等

    用法：
        if not stock_table:
            raise DataParseError("HTML 中未找到库存表格，页面结构可能已变更")
    """
    pass


class DataNotFoundError(DataError):
    """
    数据未查询到 —— 零件不存在、未激活、无库存记录等

    用法：
        if data.get("status") == "未查询到":
            raise DataNotFoundError("零件不存在或未激活")
    """
    pass


class DataFormatError(DataError):
    """
    数据格式异常 —— 价格无法转数字、日期格式不符合预期等

    用法：
        if not price_text.isdigit():
            raise DataFormatError(f"价格格式异常: {price_text}")
    """
    pass


class DataPersistenceError(DataError):
    """
    数据持久化失败 —— 数据库 upsert / commit 等操作出错

    用法：
        try:
            session.execute(statement)
        except Exception as e:
            raise DataPersistenceError(f"数据库写入失败: {e}") from e
    """
    pass
