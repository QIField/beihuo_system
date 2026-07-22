# -*- coding:utf-8 -*-
"""
用户-角色管理业务服务（SQLAlchemy ORM 版本）

负责用户与角色之间的关联关系管理（分配角色、取消角色等）。
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_

from app.utils.orm.session import orm_session
from app.services.permission_service.permission_service import PermissionService
from app.models.orm_models.system_models import (
    CrmappUserRoles,
    CrmappUsers,
    CrmappRoles,
)


class UserRoleManagementService:
    """
    用户-角色管理服务类（SQLAlchemy ORM 版本）
    """

    # ======================================================================
    # 用户列表查询（用于用户角色分配页面的左侧用户列表）
    # ======================================================================

    @staticmethod
    def get_user_list(
        page: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
    ) -> Tuple[List[Dict], int]:
        """
        获取用户列表（分页 + 搜索）

        Args:
            page: 页码，默认 1
            page_size: 每页数量，默认 10
            keyword: 搜索关键词（用户名/门店/部门/职级模糊匹配），可为 None

        Returns:
            (用户字典列表, 总数)
        """
        if page <= 0:
            page = 1
        if page_size <= 0:
            page_size = 10

        try:
            with orm_session() as session:
                query = session.query(CrmappUsers)

                if keyword:
                    like_key = f'%{keyword}%'
                    query = query.filter(
                        (CrmappUsers.username.like(like_key))
                        | (CrmappUsers.store.like(like_key))
                        | (CrmappUsers.department.like(like_key))
                        | (CrmappUsers.job_level.like(like_key))
                    )

                total = query.count()

                users = (
                    query.order_by(CrmappUsers.id.asc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                    .all()
                )

                # 在 session 关闭前完成字段读取
                user_list = [
                    u.to_dict(include_sensitive=False)
                    for u in users
                ]

            return user_list, total

        except Exception as e:
            print(f"[UserRoleManagementService] 获取用户列表失败: keyword={keyword}, error={str(e)}")
            return [], 0

    # ======================================================================
    # 用户的角色查询
    # ======================================================================

    @staticmethod
    def get_user_roles(user_id: int) -> List[Dict]:
        """
        获取用户的角色列表

        Args:
            user_id: 用户ID

        Returns:
            角色列表（含分配状态、角色基本信息）
        """
        try:
            with orm_session() as session:
                # SELECT ur.*, r.*
                # FROM crmapp_user_roles ur
                # INNER JOIN crmapp_roles r ON ur.role_id = r.id
                # WHERE ur.user_id = ? AND ur.status = 1
                # ORDER BY ur.id ASC
                rows = (
                    session.query(
                        CrmappUserRoles.id,
                        CrmappUserRoles.user_id,
                        CrmappUserRoles.role_id,
                        CrmappUserRoles.status,
                        CrmappUserRoles.created_time,
                        CrmappUserRoles.updated_time,
                        CrmappRoles.role_name,
                        CrmappRoles.role_code,
                        CrmappRoles.description,
                    )
                    .join(
                        CrmappRoles,
                        CrmappUserRoles.role_id == CrmappRoles.id,
                    )
                    .filter(
                        and_(
                            CrmappUserRoles.user_id == user_id,
                            CrmappUserRoles.status == 1,
                        )
                    )
                    .order_by(CrmappUserRoles.id.asc())
                    .all()
                )

                return [
                    {
                        'id': r.id,
                        'user_id': r.user_id,
                        'role_id': r.role_id,
                        'role_name': r.role_name,
                        'role_code': r.role_code,
                        'description': r.description,
                        'status': r.status,
                        'created_time': (
                            r.created_time.strftime('%Y-%m-%d %H:%M:%S')
                            if r.created_time else None
                        ),
                        'updated_time': (
                            r.updated_time.strftime('%Y-%m-%d %H:%M:%S')
                            if r.updated_time else None
                        ),
                    }
                    for r in rows
                ]

        except Exception as e:
            print(f"[UserRoleManagementService] 获取用户角色失败: user_id={user_id}, error={str(e)}")
            return []

    @staticmethod
    def get_user_roles_with_all(user_id: int) -> List[Dict]:
        """
        获取所有角色 + 用户分配状态（用于角色分配页面）

        Args:
            user_id: 用户ID

        Returns:
            所有角色列表（含是否分配给用户的状态）
        """
        try:
            with orm_session() as session:
                # 查询所有角色（左连接用户角色关联表）
                # SELECT r.*, ur.id as ur_id, ur.status as assign_status
                # FROM crmapp_roles r
                # LEFT JOIN crmapp_user_roles ur
                #     ON ur.role_id = r.id
                #     AND ur.user_id = ?
                #     AND ur.status = 1
                # ORDER BY r.id ASC
                rows = (
                    session.query(
                        CrmappRoles.id,
                        CrmappRoles.role_name,
                        CrmappRoles.role_code,
                        CrmappRoles.description,
                        CrmappRoles.status,
                        CrmappUserRoles.id.label('ur_id'),
                        CrmappUserRoles.status.label('assign_status'),
                    )
                    .outerjoin(
                        CrmappUserRoles,
                        and_(
                            CrmappUserRoles.role_id == CrmappRoles.id,
                            CrmappUserRoles.user_id == user_id,
                            CrmappUserRoles.status == 1,
                        ),
                    )
                    .order_by(CrmappRoles.id.asc())
                    .all()
                )

                return [
                    {
                        'id': r.id,
                        'role_name': r.role_name,
                        'role_code': r.role_code,
                        'description': r.description,
                        'status': r.status,
                        'assigned': 1 if r.ur_id is not None and r.assign_status == 1 else 0,
                    }
                    for r in rows
                ]

        except Exception as e:
            print(f"[UserRoleManagementService] 获取用户角色列表失败: user_id={user_id}, error={str(e)}")
            return []

    @staticmethod
    def get_users_by_role(role_id: int) -> List[Dict]:
        """
        获取某角色下的所有用户

        Args:
            role_id: 角色ID

        Returns:
            用户列表（含基本信息）
        """
        try:
            with orm_session() as session:
                # SELECT ur.*, u.*
                # FROM crmapp_user_roles ur
                # INNER JOIN crmapp_users u ON ur.user_id = u.id
                # WHERE ur.role_id = ? AND ur.status = 1
                # ORDER BY ur.id ASC
                rows = (
                    session.query(
                        CrmappUserRoles.id,
                        CrmappUserRoles.user_id,
                        CrmappUserRoles.role_id,
                        CrmappUserRoles.status,
                        CrmappUsers.username,
                        CrmappUsers.usercode,
                        CrmappUsers.email,
                        CrmappUsers.status.label('user_status'),
                    )
                    .join(
                        CrmappUsers,
                        CrmappUserRoles.user_id == CrmappUsers.id,
                    )
                    .filter(
                        and_(
                            CrmappUserRoles.role_id == role_id,
                            CrmappUserRoles.status == 1,
                        )
                    )
                    .order_by(CrmappUserRoles.id.asc())
                    .all()
                )

                return [
                    {
                        'id': r.id,
                        'user_id': r.user_id,
                        'role_id': r.role_id,
                        'username': r.username,
                        'usercode': r.usercode,
                        'email': r.email,
                        'status': r.user_status,
                    }
                    for r in rows
                ]

        except Exception as e:
            print(f"[UserRoleManagementService] 获取角色用户失败: role_id={role_id}, error={str(e)}")
            return []

    # ======================================================================
    # 用户分配/取消角色
    # ======================================================================

    @staticmethod
    def assign_role_to_user(user_id: int, role_id: int) -> Tuple[bool, str]:
        """
        为用户分配单个角色（幂等操作）

        - 如果用户已经有该角色且 status=1，直接返回成功
        - 如果用户已经有该角色但 status=0，更新为 status=1
        - 否则插入新记录

        Args:
            user_id: 用户ID
            role_id: 角色ID

        Returns:
            (是否成功, 消息)
        """
        if not user_id or not role_id:
            return False, "用户ID和角色ID不能为空"

        try:
            with orm_session() as session:
                # 检查用户是否存在
                user = (
                    session.query(CrmappUsers.id)
                    .filter(CrmappUsers.id == user_id)
                    .first()
                )
                if not user:
                    return False, "用户不存在"

                # 检查角色是否存在
                role = (
                    session.query(CrmappRoles.id)
                    .filter(CrmappRoles.id == role_id)
                    .first()
                )
                if not role:
                    return False, "角色不存在"

                # 检查是否已分配
                existing = (
                    session.query(CrmappUserRoles)
                    .filter(
                        and_(
                            CrmappUserRoles.user_id == user_id,
                            CrmappUserRoles.role_id == role_id,
                        )
                    )
                    .first()
                )

                if existing:
                    if existing.status == 1:
                        return True, "角色已分配"
                    else:
                        existing.status = 1
                        existing.updated_time = datetime.now()
                else:
                    new_ur = CrmappUserRoles(
                        user_id=user_id,
                        role_id=role_id,
                        status=1,
                        created_time=datetime.now(),
                        updated_time=datetime.now(),
                    )
                    session.add(new_ur)

            PermissionService.clear_cache(user_id)
            return True, "角色分配成功"

        except Exception as e:
            print(f"[UserRoleManagementService] 分配角色失败: user_id={user_id}, role_id={role_id}, error={str(e)}")
            return False, f"分配失败: {str(e)}"

    @staticmethod
    def assign_roles_to_user(user_id: int, role_ids: List[int]) -> Tuple[bool, str]:
        """
        为用户批量分配角色（覆盖式）

        - 先将该用户所有现有关联置为 status=0
        - 然后将 role_ids 中的角色置为 status=1（存在则更新，不存在则插入）

        Args:
            user_id: 用户ID
            role_ids: 角色ID列表

        Returns:
            (是否成功, 消息)
        """
        if not user_id:
            return False, "用户ID不能为空"

        try:
            with orm_session() as session:
                # 检查用户是否存在
                user = (
                    session.query(CrmappUsers.id)
                    .filter(CrmappUsers.id == user_id)
                    .first()
                )
                if not user:
                    return False, "用户不存在"

                # 先将该用户所有现有关联置为 status=0
                session.query(CrmappUserRoles).filter(
                    CrmappUserRoles.user_id == user_id
                ).update(
                    {'status': 0, 'updated_time': datetime.now()},
                    synchronize_session=False,
                )

                # 逐个处理新角色列表
                if role_ids:
                    now = datetime.now()
                    for role_id in role_ids:
                        existing = (
                            session.query(CrmappUserRoles)
                            .filter(
                                and_(
                                    CrmappUserRoles.user_id == user_id,
                                    CrmappUserRoles.role_id == role_id,
                                )
                            )
                            .first()
                        )

                        if existing:
                            existing.status = 1
                            existing.updated_time = now
                        else:
                            new_ur = CrmappUserRoles(
                                user_id=user_id,
                                role_id=role_id,
                                status=1,
                                created_time=now,
                                updated_time=now,
                            )
                            session.add(new_ur)

            PermissionService.clear_cache(user_id)
            return True, "角色分配成功"

        except Exception as e:
            print(f"[UserRoleManagementService] 批量分配角色失败: user_id={user_id}, error={str(e)}")
            return False, f"分配失败: {str(e)}"

    @staticmethod
    def remove_role_from_user(user_id: int, role_id: int) -> Tuple[bool, str]:
        """
        取消用户的某个角色（软删除：置 status=0）

        Args:
            user_id: 用户ID
            role_id: 角色ID

        Returns:
            (是否成功, 消息)
        """
        if not user_id or not role_id:
            return False, "用户ID和角色ID不能为空"

        try:
            with orm_session() as session:
                rows_affected = (
                    session.query(CrmappUserRoles)
                    .filter(
                        and_(
                            CrmappUserRoles.user_id == user_id,
                            CrmappUserRoles.role_id == role_id,
                            CrmappUserRoles.status == 1,
                        )
                    )
                    .update(
                        {'status': 0, 'updated_time': datetime.now()},
                        synchronize_session=False,
                    )
                )

            if rows_affected > 0:
                PermissionService.clear_cache(user_id)
                return True, "角色取消成功"
            else:
                return True, "用户没有该角色"

        except Exception as e:
            print(f"[UserRoleManagementService] 取消角色失败: user_id={user_id}, role_id={role_id}, error={str(e)}")
            return False, f"取消失败: {str(e)}"

    @staticmethod
    def remove_all_roles_from_user(user_id: int) -> Tuple[bool, str]:
        """
        取消用户的所有角色（软删除：置 status=0）

        Args:
            user_id: 用户ID

        Returns:
            (是否成功, 消息)
        """
        if not user_id:
            return False, "用户ID不能为空"

        try:
            with orm_session() as session:
                session.query(CrmappUserRoles).filter(
                    and_(
                        CrmappUserRoles.user_id == user_id,
                        CrmappUserRoles.status == 1,
                    )
                ).update(
                    {'status': 0, 'updated_time': datetime.now()},
                    synchronize_session=False,
                )

            PermissionService.clear_cache(user_id)
            return True, "已取消所有角色"

        except Exception as e:
            print(f"[UserRoleManagementService] 取消所有角色失败: user_id={user_id}, error={str(e)}")
            return False, f"取消失败: {str(e)}"
