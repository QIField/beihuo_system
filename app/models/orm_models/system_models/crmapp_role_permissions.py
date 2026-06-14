# -*- coding:utf-8 -*-
# @Time    : 2026/6/9
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : crmapp_role_permissions.py
# @Software: trae-cn
# @Description: 角色-权限关联表 ORM 模型（RBAC 角色权限关联层）

from sqlalchemy import Column, Integer, DateTime, SmallInteger, Index, UniqueConstraint
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CrmappRolePermissions(BaseModels):
    """
    角色-权限关联表模型（RBAC 角色权限关联层）
    对应数据库表：crmapp_role_permissions

    RBAC3 架构中的角色-权限关联表，用于建立角色与权限之间的多对多关系。
    一个角色可以拥有多个权限，一个权限可以分配给多个角色。

    设计说明：
    - 支持角色多权限：一个角色可以包含多个操作权限
    - 支持权限继承：子角色会自动继承父角色的所有权限（业务层实现）
    - 支持权限排除：可通过 exclude 字段实现权限的显式排除（预留扩展）
    """
    __tablename__ = 'crmapp_role_permissions'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 关联字段
    role_id = Column(Integer, nullable=False, comment='角色ID，关联 crmapp_roles.id')
    permission_id = Column(Integer, nullable=False, comment='权限ID，关联 crmapp_permissions.id')

    # 权限状态
    status = Column(SmallInteger, default=1, comment='权限分配状态 0-已禁用 1-生效中')

    # 时间字段
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 定义唯一约束与索引
    __table_args__ = (
        UniqueConstraint('role_id', 'permission_id', name='role_permission_unique'),
        Index('idx_role_id', 'role_id'),
        Index('idx_permission_id', 'permission_id'),
        Index('idx_status', 'status'),
        {
            'comment': '角色-权限关联表'
        }
    )

    def to_dict(self):
        """
        将角色权限关联对象转换为字典
        :return: 字典形式的关联数据
        """
        return {
            'id': self.id,
            'role_id': self.role_id,
            'permission_id': self.permission_id,
            'status': self.status,
            'created_time': self.created_time.strftime('%Y-%m-%d %H:%M:%S') if self.created_time else None,  # pyright: ignore[reportGeneralTypeIssues]
            'updated_time': self.updated_time.strftime('%Y-%m-%d %H:%M:%S') if self.updated_time else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
