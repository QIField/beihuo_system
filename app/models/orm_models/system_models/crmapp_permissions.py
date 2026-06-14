# -*- coding:utf-8 -*-
# @Time    : 2026/6/9
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : crmapp_permissions.py
# @Software: trae-cn
# @Description: 权限表 ORM 模型（RBAC 权限层）

from sqlalchemy import Column, Integer, String, DateTime, SmallInteger, Text, Index, UniqueConstraint
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CrmappPermissions(BaseModels):
    """
    权限表模型（RBAC 权限层）
    对应数据库表：crmapp_permissions

    RBAC3 架构中的权限层，用于定义系统中的操作权限。
    权限是最细粒度的控制单元，代表某个具体的操作或资源访问权。

    权限编码规范：
    - 模块:操作:资源，如 cart:delete, order:process, inquiry:view
    - 支持通配符 *，如 *:* 表示所有权限，cart:* 表示购物车模块所有权限
    - 层级结构：通过 parent_permission_id 构建权限树，便于权限管理

    权限类型说明：
    - type=1: 模块权限，控制是否能访问某个模块
    - type=2: 操作权限，控制是否能执行某个具体操作（增删改查等）
    """
    __tablename__ = 'crmapp_permissions'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 权限基础信息
    permission_name = Column(String(100), nullable=False, comment='权限名称，如：删除购物车、处理单据')
    permission_code = Column(String(100), nullable=False, comment='权限编码，唯一标识，如：cart:delete, order:process')
    description = Column(String(255), nullable=True, comment='权限描述')

    # 权限层级关系
    parent_permission_id = Column(Integer, nullable=True, comment='父权限ID，用于构建权限树，null表示顶级权限')

    # 权限类型
    type = Column(SmallInteger, default=2, comment='权限类型 1-模块权限 2-操作权限')

    # 权限状态
    status = Column(SmallInteger, default=1, comment='权限状态 0-禁用 1-启用')

    # 时间字段
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 定义唯一约束与索引
    __table_args__ = (
        UniqueConstraint('permission_code', name='permission_code'),
        Index('idx_permission_code', 'permission_code'),
        Index('idx_parent_permission_id', 'parent_permission_id'),
        Index('idx_type', 'type'),
        Index('idx_status', 'status'),
        {
            'comment': '权限表'
        }
    )

    def to_dict(self, include_hierarchy=False):
        """
        将权限对象转换为字典
        :param include_hierarchy: 是否包含层级关系信息，默认不包含
        :return: 字典形式的权限数据
        """
        result = {
            'id': self.id,
            'permission_name': self.permission_name,
            'permission_code': self.permission_code,
            'description': self.description,
            'type': self.type,
            'status': self.status,
            'created_time': self.created_time.strftime('%Y-%m-%d %H:%M:%S') if self.created_time else None,  # pyright: ignore[reportGeneralTypeIssues]
            'updated_time': self.updated_time.strftime('%Y-%m-%d %H:%M:%S') if self.updated_time else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
        if include_hierarchy:
            result['parent_permission_id'] = self.parent_permission_id
        return result
