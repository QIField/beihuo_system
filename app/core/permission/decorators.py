# -*- coding:utf-8 -*-
"""
权限管理模块 - 核心装饰器

提供通用的、解耦的权限检查装饰器。
设计目标：
1. 与具体业务逻辑解耦，通过 PermissionCheckerRegistry 注入检查逻辑
2. 支持多种权限检查模式（单权限、多权限 AND、多权限 OR）
3. 支持角色检查
4. 支持自定义错误响应格式

使用方式：
    from flask import Blueprint, jsonify
    from app.core.permission import (
        require_authentication,
        require_permission,
        require_role,
        require_admin,
    )

    bp = Blueprint('cart', __name__, url_prefix='/api/cart')

    @bp.route('/items', methods=['GET'])
    @require_permission('cart:view')
    def get_items():
        return jsonify({'code': 0, 'msg': 'success'})
"""

from functools import wraps
from typing import Callable, List

from app.core.permission.permission_checker import PermissionCheckerRegistry
from app.core.permission.error_handlers import default_error_response


# ======================================================================
# 登录验证装饰器
# ======================================================================

def require_authentication(
    error_response: Callable = default_error_response,
):
    """
    登录验证装饰器（通用版，替换项目中重复的 login_required）

    检查用户是否已登录（通过 user_id 是否存在于 session）。

    Args:
        error_response: 自定义错误响应构建函数

    使用示例:
        @bp.route('/protected')
        @require_authentication()
        def protected_view():
            return jsonify({'code': 0, 'msg': 'success'})
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = PermissionCheckerRegistry.get_user_id()
            if user_id is None:
                return error_response("未登录，请先登录", 401)
            return func(*args, **kwargs)

        return wrapper

    return decorator


# ======================================================================
# 权限检查装饰器
# ======================================================================

def require_permission(
    permission_code: str,
    error_response: Callable = default_error_response,
    auto_check_auth: bool = True,
):
    """
    单权限检查装饰器

    检查用户是否拥有指定权限。

    Args:
        permission_code: 权限编码，如 'cart:delete'
        error_response: 自定义错误响应构建函数
        auto_check_auth: 是否自动检查登录状态（默认 True）

    使用示例:
        @bp.route('/cart/delete', methods=['POST'])
        @require_permission('cart:delete')
        def delete_cart():
            return jsonify({'code': 0, 'msg': '删除成功'})
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 检查登录
            user_id = PermissionCheckerRegistry.get_user_id()
            if user_id is None:
                return error_response("未登录，请先登录", 401)

            # 检查权限
            if not PermissionCheckerRegistry.check_permission(user_id, permission_code):
                return error_response(
                    f"权限不足，需要权限: {permission_code}",
                    403,
                    required_permission=permission_code,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_any_permission(
    permission_codes: List[str],
    error_response: Callable = default_error_response,
    auto_check_auth: bool = True,
):
    """
    多权限 OR 检查装饰器

    用户只需拥有列表中的任一权限即可访问。

    Args:
        permission_codes: 权限编码列表，如 ['cart:delete', 'order:process']
        error_response: 自定义错误响应构建函数
        auto_check_auth: 是否自动检查登录状态

    使用示例:
        @bp.route('/dashboard')
        @require_any_permission(['dashboard:view', 'admin:view'])
        def dashboard():
            return jsonify({'code': 0, 'msg': 'success'})
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = PermissionCheckerRegistry.get_user_id()
            if user_id is None:
                return error_response("未登录，请先登录", 401)

            # 检查是否拥有任一权限
            has_any = False
            for perm in permission_codes:
                if PermissionCheckerRegistry.check_permission(user_id, perm):
                    has_any = True
                    break

            if not has_any:
                return error_response(
                    f"权限不足，需要以下权限之一: {', '.join(permission_codes)}",
                    403,
                    required_permissions=permission_codes,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_all_permissions(
    permission_codes: List[str],
    error_response: Callable = default_error_response,
    auto_check_auth: bool = True,
):
    """
    多权限 AND 检查装饰器

    用户必须拥有列表中的所有权限才能访问。

    Args:
        permission_codes: 权限编码列表
        error_response: 自定义错误响应构建函数
        auto_check_auth: 是否自动检查登录状态

    使用示例:
        @bp.route('/admin/delete_user', methods=['POST'])
        @require_all_permissions(['user:view', 'user:delete'])
        def delete_user():
            return jsonify({'code': 0, 'msg': '删除成功'})
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = PermissionCheckerRegistry.get_user_id()
            if user_id is None:
                return error_response("未登录，请先登录", 401)

            # 检查是否拥有所有权限
            missing_permissions = []
            for perm in permission_codes:
                if not PermissionCheckerRegistry.check_permission(user_id, perm):
                    missing_permissions.append(perm)

            if missing_permissions:
                return error_response(
                    f"权限不足，缺少权限: {', '.join(missing_permissions)}",
                    403,
                    missing_permissions=missing_permissions,
                    required_permissions=permission_codes,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


# ======================================================================
# 角色检查装饰器
# ======================================================================

def require_role(
    role_code: str,
    error_response: Callable = default_error_response,
    auto_check_auth: bool = True,
):
    """
    角色检查装饰器

    检查用户是否拥有指定角色。

    Args:
        role_code: 角色编码，如 'super_admin'
        error_response: 自定义错误响应构建函数
        auto_check_auth: 是否自动检查登录状态

    使用示例:
        @bp.route('/admin/settings')
        @require_role('super_admin')
        def admin_settings():
            return jsonify({'code': 0, 'msg': 'success'})
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = PermissionCheckerRegistry.get_user_id()
            if user_id is None:
                return error_response("未登录，请先登录", 401)

            # 检查角色
            if not PermissionCheckerRegistry.check_role(user_id, role_code):
                return error_response(
                    f"权限不足，需要角色: {role_code}",
                    403,
                    required_role=role_code,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_any_role(
    role_codes: List[str],
    error_response: Callable = default_error_response,
    auto_check_auth: bool = True,
):
    """
    多角色 OR 检查装饰器

    用户只需拥有列表中的任一角色即可访问。

    Args:
        role_codes: 角色编码列表，如 ['super_admin', 'store_admin']
        error_response: 自定义错误响应构建函数
        auto_check_auth: 是否自动检查登录状态

    使用示例:
        @bp.route('/management')
        @require_any_role(['super_admin', 'store_admin', 'business_manager'])
        def management_page():
            return jsonify({'code': 0, 'msg': 'success'})
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = PermissionCheckerRegistry.get_user_id()
            if user_id is None:
                return error_response("未登录，请先登录", 401)

            # 检查是否拥有任一角色
            has_any = False
            for role in role_codes:
                if PermissionCheckerRegistry.check_role(user_id, role):
                    has_any = True
                    break

            if not has_any:
                return error_response(
                    f"权限不足，需要以下角色之一: {', '.join(role_codes)}",
                    403,
                    required_roles=role_codes,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


# ======================================================================
# 自定义检查装饰器
# ======================================================================

def require_custom_check(
    check_func: Callable[[int], bool],
    error_message: str = "权限不足",
    error_response: Callable = default_error_response,
    auto_check_auth: bool = True,
):
    """
    自定义检查装饰器

    允许传入任意自定义检查函数，实现灵活的权限判断。

    Args:
        check_func: 自定义检查函数，接收 user_id 参数，返回 bool
        error_message: 权限不足时的错误消息
        error_response: 自定义错误响应构建函数
        auto_check_auth: 是否自动检查登录状态

    使用示例:
        def check_store_access(user_id: int) -> bool:
            # 检查用户是否有权限访问当前门店的特殊逻辑
            current_store = get_current_store()
            return check_user_store_permission(user_id, current_store)

        @bp.route('/store/special_data')
        @require_custom_check(check_store_access, "无权访问当前门店数据")
        def special_data():
            return jsonify({'code': 0, 'msg': 'success'})
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = PermissionCheckerRegistry.get_user_id()
            if user_id is None:
                return error_response("未登录，请先登录", 401)

            # 执行自定义检查
            if not check_func(user_id):
                return error_response(error_message, 403)

            return func(*args, **kwargs)

        return wrapper

    return decorator


# ======================================================================
# 便捷装饰器组合
# ======================================================================

def require_admin(
    error_response: Callable = default_error_response,
):
    """
    管理员权限装饰器（便捷）

    等价于 @require_role('super_admin')
    """
    return require_role('super_admin', error_response)


def require_any_admin(
    error_response: Callable = default_error_response,
):
    """
    任意管理员角色装饰器（便捷）

    检查用户是否拥有超级管理员或门店管理员角色
    """
    return require_any_role(['super_admin', 'store_admin'], error_response)


__all__ = [
    'require_authentication',
    'require_permission',
    'require_any_permission',
    'require_all_permissions',
    'require_role',
    'require_any_role',
    'require_custom_check',
    'require_admin',
    'require_any_admin',
]
