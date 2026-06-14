# -*- coding:utf-8 -*-
# @Time    : 2026/6/9
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : crmapp_user_roles.py
# @Software: trae-cn
# @Description: 用户-角色关联表 ORM 模型（RBAC 用户角色关联层）

from sqlalchemy import Column, Integer, DateTime, SmallInteger, Index, UniqueConstraint
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CrmappUserRoles(BaseModels):
    """
    用户-角色关联表模型（RBAC 用户角色关联层）
    对应数据库表：crmapp_user_roles

    RBAC3 架构中的用户-角色关联表，用于建立用户与角色之间的多对多关系。
    一个用户可以拥有多个角色，一个角色可以分配给多个用户。

    设计说明：
    - 支持用户多角色：一个用户可以同时担任多个角色，权限取所有角色的并集
    - 支持角色有效期：通过 start_time 和 end_time 控制角色的生效时间
    - 支持临时角色：可通过有效期字段实现临时角色分配
    """
    __tablename__ = 'crmapp_user_roles'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 关联字段
    user_id = Column(Integer, nullable=False, comment='用户ID，关联 crmapp_users.id')
    role_id = Column(Integer, nullable=False, comment='角色ID，关联 crmapp_roles.id')

    # 角色有效期（用于临时角色分配）
    start_time = Column(DateTime, nullable=True, comment='角色生效时间，null表示立即生效')
    end_time = Column(DateTime, nullable=True, comment='角色失效时间，null表示永久有效')

    # 分配状态
    status = Column(SmallInteger, default=1, comment='分配状态 0-已禁用 1-生效中')

    # 时间字段
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 定义唯一约束与索引
    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='user_role_unique'),
        Index('idx_user_id', 'user_id'),
        Index('idx_role_id', 'role_id'),
        Index('idx_status', 'status'),
        Index('idx_time_range', 'start_time', 'end_time'),
        {
            'comment': '用户-角色关联表'
        }
    )

    def to_dict(self):
        """
        将用户角色关联对象转换为字典
        :return: 字典形式的关联数据
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'role_id': self.role_id,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else None,  # pyright: ignore[reportGeneralTypeIssues]
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else None,  # pyright: ignore[reportGeneralTypeIssues]
            'status': self.status,
            'created_time': self.created_time.strftime('%Y-%m-%d %H:%M:%S') if self.created_time else None,  # pyright: ignore[reportGeneralTypeIssues]
            'updated_time': self.updated_time.strftime('%Y-%m-%d %H:%M:%S') if self.updated_time else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
