# -*- coding:utf-8 -*-
"""
权限管理模块 - 自定义异常

提供权限检查过程中可能抛出的自定义异常类。
"""


class PermissionDeniedError(Exception):
    """权限不足异常"""

    def __init__(self, message: str = "权限不足", permission: str = None):
        self.message = message
        self.permission = permission
        super().__init__(message)


class NotAuthenticatedError(Exception):
    """未登录异常"""

    def __init__(self, message: str = "未登录，请先登录"):
        self.message = message
        super().__init__(message)


__all__ = [
    'PermissionDeniedError',
    'NotAuthenticatedError',
]
