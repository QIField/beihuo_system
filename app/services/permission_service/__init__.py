# -*- coding:utf-8 -*-
"""
权限管理服务模块入口

提供权限检查、角色管理、权限管理等功能。
使用方式：
    from app.services.permission_service import (
        PermissionService,
        RoleManagementService,
        PermissionManagementService,
        UserRoleManagementService,
        init_permission_checkers
    )
    
    # 在应用启动时调用一次，注册权限检查器
    init_permission_checkers()
"""

from app.services.permission_service.permission_service import PermissionService
from app.services.permission_service.role_management_service import RoleManagementService
from app.services.permission_service.permission_management_service import PermissionManagementService
from app.services.permission_service.user_role_management_service import UserRoleManagementService

# 是否已经初始化（避免重复注册）
_initialized = False


def init_permission_checkers():
    """
    初始化权限检查器
    
    将 PermissionService 的方法注册到装饰器系统的 PermissionCheckerRegistry。
    这样装饰器（require_permission 等）就可以通过业务服务层检查权限。
    
    应该在应用启动时调用一次。
    """
    global _initialized
    if _initialized:
        return
    
    try:
        from app.core.permission import PermissionCheckerRegistry
        
        # 注册权限检查函数
        PermissionCheckerRegistry.register_permission_checker(PermissionService.has_permission)
        
        # 注册角色检查函数
        PermissionCheckerRegistry.register_role_checker(PermissionService.has_role)
        
        # 注册权限获取函数
        PermissionCheckerRegistry.register_permissions_getter(PermissionService.get_user_permissions)
        
        # 注册角色获取函数
        PermissionCheckerRegistry.register_roles_getter(PermissionService.get_user_roles)
        
        # 注册用户ID获取函数（从 session 中获取）
        def get_current_user_id_from_session():
            from flask import session
            return session.get('user_id')
        
        PermissionCheckerRegistry.register_user_id_getter(get_current_user_id_from_session)
        
        _initialized = True
        print("[PermissionService] 权限检查器注册成功")
        
    except Exception as e:
        print(f"[PermissionService] 权限检查器注册失败: {str(e)}")


__all__ = [
    'PermissionService',
    'RoleManagementService',
    'PermissionManagementService',
    'UserRoleManagementService',
    'init_permission_checkers',
]
