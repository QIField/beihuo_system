# -*- coding:utf-8 -*-
"""
权限检查核心服务（使用 SQLAlchemy ORM）

提供用户权限、角色的查询和验证功能。
使用方式：
    from app.services.permission_service import PermissionService

    # 检查权限
    if PermissionService.has_permission(user_id, 'cart:delete'):
        # 执行操作
        pass

    # 检查角色
    if PermissionService.has_role(user_id, 'super_admin'):
        # 执行操作
        pass
"""

from datetime import datetime
from typing import List, Optional, Set

from app.core.cache_utils import get_default_cache
from app.utils.orm.session import orm_session
from app.models.orm_models.system_models import (
    CrmappRoles,
    CrmappPermissions,
    CrmappUserRoles,
    CrmappRolePermissions,
    CrmappUsers,
)


# ======================================================================
# 权限缓存（使用应用级共享缓存 cache_utils.get_default_cache）
# - 通过 key 前缀区分：perm:user_{id} 存权限，role:user_{id} 存角色
# - TTL=60 秒：权限变更后最多 60 秒生效
# ======================================================================

# 统一使用应用级共享缓存（单例）
_cache = get_default_cache()


class PermissionService:
    """
    权限检查核心服务类（SQLAlchemy ORM 版本）

    负责：
    1. 从数据库获取用户的角色列表
    2. 从数据库获取用户的权限列表
    3. 验证用户是否拥有指定权限/角色
    4. 实现角色继承（父角色权限自动被子角色继承）
    5. 通过 cache_utils.Cache 提供线程安全的内存缓存（TTL=60s, LRU 淘汰）
    """

    # 缓存开关（保留这个开关，方便调试时临时关闭）
    _CACHE_ENABLED = True
    _CACHE_TTL = 60*30  # 缓存有效期（秒），与上面 Cache 实例保持一致

    # ======================================================================
    # 缓存管理
    # ======================================================================

    @classmethod
    def clear_cache(cls, user_id: Optional[int] = None):
        """
        清除权限缓存

        Args:
            user_id: 指定用户ID清除缓存，None 则清除所有缓存
        """
        if user_id is None:
            # 只清权限相关的 key，不影响应用其他缓存
            for key in _cache.keys('perm:user_*'):
                _cache.delete(key)
            for key in _cache.keys('role:user_*'):
                _cache.delete(key)
        else:
            _cache.delete(f"perm:user_{user_id}")
            _cache.delete(f"role:user_{user_id}")

    @classmethod
    def _get_cached_permissions(cls, user_id: int) -> Optional[Set[str]]:
        """从缓存获取权限（若未启用或已过期返回 None）"""
        if not cls._CACHE_ENABLED:
            return None
        return _cache.get(f"perm:user_{user_id}")

    @classmethod
    def _set_cached_permissions(cls, user_id: int, permissions: Set[str]):
        """设置权限缓存"""
        if cls._CACHE_ENABLED:
            _cache.set(f"perm:user_{user_id}", permissions, ttl=cls._CACHE_TTL)

    @classmethod
    def _get_cached_roles(cls, user_id: int) -> Optional[Set[str]]:
        """从缓存获取角色（若未启用或已过期返回 None）"""
        if not cls._CACHE_ENABLED:
            return None
        return _cache.get(f"role:user_{user_id}")

    @classmethod
    def _set_cached_roles(cls, user_id: int, roles: Set[str]):
        """设置角色缓存"""
        if cls._CACHE_ENABLED:
            _cache.set(f"role:user_{user_id}", roles, ttl=cls._CACHE_TTL)

    # ======================================================================
    # 角色查询（SQLAlchemy ORM）
    # ======================================================================

    @classmethod
    def get_user_roles(cls, user_id: int) -> Set[str]:
        """
        获取用户的所有角色编码（含角色继承）

        通过 CrmappUserRoles 表查询用户分配的角色，
        然后递归查询父角色，实现角色继承。

        Args:
            user_id: 用户ID

        Returns:
            角色编码集合，如 {'business_staff', 'read_only'}
        """
        # 先尝试从缓存获取
        cached = cls._get_cached_roles(user_id)
        if cached is not None:
            return cached

        roles: Set[str] = set()

        try:
            with orm_session() as session:
                now = datetime.now()

                # ----------------------------------------------------------
                # 第一步：查询用户直接分配的角色（状态+有效期过滤）
                # 对应 SQL：
                #   SELECT r.id, r.role_code
                #   FROM crmapp_user_roles ur
                #   INNER JOIN crmapp_roles r ON ur.role_id = r.id
                #   WHERE ur.user_id = %s
                #     AND ur.status = 1
                #     AND r.status = 1
                #     AND (ur.start_time IS NULL OR ur.start_time <= %s)
                #     AND (ur.end_time   IS NULL OR ur.end_time   >= %s)
                # ----------------------------------------------------------
                direct_roles = (
                    session.query(CrmappRoles.id, CrmappRoles.role_code)
                    .join(CrmappUserRoles, CrmappUserRoles.role_id == CrmappRoles.id)
                    .filter(
                        CrmappUserRoles.user_id == user_id,
                        CrmappUserRoles.status == 1,
                        CrmappRoles.status == 1,
                        # 有效期：start_time 为 NULL 或 <= now
                        (CrmappUserRoles.start_time.is_(None) | (CrmappUserRoles.start_time <= now)),
                        # 有效期：end_time 为 NULL 或 >= now
                        (CrmappUserRoles.end_time.is_(None) | (CrmappUserRoles.end_time >= now)),
                    )
                    .all()
                )

                # 收集直接角色 ID 和编码
                current_role_ids: Set[int] = set()
                for row in direct_roles:
                    current_role_ids.add(row.id)
                    roles.add(row.role_code)

                # ----------------------------------------------------------
                # 第二步：递归查询父角色（角色继承）
                # ----------------------------------------------------------
                if current_role_ids:
                    cls._recursive_get_parent_roles(session, current_role_ids, roles)

            # 查询完成后写入缓存
            cls._set_cached_roles(user_id, roles)

        except Exception as e:
            print(f"[PermissionService] 获取用户角色失败: user_id={user_id}, error={str(e)}")

        return roles

    @classmethod
    def _recursive_get_parent_roles(cls, session, role_ids: Set[int], roles: Set[str]):
        """
        递归查询父角色

        Args:
            session: SQLAlchemy Session 对象
            role_ids: 当前角色ID集合
            roles: 收集角色编码的集合
        """
        if not role_ids:
            return

        # ----------------------------------------------------------
        # 第一步：找出这批角色的 parent_role_id
        # 对应 SQL：
        #   SELECT DISTINCT r.parent_role_id
        #   FROM crmapp_roles r
        #   WHERE r.id IN (...)
        #     AND r.parent_role_id IS NOT NULL
        #     AND r.status = 1
        # ----------------------------------------------------------
        parent_rows = (
            session.query(CrmappRoles.parent_role_id)
            .filter(
                CrmappRoles.id.in_(list(role_ids)),
                CrmappRoles.parent_role_id.isnot(None),
                CrmappRoles.status == 1,
            )
            .distinct()
            .all()
        )

        # 收集父角色 ID（排除已经查询过的，避免循环）
        parent_ids: Set[int] = set()
        for row in parent_rows:
            pid = row.parent_role_id
            if pid and pid not in role_ids:
                parent_ids.add(pid)

        # ----------------------------------------------------------
        # 第二步：查询父角色的详细信息（role_code）
        # 对应 SQL：
        #   SELECT id, role_code FROM crmapp_roles WHERE id IN (...)
        # ----------------------------------------------------------
        if parent_ids:
            parent_role_rows = (
                session.query(CrmappRoles.id, CrmappRoles.role_code)
                .filter(
                    CrmappRoles.id.in_(list(parent_ids)),
                    CrmappRoles.status == 1,
                )
                .all()
            )

            for row in parent_role_rows:
                if row.role_code not in roles:
                    roles.add(row.role_code)
                    role_ids.add(row.id)  # 标记已查询过，避免循环

            # ------------------------------------------------------
            # 第三步：递归查询祖父角色
            # ------------------------------------------------------
            cls._recursive_get_parent_roles(session, parent_ids, roles)

    # ======================================================================
    # 权限查询（SQLAlchemy ORM）
    # ======================================================================

    @classmethod
    def get_user_permissions(cls, user_id: int) -> Set[str]:
        """
        获取用户的所有权限编码

        先获取用户所有角色，再查询这些角色的所有权限，
        最后合并去重。

        Args:
            user_id: 用户ID

        Returns:
            权限编码集合，如 {'cart:view', 'cart:delete', 'order:process'}
        """
        # 先尝试从缓存获取
        cached = cls._get_cached_permissions(user_id)
        if cached is not None:
            return cached      
        permissions: Set[str] = set()

        try:
            # 1. 先获取用户所有角色（这一步内部有自己的缓存）
            roles = cls.get_user_roles(user_id)

            if not roles:
                # 无角色，设置空缓存并返回
                cls._set_cached_permissions(user_id, permissions)
                return permissions

            with orm_session() as session:
                # ------------------------------------------------------
                # 第一步：根据 role_code 查询角色 ID
                # 对应 SQL：
                #   SELECT id FROM crmapp_roles WHERE role_code IN (...) AND status = 1
                # ------------------------------------------------------
                

                role_id_rows = (
                    session.query(CrmappRoles.id)
                    .filter(
                        CrmappRoles.role_code.in_(list(roles)),
                        CrmappRoles.status == 1,
                    )
                    .all()
                )

                role_ids = [row.id for row in role_id_rows]

                if role_ids:
                    # --------------------------------------------------
                    # 第二步：通过角色-权限关联表，查所有权限编码
                    # 对应 SQL：
                    #   SELECT DISTINCT p.permission_code
                    #   FROM crmapp_role_permissions rp
                    #   INNER JOIN crmapp_permissions p
                    #           ON rp.permission_id = p.id
                    #   WHERE rp.role_id IN (...)
                    #     AND rp.status = 1
                    #     AND p.status = 1
                    # --------------------------------------------------
                    perm_rows = (
                        session.query(CrmappPermissions.permission_code)
                        .join(
                            CrmappRolePermissions,
                            CrmappRolePermissions.permission_id == CrmappPermissions.id,
                        )
                        .filter(
                            CrmappRolePermissions.role_id.in_(role_ids),
                            CrmappRolePermissions.status == 1,
                            CrmappPermissions.status == 1,
                        )
                        .distinct()
                        .all()
                    )

                    for row in perm_rows:
                        permissions.add(row.permission_code)

            # 查询完成后写入缓存
            cls._set_cached_permissions(user_id, permissions)

        except Exception as e:
            print(f"[PermissionService] 获取用户权限失败: user_id={user_id}, error={str(e)}")

        return permissions

    # ======================================================================
    # 权限/角色检查
    # ======================================================================

    @classmethod
    def has_permission(cls, user_id: int, permission_code: str) -> bool:
        """
        检查用户是否拥有指定权限

        Args:
            user_id: 用户ID
            permission_code: 权限编码

        Returns:
            True 表示有权限，False 表示无权限
        """
        if not user_id:
            return False

        # 管理员自动拥有所有权限
        if cls.is_admin(user_id):
            return True

        print(f"[PermissionService] 检查用户 {user_id} 是否有权限 {permission_code}")
        permissions = cls.get_user_permissions(user_id)
        return permission_code in permissions

    @classmethod
    def has_any_permission(cls, user_id: int, permission_codes: List[str]) -> bool:
        """
        检查用户是否拥有列表中的任一权限（OR 逻辑）

        Args:
            user_id: 用户ID
            permission_codes: 权限编码列表

        Returns:
            True 表示拥有任一权限，False 表示一个都没有
        """
        if not user_id or not permission_codes:
            return False

        permissions = cls.get_user_permissions(user_id)
        return any(perm in permissions for perm in permission_codes)

    @classmethod
    def has_all_permissions(cls, user_id: int, permission_codes: List[str]) -> bool:
        """
        检查用户是否拥有列表中的所有权限（AND 逻辑）

        Args:
            user_id: 用户ID
            permission_codes: 权限编码列表

        Returns:
            True 表示拥有所有权限，False 表示缺少权限
        """
        if not user_id or not permission_codes:
            return False

        permissions = cls.get_user_permissions(user_id)
        return all(perm in permissions for perm in permission_codes)

    @classmethod
    def has_role(cls, user_id: int, role_code: str) -> bool:
        """
        检查用户是否拥有指定角色

        Args:
            user_id: 用户ID
            role_code: 角色编码

        Returns:
            True 表示拥有该角色，False 表示不拥有
        """
        if not user_id:
            return False

        roles = cls.get_user_roles(user_id)
        return role_code in roles

    @classmethod
    def has_any_role(cls, user_id: int, role_codes: List[str]) -> bool:
        """
        检查用户是否拥有列表中的任一角色（OR 逻辑）

        Args:
            user_id: 用户ID
            role_codes: 角色编码列表

        Returns:
            True 表示拥有任一角色，False 表示一个都没有
        """
        if not user_id or not role_codes:
            return False

        roles = cls.get_user_roles(user_id)
        return any(role in roles for role in role_codes)

    # ======================================================================
    # 向后兼容：支持旧的字段检查
    # ======================================================================

    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """
        检查用户是否为管理员（兼容旧的 is_admin 字段）

        优先检查角色（super_admin 或 store_admin），
        如果角色表未初始化，回退到检查 crmapp_users 的 is_admin 字段。

        Args:
            user_id: 用户ID

        Returns:
            True 表示是管理员
        """
        # 优先检查角色
        if cls.has_any_role(user_id, ['super_admin', 'store_admin']):
            return True

        # 回退：检查用户表的 is_admin 字段（SQLAlchemy ORM 版本）
        try:
            with orm_session() as session:
                user = (
                    session.query(CrmappUsers.is_admin)
                    .filter(CrmappUsers.id == user_id)
                    .first()
                )
                if user and user.is_admin:
                    return True
        except Exception as e:
            print(f"[PermissionService] 检查管理员状态失败: user_id={user_id}, error={str(e)}")

        return False
