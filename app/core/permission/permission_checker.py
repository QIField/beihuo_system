# -*- coding:utf-8 -*-
"""
权限管理模块 - 权限检查器注册表

提供可注入的权限检查器注册表，让装饰器代码与具体业务逻辑解耦。

使用方式：
    from app.core.permission import PermissionCheckerRegistry
    from app.services.permission_service import PermissionService

    # 在应用启动时注册实际的检查函数
    PermissionCheckerRegistry.register_permission_checker(PermissionService.has_permission)
    PermissionCheckerRegistry.register_role_checker(PermissionService.has_role)

    # 之后装饰器就可以正常工作了
"""

from typing import Callable, Optional, Set
from flask import session


class PermissionCheckerRegistry:
    """
    权限检查器注册表

    通过动态注册回调函数，让装饰器可以调用业务层的权限检查逻辑，
    而不需要直接 import 业务层代码（避免循环依赖）。

    设计原则：
    - 未注册检查器时，会抛出明确的 RuntimeError，而不是静默返回 False
    - 所有注册和检查操作都是线程安全的（只读引用，不会中途改变）
    """

    # 已注册的回调函数（未注册时为 None）
    _permission_checker: Optional[Callable[[int, str], bool]] = None
    _role_checker: Optional[Callable[[int, str], bool]] = None
    _permissions_getter: Optional[Callable[[int], Set[str]]] = None
    _roles_getter: Optional[Callable[[int], Set[str]]] = None
    _user_id_getter: Optional[Callable[[], Optional[int]]] = None

    # ======================================================================
    # 注册方法
    # ======================================================================

    @classmethod
    def register_permission_checker(cls, checker: Callable[[int, str], bool]):
        """注册权限检查函数"""
        cls._permission_checker = checker

    @classmethod
    def register_role_checker(cls, checker: Callable[[int, str], bool]):
        """注册角色检查函数"""
        cls._role_checker = checker

    @classmethod
    def register_permissions_getter(cls, getter: Callable[[int], Set[str]]):
        """注册权限获取函数"""
        cls._permissions_getter = getter

    @classmethod
    def register_roles_getter(cls, getter: Callable[[int], Set[str]]):
        """注册角色获取函数"""
        cls._roles_getter = getter

    @classmethod
    def register_user_id_getter(cls, getter: Callable[[], Optional[int]]):
        """注册用户ID获取函数"""
        cls._user_id_getter = getter  # pyright: ignore[reportAttributeAccessIssue]

    # ======================================================================
    # 检查 / 获取方法
    # ======================================================================

    @classmethod
    def get_user_id(cls) -> Optional[int]:
        """获取当前用户ID（默认从 session 获取）"""
        if cls._user_id_getter is not None:  # pyright: ignore[reportAttributeAccessIssue]
            return cls._user_id_getter()  # pyright: ignore[reportAttributeAccessIssue]
        return session.get('user_id')

    @classmethod
    def check_permission(cls, user_id: int, permission_code: str) -> bool:
        """检查用户是否拥有指定权限"""
        if cls._permission_checker is None:
            raise RuntimeError(
                "权限检查器未初始化：请在应用启动时调用 "
                "PermissionCheckerRegistry.register_permission_checker()"
            )
        return cls._permission_checker(user_id, permission_code)

    @classmethod
    def check_role(cls, user_id: int, role_code: str) -> bool:
        """检查用户是否拥有指定角色"""
        if cls._role_checker is None:
            raise RuntimeError(
                "角色检查器未初始化：请在应用启动时调用 "
                "PermissionCheckerRegistry.register_role_checker()"
            )
        return cls._role_checker(user_id, role_code)

    @classmethod
    def get_permissions(cls, user_id: int) -> Set[str]:
        """获取用户的所有权限编码"""
        if cls._permissions_getter is None:
            raise RuntimeError(
                "权限获取器未初始化：请在应用启动时调用 "
                "PermissionCheckerRegistry.register_permissions_getter()"
            )
        return cls._permissions_getter(user_id)

    @classmethod
    def get_roles(cls, user_id: int) -> Set[str]:
        """获取用户的所有角色编码"""
        if cls._roles_getter is None:
            raise RuntimeError(
                "角色获取器未初始化：请在应用启动时调用 "
                "PermissionCheckerRegistry.register_roles_getter()"
            )
        return cls._roles_getter(user_id)


__all__ = [
    'PermissionCheckerRegistry',
]
