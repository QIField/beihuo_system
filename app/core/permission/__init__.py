# -*- coding:utf-8 -*-
"""
权限管理模块入口

提供权限检查、角色管理相关的核心功能：
1. PermissionCheckerRegistry - 可注入的检查器注册表
2. 各种装饰器（require_permission, require_role 等）
3. 自定义异常

使用方式：
    from app.core.permission import (
        require_permission,
        require_role,
        require_admin,
        PermissionCheckerRegistry,
    )
"""

from app.core.permission.exceptions import (
    PermissionDeniedError,
    NotAuthenticatedError,
)

from app.core.permission.permission_checker import (
    PermissionCheckerRegistry,
)

from app.core.permission.error_handlers import (
    default_error_response,
    json_error_response,
)

from app.core.permission.decorators import (
    require_authentication,
    require_page_login,
    require_page_permission,
    require_page_role,
    require_permission,
    require_any_permission,
    require_all_permissions,
    require_role,
    require_any_role,
    require_custom_check,
    require_admin,
    require_any_admin,
)

__all__ = [
    # 基础类
    'PermissionCheckerRegistry',
    # 异常
    'PermissionDeniedError',
    'NotAuthenticatedError',
    # 装饰器
    'require_authentication',
    'require_page_login',
    'require_page_permission',
    'require_page_role',
    'require_permission',
    'require_any_permission',
    'require_all_permissions',
    'require_role',
    'require_any_role',
    'require_custom_check',
    'require_admin',
    'require_any_admin',
    # 工具
    'default_error_response',
    'json_error_response',
]
