# -*- coding:utf-8 -*-
"""
权限管理业务服务（SQLAlchemy ORM 版本）

负责权限的增删改查、权限分组管理等功能。
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime

from sqlalchemy import and_, or_

from app.utils.orm.session import orm_session
from app.services.permission_service.permission_service import PermissionService
from app.models.orm_models.system_models import (
    CrmappPermissions,
    CrmappRolePermissions,
)


class PermissionManagementService:
    """
    权限管理服务类（SQLAlchemy ORM 版本）
    """

    # ======================================================================
    # 权限查询
    # ======================================================================

    @staticmethod
    def get_permission_list(page: int = 1, page_size: int = 50, keyword: str = None,  # pyright: ignore[reportArgumentType]
                            perm_type: int = None, parent_permission_id: int = None) -> Tuple[List[Dict], int]:  # pyright: ignore[reportArgumentType]
        """
        获取权限列表（分页）

        Args:
            page: 页码
            page_size: 每页数量
            keyword: 搜索关键词（权限名称或编码）
            perm_type: 权限类型筛选（1-模块权限，2-操作权限）
            parent_permission_id: 父权限ID筛选

        Returns:
            (权限列表, 总数)
        """
        permissions: List[Dict] = []
        total = 0
        offset = (page - 1) * page_size

        try:
            with orm_session() as session:
                query = session.query(CrmappPermissions)

                # 构建查询条件
                conditions = []
                if keyword and keyword != '':
                   
                    like_pattern = f"%{keyword}%"
                    conditions.append(
                        or_(
                            CrmappPermissions.permission_name.like(like_pattern),
                            CrmappPermissions.permission_code.like(like_pattern),
                        )
                    )
                if perm_type is not None and perm_type != '':
                   
                    conditions.append(CrmappPermissions.type == perm_type)
                if parent_permission_id is not None and parent_permission_id != '':
                    conditions.append(CrmappPermissions.parent_permission_id == parent_permission_id)

                if conditions:
                    query = query.filter(and_(*conditions))

                # 查询总数（先不做 limit/offset）
                total = query.count()

                # 查询数据（分页 + 排序）
                rows = (
                    query.order_by(CrmappPermissions.type.asc(),
                                   CrmappPermissions.id.asc())
                    .limit(page_size)
                    .offset(offset)
                    .all()
                )

                # 类型映射
                type_map = {1: '模块权限', 2: '操作权限'}

                for row in rows:
                    perm = {
                        'id': row.id,
                        'permission_name': row.permission_name,
                        'permission_code': row.permission_code,
                        'description': row.description,
                        'parent_permission_id': row.parent_permission_id,
                        'type': row.type,
                        'type_name': type_map.get(row.type, '未知'),  # pyright: ignore[reportCallIssue, reportArgumentType]
                        'status': row.status,
                        'created_time': (
                            row.created_time.strftime('%Y-%m-%d %H:%M:%S')
                            if row.created_time else None  # pyright: ignore[reportGeneralTypeIssues]
                        ),
                        'updated_time': (
                            row.updated_time.strftime('%Y-%m-%d %H:%M:%S')
                            if row.updated_time else None  # pyright: ignore[reportGeneralTypeIssues]
                        ),
                    }
                    permissions.append(perm)

        except Exception as e:
            print(f"[PermissionManagementService] 获取权限列表失败: {str(e)}")

        return permissions, total

    @staticmethod
    def get_permission_by_id(permission_id: int) -> Optional[Dict]:
        """
        根据ID获取权限详情

        Args:
            permission_id: 权限ID

        Returns:
            权限字典，不存在返回 None
        """
        try:
            with orm_session() as session:
                row = (
                    session.query(CrmappPermissions)
                    .filter(CrmappPermissions.id == permission_id)
                    .first()
                )

                if not row:
                    return None

                type_map = {1: '模块权限', 2: '操作权限'}

                return {
                    'id': row.id,
                    'permission_name': row.permission_name,
                    'permission_code': row.permission_code,
                    'description': row.description,
                    'parent_permission_id': row.parent_permission_id,
                    'type': row.type,
                    'type_name': type_map.get(row.type, '未知'),  # pyright: ignore[reportGeneralTypeIssues, reportCallIssue, reportArgumentType]
                    'status': row.status,
                    'created_time': (
                        row.created_time.strftime('%Y-%m-%d %H:%M:%S')
                        if row.created_time else None  # pyright: ignore[reportGeneralTypeIssues]
                    ),
                    'updated_time': (
                        row.updated_time.strftime('%Y-%m-%d %H:%M:%S')
                        if row.updated_time else None  # pyright: ignore[reportGeneralTypeIssues]
                    ),
                }

        except Exception as e:
            print(f"[PermissionManagementService] 获取权限详情失败: permission_id={permission_id}, error={str(e)}")
            return None

    @staticmethod
    def get_all_permissions() -> List[Dict]:
        """
        获取所有模块权限（type=1）并构建无限层级树形结构。

        用于"父权限下拉框"等只需模块作为候选父节点的场景。
        只返回 type=1 的模块权限，支持任意层级的父子嵌套。

        Returns:
            [
                {
                    "id": 1,
                    "permission_name": "系统管理",
                    "permission_code": "module:system",
                    "type": 1,
                    ...
                    "children": [
                        {
                            "id": 2,
                            "permission_name": "用户管理",
                            "type": 1,
                            ...
                            "children": [...]
                        },
                        ...
                    ]
                },
                ...
            ]
        """
        try:
            all_perms: List[Dict] = []
            with orm_session() as session:
                rows = (
                    session.query(CrmappPermissions)
                    .filter(CrmappPermissions.type == 1)
                    .order_by(
                        CrmappPermissions.id.asc()
                    )
                    .all()
                )

                for r in rows:
                    all_perms.append({
                        'id': r.id,
                        'permission_name': r.permission_name,
                        'permission_code': r.permission_code,
                        'description': r.description,
                        'parent_permission_id': r.parent_permission_id,
                        'type': r.type,
                        'status': r.status,
                        'children': [],
                        'created_time': (
                            r.created_time.strftime('%Y-%m-%d %H:%M:%S')
                            if r.created_time else None  # pyright: ignore[reportGeneralTypeIssues]
                        ),
                        'updated_time': (
                            r.updated_time.strftime('%Y-%m-%d %H:%M:%S')
                            if r.updated_time else None  # pyright: ignore[reportGeneralTypeIssues]
                        ),
                    })

            id_map: Dict[int, Dict] = {p['id']: p for p in all_perms}
            roots: List[Dict] = []

            for perm in all_perms:
                parent_id = perm['parent_permission_id']
                if parent_id is None or parent_id not in id_map:
                    roots.append(perm)
                else:
                    id_map[parent_id]['children'].append(perm)

            return roots

        except Exception as e:
            print(f"[PermissionManagementService] 获取模块权限树失败: {str(e)}")
            return []

    @staticmethod
    def get_permission_tree() -> List[Dict]:
        """
        获取所有权限并按 parent_permission_id 构建多叉树。

        用于前端权限分配弹窗等需要树形展示的场景。

        构建逻辑：
        1. 查询所有权限，在 session 关闭前完成字段读取
        2. 以 parent_permission_id 作为父子关系键，构建任意层级的树
        3. parent_permission_id 为 null 或找不到对应父节点的作为根节点
        4. 找不到父节点且 type=2 的操作权限归入"其他"虚拟分组

        Returns:
            权限树列表，每个节点形如：
            {
                "id": 1,
                "permission_name": "...",
                "permission_code": "...",
                "parent_permission_id": null,
                "type": 1,
                "status": 1,
                "children": [ ... ]  # 无子节点时为 []
            }
        """
        try:
            all_perms: List[Dict] = []
            with orm_session() as session:
                rows = (
                    session.query(CrmappPermissions)
                    .order_by(
                        CrmappPermissions.type.asc(),
                        CrmappPermissions.id.asc()
                    )
                    .all()
                )

                # 在 session 关闭前完成字段读取，避免 lazy-load 失败
                for r in rows:
                    all_perms.append({
                        'id': r.id,
                        'permission_name': r.permission_name,
                        'permission_code': r.permission_code,
                        'parent_permission_id': r.parent_permission_id,
                        'type': r.type,
                        'status': r.status,
                        'children': [],
                    })

            # 建立 id -> 节点 快速索引
            id_map: Dict[int, Dict] = {p['id']: p for p in all_perms}

            roots: List[Dict] = []
            orphan_ops: List[Dict] = []  # 仅记录"操作权限且找不到父"的节点

            for perm in all_perms:
                parent_id = perm['parent_permission_id']
                if parent_id is None:
                    # 无父节点，作为根
                    roots.append(perm)
                elif parent_id in id_map:
                    # 找到真实父节点，挂到其 children 下
                    id_map[parent_id]['children'].append(perm)
                else:
                    # parent_permission_id 指向不存在的节点，做降级处理
                    if perm['type'] == 2:
                        # 操作权限：归入"其他"虚拟分组
                        orphan_ops.append(perm)
                    else:
                        # 模块/其他类型：作为根节点展示
                        roots.append(perm)

            # 如有孤立的操作权限，追加"其他"虚拟根节点
            if orphan_ops:
                roots.append({
                    'id': 0,
                    'permission_name': '其他',
                    'permission_code': 'module:other',
                    'parent_permission_id': None,
                    'type': 1,
                    'status': 1,
                    'children': orphan_ops,
                })

            return roots

        except Exception as e:
            print(f"[PermissionManagementService] 获取权限树失败: {str(e)}")
            return []

    # ======================================================================
    # 权限创建
    # ======================================================================

    @staticmethod
    def create_permission(permission_name: str, permission_code: str, description: str = '',
                          parent_permission_id: int = None, perm_type: int = 2,  # pyright: ignore[reportArgumentType]
                          status: int = 1) -> Tuple[bool, str, Optional[int]]:
        """
        创建新权限

        Args:
            permission_name: 权限名称
            permission_code: 权限编码（唯一）
            description: 权限描述
            parent_permission_id: 父权限ID（用于权限树）
            perm_type: 权限类型（1-模块权限，2-操作权限）
            status: 状态（0-禁用，1-启用）

        Returns:
            (是否成功, 消息, 新权限ID)
        """
        if not permission_name or not permission_code:
            return False, "权限名称和编码不能为空", None

        try:
            with orm_session() as session:
                # 检查 permission_code 是否已存在
                exists = (
                    session.query(CrmappPermissions.id)
                    .filter(CrmappPermissions.permission_code == permission_code)
                    .first()
                )
                if exists:
                    return False, f"权限编码 {permission_code} 已存在", None

                # 检查父权限是否存在
                if parent_permission_id:
                    parent = (
                        session.query(CrmappPermissions.id)
                        .filter(CrmappPermissions.id == parent_permission_id)
                        .first()
                    )
                    if not parent:
                        return False, "父权限不存在", None

                # 创建新权限
                new_perm = CrmappPermissions(
                    permission_name=permission_name,
                    permission_code=permission_code,
                    description=description,
                    parent_permission_id=parent_permission_id,
                    type=perm_type,
                    status=status,
                    created_time=datetime.now(),
                    updated_time=datetime.now(),
                )
                session.add(new_perm)
                session.flush()  # 拿到新生成的 id
                permission_id = new_perm.id

            PermissionService.clear_cache()
            return True, "创建成功", permission_id  # pyright: ignore[reportReturnType]

        except Exception as e:
            print(f"[PermissionManagementService] 创建权限失败: {str(e)}")
            return False, f"创建失败: {str(e)}", None

    # ======================================================================
    # 权限更新
    # ======================================================================

    @staticmethod
    def update_permission(permission_id: int, permission_name: str = None, permission_code: str = None,  # pyright: ignore[reportArgumentType]
                          description: str = None, parent_permission_id: int = None,  # pyright: ignore[reportArgumentType]
                          perm_type: int = None, status: int = None) -> Tuple[bool, str]:  # pyright: ignore[reportArgumentType]
        """
        更新权限信息

        Args:
            permission_id: 权限ID
            permission_name: 权限名称（可选）
            permission_code: 权限编码（可选）
            description: 权限描述（可选）
            parent_permission_id: 父权限ID（可选）
            perm_type: 权限类型（可选）
            status: 状态（可选）

        Returns:
            (是否成功, 消息)
        """
        if not permission_id:
            return False, "权限ID不能为空"

        try:
            with orm_session() as session:
                # 查询要更新的权限对象
                perm = (
                    session.query(CrmappPermissions)
                    .filter(CrmappPermissions.id == permission_id)
                    .first()
                )
                if not perm:
                    return False, "权限不存在"

                # 检查 permission_code 唯一性（如果要更新的话）
                if permission_code and permission_code != perm.permission_code:
                    code_exists = (
                        session.query(CrmappPermissions.id)
                        .filter(
                            CrmappPermissions.permission_code == permission_code,
                            CrmappPermissions.id != permission_id,
                        )
                        .first()
                    )
                    if code_exists:
                        return False, f"权限编码 {permission_code} 已存在"

                # 逐字段更新
                if permission_name is not None:
                    perm.permission_name = permission_name  # pyright: ignore[reportAttributeAccessIssue]
                if permission_code is not None:
                    perm.permission_code = permission_code  # pyright: ignore[reportAttributeAccessIssue]
                if description is not None:
                    perm.description = description  # pyright: ignore[reportAttributeAccessIssue]
                if parent_permission_id is not None:
                    perm.parent_permission_id = parent_permission_id  # pyright: ignore[reportAttributeAccessIssue]
                if perm_type is not None:
                    perm.type = perm_type  # pyright: ignore[reportAttributeAccessIssue]
                if status is not None:
                    perm.status = status  # pyright: ignore[reportAttributeAccessIssue]

                perm.updated_time = datetime.now()  # pyright: ignore[reportAttributeAccessIssue]

            PermissionService.clear_cache()
            return True, "更新成功"

        except Exception as e:
            print(f"[PermissionManagementService] 更新权限失败: permission_id={permission_id}, error={str(e)}")
            return False, f"更新失败: {str(e)}"

    # ======================================================================
    # 权限删除
    # ======================================================================

    @staticmethod
    def delete_permission(permission_id: int) -> Tuple[bool, str]:
        """
        删除权限

        注意：
        1. 检查是否有子权限引用该权限
        2. 检查是否有角色使用该权限
        3. 删除角色-权限关联

        Args:
            permission_id: 权限ID

        Returns:
            (是否成功, 消息)
        """
        if not permission_id:
            return False, "权限ID不能为空"

        try:
            with orm_session() as session:
                # 检查是否有子权限（parent_permission_id = permission_id）
                child_count = (
                    session.query(CrmappPermissions.id)
                    .filter(CrmappPermissions.parent_permission_id == permission_id)
                    .count()
                )
                if child_count > 0:
                    return False, "该权限存在子权限，无法删除"

                # 删除角色-权限关联
                session.query(CrmappRolePermissions).filter(
                    CrmappRolePermissions.permission_id == permission_id
                ).delete(synchronize_session=False)

                # 删除权限本身
                session.query(CrmappPermissions).filter(
                    CrmappPermissions.id == permission_id
                ).delete(synchronize_session=False)

            PermissionService.clear_cache()
            return True, "删除成功"

        except Exception as e:
            print(f"[PermissionManagementService] 删除权限失败: permission_id={permission_id}, error={str(e)}")
            return False, f"删除失败: {str(e)}"
