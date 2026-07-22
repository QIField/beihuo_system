# -*- coding:utf-8 -*-
"""
微信报价数据权限服务

提供用户群权限查询等功能。
"""

from typing import List, Dict

from app.utils.orm.session import orm_session
from app.models.orm_models.system_models import CrmappPermissions
from app.services.permission_service import PermissionService


VIEW_GROUP_PREFIX = 'wx_group:view_group'


def get_user_group_permissions(user_id: int) -> List[Dict[str, str]]:
    """
    获取用户拥有的群权限列表

    匹配 wx_group:view_group 前缀的权限，返回权限编码和对应的群名称。
    如果用户拥有 wx_group:view_group_all 权限，则返回所有群权限。

    Args:
        user_id: 用户ID

    Returns:
        权限列表，每项包含 permission_code 和 group_name
        [
            {"permission_code": "wx_group:view_group_f3", "group_name": "F3查询群"},
            ...
        ]
    """
    all_group_perms: List[Dict[str, str]] = []
    try:
        with orm_session() as session:
            rows = (
                session.query(
                    CrmappPermissions.permission_code,
                    CrmappPermissions.permission_name
                )
                .filter(
                    CrmappPermissions.permission_code.like(f'{VIEW_GROUP_PREFIX}%'),
                    CrmappPermissions.status == 1,
                )
                .order_by(CrmappPermissions.id.asc())
                .all()
            )
            for row in rows:
                all_group_perms.append({
                    'permission_code': row.permission_code,
                    'group_name': row.permission_name
                })
    except Exception as e:
        print(f"[get_user_group_permissions] 查询群权限失败: {str(e)}")
        return []

    user_permissions = PermissionService.get_user_permissions(user_id)

    view_all_perm = f'{VIEW_GROUP_PREFIX}_all'
    if view_all_perm in user_permissions:
        return all_group_perms

    result = []
    for perm in all_group_perms:
        if perm['permission_code'] in user_permissions:
            result.append(perm)

    return result
