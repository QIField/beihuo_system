# -*- coding:utf-8 -*-
# @Time    : 2026/6/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : base.py
# @Software : PyCharm
# 基础异常类 —— 项目所有自定义异常的基类
# =====================================================================


class BeihuoBaseException(Exception):
    """
    项目根异常类 —— 所有自定义异常都继承自它
    便于统一捕获和日志记录。

    用法：
        try:
            ...
        except BeihuoBaseException as e:
            logger.error(f"业务异常: {e}")
    """

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message

    def __str__(self):
        return self.message


class ParameterError(BeihuoBaseException):
    """
    参数校验异常 —— 入参不合法、格式错误、缺失必填项等
    例如：零件号为空、格式不正确、长度异常等

    用法：
        raise ParameterError("零件号（oe）不能为空")
    """
    pass


class BusinessError(BeihuoBaseException):
    """
    通用业务异常 —— 业务规则不满足
    作为其他业务异常的基类，也可以直接使用。

    用法：
        raise BusinessError("当前零件不支持批量查询")
    """
    pass
