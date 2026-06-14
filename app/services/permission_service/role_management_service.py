# -*- coding:utf-8 -*-
"""
角色管理业务服务（SQLAlchemy ORM 版本）

负责角色的增删改查、角色继承关系管理等功能。
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, or_

from app.utils.orm.session import orm_session
from app.models.orm_models.system_models import (
    CrmappRoles,
    CrmappUserRoles,
    CrmappRolePermissions,
    CrmappPermissions,
)


class RoleManagementService:
    """
    角色管理服务类（SQLAlchemy ORM 版本）
    """

    # ======================================================================
    # 角色查询
    # ======================================================================

    @staticmethod
    def get_role_list(page: int = 1, page_size: int = 50, keyword: str = None) -> Tuple[List[Dict], int]:
        """
        获取角色列表（分页）

        Args:
            page: 页码
            page_size: 每页数量
            keyword: 搜索关键词（角色名称或编码）

        Returns:
            (角色列表, 总数)
        """
        roles: List[Dict] = []
        total = 0
        offset = (page - 1) * page_size

        try:
            with orm_session() as session:
                query = session.query(CrmappRoles)

                if keyword:
                    like_pattern = f"%{keyword}%"
                    query = query.filter(
                        or_(
                            CrmappRoles.role_name.like(like_pattern),
                            CrmappRoles.role_code.like(like_pattern),
                        )
                    )

                # 查询总数
                total = query.count()

                # 查询数据
                rows = (
                    query.order_by(CrmappRoles.id.asc())
                    .limit(page_size)
                    .offset(offset)
                    .all()
                )

                # 收集所有 parent_role_id，一次性查询父角色名称
                parent_ids = [r.parent_role_id for r in rows if r.parent_role_id]
                parent_map = {}
                if parent_ids:
                    parent_rows = (
                        session.query(CrmappRoles.id, CrmappRoles.role_name)
                        .filter(CrmappRoles.id.in_(parent_ids))
                        .all()
                    )
                    parent_map = {pr.id: pr.role_name for pr in parent_rows}

                # 格式化输出
                for row in rows:
                    role = {
                        'id': row.id,
                        'role_name': row.role_name,
                        'role_code': row.role_code,
                        'description': row.description,
                        'parent_role_id': row.parent_role_id,
                        'parent_role_name': parent_map.get(row.parent_role_id, '') if row.parent_role_id else '',
                        'status': row.status,
                        'created_time': (
                            row.created_time.strftime('%Y-%m-%d %H:%M:%S')
                            if row.created_time else None
                        ),
                        'updated_time': (
                            row.updated_time.strftime('%Y-%m-%d %H:%M:%S')
                            if row.updated_time else None
                        ),
                    }
                    roles.append(role)

        except Exception as e:
            print(f"[RoleManagementService] 获取角色列表失败: {str(e)}")

        return roles, total

    @staticmethod
    def get_role_by_id(role_id: int) -> Optional[Dict]:
        """
        根据ID获取角色详情

        Args:
            role_id: 角色ID

        Returns:
            角色字典，不存在返回 None
        """
        try:
            with orm_session() as session:
                row = (
                    session.query(CrmappRoles)
                    .filter(CrmappRoles.id == role_id)
                    .first()
                )

                if not row:
                    return None

                # 查询父角色名称
                parent_role_name = ''
                if row.parent_role_id:
                    parent = (
                        session.query(CrmappRoles.role_name)
                        .filter(CrmappRoles.id == row.parent_role_id)
                        .first()
                    )
                    parent_role_name = parent.role_name if parent else ''

                return {
                    'id': row.id,
                    'role_name': row.role_name,
                    'role_code': row.role_code,
                    'description': row.description,
                    'parent_role_id': row.parent_role_id,
                    'parent_role_name': parent_role_name,
                    'status': row.status,
                    'created_time': (
                        row.created_time.strftime('%Y-%m-%d %H:%M:%S')
                        if row.created_time else None
                    ),
                    'updated_time': (
                        row.updated_time.strftime('%Y-%m-%d %H:%M:%S')
                        if row.updated_time else None
                    ),
                }

        except Exception as e:
            print(f"[RoleManagementService] 获取角色详情失败: role_id={role_id}, error={str(e)}")
            return None

    @staticmethod
    def get_all_roles() -> List[Dict]:
        """
        获取所有角色（用于下拉选择）

        Returns:
            角色列表（仅包含 id, role_name, role_code, parent_role_id）
        """
        try:
            with orm_session() as session:
                rows = (
                    session.query(CrmappRoles)
                    .filter(CrmappRoles.status == 1)
                    .order_by(CrmappRoles.id.asc())
                    .all()
                )

                return [
                    {
                        'id': r.id,
                        'role_name': r.role_name,
                        'role_code': r.role_code,
                        'parent_role_id': r.parent_role_id,
                    }
                    for r in rows
                ]

        except Exception as e:
            print(f"[RoleManagementService] 获取所有角色失败: {str(e)}")
            return []

    # ======================================================================
    # 角色创建
    # ======================================================================

    @staticmethod
    def create_role(role_name: str, role_code: str, description: str = '',
                    parent_role_id: int = None, status: int = 1) -> Tuple[bool, str, Optional[int]]:
        """
        创建新角色

        Args:
            role_name: 角色名称
            role_code: 角色编码（唯一）
            description: 角色描述
            parent_role_id: 父角色ID（用于角色继承）
            status: 状态（0-禁用，1-启用）

        Returns:
            (是否成功, 消息, 新角色ID)
        """
        if not role_name or not role_code:
            return False, "角色名称和编码不能为空", None

        try:
            with orm_session() as session:
                # 检查 role_code 是否已存在
                exists = (
                    session.query(CrmappRoles.id)
                    .filter(CrmappRoles.role_code == role_code)
                    .first()
                )
                if exists:
                    return False, f"角色编码 {role_code} 已存在", None

                # 检查父角色是否存在
                if parent_role_id:
                    parent = (
                        session.query(CrmappRoles.id)
                        .filter(CrmappRoles.id == parent_role_id)
                        .first()
                    )
                    if not parent:
                        return False, "父角色不存在", None

                # 创建新角色
                new_role = CrmappRoles(
                    role_name=role_name,
                    role_code=role_code,
                    description=description,
                    parent_role_id=parent_role_id,
                    status=status,
                    created_time=datetime.now(),
                    updated_time=datetime.now(),
                )
                session.add(new_role)
                session.flush()  # 拿到新生成的 id
                role_id = new_role.id

            return True, "创建成功", role_id

        except Exception as e:
            print(f"[RoleManagementService] 创建角色失败: {str(e)}")
            return False, f"创建失败: {str(e)}", None

    # ======================================================================
    # 角色更新
    # ======================================================================

    @staticmethod
    def update_role(role_id: int, role_name: str = None, role_code: str = None,
                    description: str = None, parent_role_id: int = None,
                    status: int = None) -> Tuple[bool, str]:
        """
        更新角色信息

        Args:
            role_id: 角色ID
            role_name: 角色名称（可选）
            role_code: 角色编码（可选）
            description: 角色描述（可选）
            parent_role_id: 父角色ID（可选）
            status: 状态（可选）

        Returns:
            (是否成功, 消息)
        """
        if not role_id:
            return False, "角色ID不能为空"

        try:
            with orm_session() as session:
                role = (
                    session.query(CrmappRoles)
                    .filter(CrmappRoles.id == role_id)
                    .first()
                )
                if not role:
                    return False, "角色不存在"

                # 检查 role_code 唯一性（如果要更新的话）
                if role_code and role_code != role.role_code:
                    code_exists = (
                        session.query(CrmappRoles.id)
                        .filter(
                            CrmappRoles.role_code == role_code,
                            CrmappRoles.id != role_id,
                        )
                        .first()
                    )
                    if code_exists:
                        return False, f"角色编码 {role_code} 已存在"

                # 逐字段更新
                if role_name is not None:
                    role.role_name = role_name
                if role_code is not None:
                    role.role_code = role_code
                if description is not None:
                    role.description = description
                if parent_role_id is not None:
                    role.parent_role_id = parent_role_id
                if status is not None:
                    role.status = status

                role.updated_time = datetime.now()

            return True, "更新成功"

        except Exception as e:
            print(f"[RoleManagementService] 更新角色失败: role_id={role_id}, error={str(e)}")
            return False, f"更新失败: {str(e)}"

    # ======================================================================
    # 角色删除
    # ======================================================================

    @staticmethod
    def delete_role(role_id: int) -> Tuple[bool, str]:
        """
        删除角色

        注意：
        1. 检查是否有子角色引用该角色
        2. 检查是否有用户使用该角色
        3. 删除角色-权限关联

        Args:
            role_id: 角色ID

        Returns:
            (是否成功, 消息)
        """
        if not role_id:
            return False, "角色ID不能为空"

        try:
            with orm_session() as session:
                # 检查是否有子角色
                child_count = (
                    session.query(CrmappRoles.id)
                    .filter(CrmappRoles.parent_role_id == role_id)
                    .count()
                )
                if child_count > 0:
                    return False, "该角色存在子角色，无法删除"

                # 检查是否有用户使用该角色
                user_count = (
                    session.query(CrmappUserRoles.id)
                    .filter(CrmappUserRoles.role_id == role_id)
                    .count()
                )
                if user_count > 0:
                    return False, "有用户正在使用该角色，无法删除"

                # 删除角色-权限关联
                session.query(CrmappRolePermissions).filter(
                    CrmappRolePermissions.role_id == role_id
                ).delete(synchronize_session=False)

                # 删除角色本身
                session.query(CrmappRoles).filter(
                    CrmappRoles.id == role_id
                ).delete(synchronize_session=False)

            return True, "删除成功"

        except Exception as e:
            print(f"[RoleManagementService] 删除角色失败: role_id={role_id}, error={str(e)}")
            return False, f"删除失败: {str(e)}"

    # ======================================================================
    # 角色-权限管理
    # ======================================================================

    @staticmethod
    def get_role_permissions(role_id: int) -> List[Dict]:
        """
        获取角色的权限列表

        Args:
            role_id: 角色ID

        Returns:
            权限列表（含分配状态）
        """
        try:
            with orm_session() as session:
                # SELECT p.*, rp.status as assign_status
                # FROM crmapp_role_permissions rp
                # INNER JOIN crmapp_permissions p ON rp.permission_id = p.id
                # WHERE rp.role_id = ?
                # ORDER BY p.id ASC
                rows = (
                    session.query(
                        CrmappPermissions.id,
                        CrmappPermissions.permission_name,
                        CrmappPermissions.permission_code,
                        CrmappPermissions.description,
                        CrmappPermissions.type,
                        CrmappPermissions.status,
                        CrmappRolePermissions.status.label('assign_status'),
                    )
                    .join(
                        CrmappRolePermissions,
                        CrmappRolePermissions.permission_id == CrmappPermissions.id,
                    )
                    .filter(CrmappRolePermissions.role_id == role_id)
                    .order_by(CrmappPermissions.id.asc())
                    .all()
                )

                return [
                    {
                        'id': r.id,
                        'permission_name': r.permission_name,
                        'permission_code': r.permission_code,
                        'description': r.description,
                        'type': r.type,
                        'status': r.status,
                        'assign_status': r.assign_status,
                    }
                    for r in rows
                ]

        except Exception as e:
            print(f"[RoleManagementService] 获取角色权限失败: role_id={role_id}, error={str(e)}")
            return []

    @staticmethod
    def assign_permissions_to_role(role_id: int, permission_ids: List[int]) -> Tuple[bool, str]:
        """
        为角色分配权限（覆盖式）

        先删除原有的所有权限关联，再批量插入新的。

        Args:
            role_id: 角色ID
            permission_ids: 权限ID列表

        Returns:
            (是否成功, 消息)
        """
        if not role_id:
            return False, "角色ID不能为空"

        try:
            with orm_session() as session:
                # 删除原有所有关联
                session.query(CrmappRolePermissions).filter(
                    CrmappRolePermissions.role_id == role_id
                ).delete(synchronize_session=False)

                # 批量插入新关联
                if permission_ids:
                    now = datetime.now()
                    for perm_id in permission_ids:
                        rp = CrmappRolePermissions(
                            role_id=role_id,
                            permission_id=perm_id,
                            status=1,
                            created_time=now,
                            updated_time=now,
                        )
                        session.add(rp)

            return True, "权限分配成功"

        except Exception as e:
            print(f"[RoleManagementService] 分配权限失败: role_id={role_id}, error={str(e)}")
            return False, f"分配失败: {str(e)}"
