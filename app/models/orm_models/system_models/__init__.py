# -*- coding:utf-8 -*-
# @Time    : 2026/06/09 18:15
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: trae-cn

from app.models.orm_models.system_models.crmapp_users import CrmappUsers
from app.models.orm_models.system_models.crmapp_roles import CrmappRoles
from app.models.orm_models.system_models.crmapp_permissions import CrmappPermissions
from app.models.orm_models.system_models.crmapp_user_roles import CrmappUserRoles
from app.models.orm_models.system_models.crmapp_role_permissions import CrmappRolePermissions

__all__ = [
    'CrmappUsers',
    'CrmappRoles',
    'CrmappPermissions',
    'CrmappUserRoles',
    'CrmappRolePermissions',
]
