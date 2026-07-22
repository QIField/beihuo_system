# -*- coding:utf-8 -*-
"""
权限管理模块 - 增强版装饰器

提供更灵活的权限控制装饰器，如参数级权限限制。
"""

# 导入 wraps 装饰器，用于保留被装饰函数的元信息（函数名、文档字符串等）
from functools import wraps
# 导入类型注解，用于类型提示，提高代码可读性和 IDE 支持
from typing import Callable, Any, Dict

# 导入 Flask 的 request 对象，用于获取当前请求的参数
from flask import request

# 导入权限检查器注册表，提供统一的权限检查入口（与业务逻辑解耦）
from app.core.permission.permission_checker import PermissionCheckerRegistry
# 导入默认错误响应构建函数，用于权限不足时返回统一格式的错误响应
from app.core.permission.error_handlers import default_error_response


def require_param_permission(
    param_name: str,           # 要限制的参数名称（如 'status'、'type' 等）
    permission_value_map: Dict[str, Any],  # 权限编码与参数值的映射字典：{权限编码: 参数值}
    bypass_permission: str = None,  # 超级权限编码，拥有该权限可访问所有参数值  # pyright: ignore[reportArgumentType]
):
    """
    参数权限限制装饰器

    根据用户权限限制某个参数的有效值。一个权限对应一个参数值。
    用户没有对应权限时，直接拦截返回 403 错误。
    未登录时直接返回 401 错误。
    拥有 bypass_permission 权限的用户可跳过参数值检查，访问所有值。

    Args:
        param_name: 要限制的参数名称
        permission_value_map: 权限编码与参数值的映射 {permission_code: param_value}
                              用户拥有某个权限，才能使用对应的值
        bypass_permission: 超级权限编码，拥有该权限可访问所有参数值（默认 None）

    使用示例:
        @bp.route('/orders', methods=['GET'])
        @require_param_permission(
            'status',
            {
                'order:view_pending': 'pending',
                'order:view_completed': 'completed',
            },
            bypass_permission='order:view_all',
        )
        def get_orders(status=None):
            # status 参数已被校验，只有有权限的值才会通过
            # 拥有 order:view_all 权限的用户可以访问任意 status 值
            pass
    """

    # 定义装饰器函数，接收被装饰的原函数作为参数
    def decorator(func: Callable) -> Callable:
        # 使用 wraps 保留原函数的元信息（函数名、__doc__ 等）
        @wraps(func)
        # 定义包装函数，在调用原函数前后执行权限检查和参数校验逻辑
        def wrapper(*args, **kwargs):
            # 从权限检查器注册表获取当前登录用户的 ID
            user_id = PermissionCheckerRegistry.get_user_id()

            # 判断用户是否未登录（user_id 为 None 表示未登录）
            if user_id is None:
                # 返回 401 未登录错误响应
                return default_error_response("未登录，请先登录", 401)

            # 检查是否拥有超级权限，拥有则直接放行，跳过参数值检查
            if bypass_permission and PermissionCheckerRegistry.check_permission(user_id, bypass_permission):
                return func(*args, **kwargs)

            # 初始化允许的参数值集合（用集合去重，提高查找效率）
            allowed_values = set()
            # 遍历权限-值映射字典
            for perm_code, value in permission_value_map.items():
                # 检查用户是否拥有该权限
                if PermissionCheckerRegistry.check_permission(user_id, perm_code):
                    # 拥有权限则将对应的值加入允许集合
                    allowed_values.add(value)

            # 先尝试从 kwargs 中获取参数值（可能由外层装饰器传入）
            current_value = kwargs.get(param_name)
            # 如果 kwargs 中没有该参数，则从 HTTP 请求中获取
            if current_value is None:
                # GET 请求：从 URL 查询参数中获取
                if request.method == 'GET':
                    current_value = request.args.get(param_name)
                # JSON 请求：从请求体 JSON 中获取
                elif request.is_json:
                    current_value = request.json.get(param_name) if request.json else None
                # 其他请求（如 POST form）：从表单数据中获取
                else:
                    current_value = request.form.get(param_name)

            # 判断当前请求的参数值是否在允许的集合中
            if current_value not in allowed_values:
                # 找出需要哪些权限才能使用当前值
                required_permissions = [
                    perm_code for perm_code, value in permission_value_map.items()
                    if value == current_value
                ]
                # 如果找不到对应的权限，说明该值本身不合法，返回所有可用权限
                if not required_permissions:
                    required_permissions = list(permission_value_map.keys())
                # 返回 403 权限不足错误响应
                return default_error_response(
                    f"权限不足，需要权限: {', '.join(required_permissions)}",
                    403,
                    required_permissions=required_permissions,
                )

            # 权限校验通过，直接调用原函数
            # 注意：不修改 kwargs，原函数自行从 request 中获取参数
            return func(*args, **kwargs)

        # 返回包装后的函数
        return wrapper

    # 返回装饰器函数
    return decorator


# 模块导出列表，定义使用 `from module import *` 时导出的内容
__all__ = [
    'require_param_permission',  # 导出参数权限限制装饰器
]
