# -*- coding:utf-8 -*-
# @Time    : 2026/6/9
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : crmapp_roles.py
# @Software: trae-cn
# @Description: 角色表 ORM 模型（RBAC 角色层）

from sqlalchemy import Column, Integer, String, DateTime, SmallInteger, Text, Index, UniqueConstraint
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CrmappRoles(BaseModels):
    """
    角色表模型（RBAC 角色层）
    对应数据库表：crmapp_roles

    RBAC3 架构中的角色层，用于定义系统中的角色集合。
    角色作为权限的集合单位，用户通过分配角色来获得权限。

    角色层级关系说明：
    - 支持角色继承（通过 parent_role_id 字段实现）
    - 子角色会继承父角色的所有权限
    - 可构建多级角色树，如：超级管理员 -> 管理员 -> 部门主管 -> 普通用户
    """
    __tablename__ = 'crmapp_roles'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 角色基础信息
    role_name = Column(String(50), nullable=False, comment='角色名称，如：超级管理员、业务经理')
    role_code = Column(String(50), nullable=False, comment='角色编码，唯一标识，如：super_admin、business_manager')
    description = Column(String(255), nullable=True, comment='角色描述')

    # 角色层级关系（支持角色继承）
    parent_role_id = Column(Integer, nullable=True, comment='父角色ID，用于角色继承，null表示顶级角色')

    # 角色状态
    status = Column(SmallInteger, default=1, comment='角色状态 0-禁用 1-启用')

    # 时间字段
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 定义唯一约束与索引
    __table_args__ = (
        UniqueConstraint('role_code', name='role_code'),
        Index('idx_role_code', 'role_code'),
        Index('idx_parent_role_id', 'parent_role_id'),
        Index('idx_status', 'status'),
        {
            'comment': '角色表'
        }
    )

    def to_dict(self, include_hierarchy=False):
        """
        将角色对象转换为字典
        :param include_hierarchy: 是否包含层级关系信息，默认不包含
        :return: 字典形式的角色数据
        """
        result = {
            'id': self.id,
            'role_name': self.role_name,
            'role_code': self.role_code,
            'description': self.description,
            'status': self.status,
            'created_time': self.created_time.strftime('%Y-%m-%d %H:%M:%S') if self.created_time else None,  # pyright: ignore[reportGeneralTypeIssues]
            'updated_time': self.updated_time.strftime('%Y-%m-%d %H:%M:%S') if self.updated_time else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
        if include_hierarchy:
            result['parent_role_id'] = self.parent_role_id
        return result
