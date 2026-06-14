# -*- coding:utf-8 -*-
"""
权限管理模块 - 错误响应构建器

提供权限检查失败时的响应构建函数，
支持自定义错误响应格式，便于与项目现有的 API 响应规范统一。

使用方式：
    from app.core.permission import default_error_response

    # 作为装饰器参数
    @require_permission('cart:delete', error_response=default_error_response)
    def delete_cart():
        pass

    # 也可以自定义响应构建器
    def custom_response(message, code, **kwargs):
        return jsonify({'success': False, 'message': message, **kwargs}), code
"""

from typing import Callable, Any
from flask import jsonify


def default_error_response(message: str, code: int = 403, **kwargs: Any) -> tuple:
    """
    默认的错误响应构建器

    Args:
        message: 错误消息
        code: HTTP 状态码
        **kwargs: 额外数据

    Returns:
        Flask 响应元组 (json_data, status_code)
    """
    response_data = {
        'code': code,
        'msg': message,
        'data': None,
    }
    response_data.update(kwargs)
    return jsonify(response_data), code


def json_error_response(message: str, code: int = 403, **kwargs: Any) -> tuple:
    """
    简洁版错误响应构建器（与项目现有 API 风格保持一致）

    Args:
        message: 错误消息
        code: HTTP 状态码
        **kwargs: 额外数据

    Returns:
        Flask 响应元组 (json_data, status_code)
    """
    response_data = {
        'code': code,
        'msg': message,
    }
    response_data.update(kwargs)
    return jsonify(response_data), code


# 别名（保留与项目风格保持一致
