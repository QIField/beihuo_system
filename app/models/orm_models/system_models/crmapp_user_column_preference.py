# -*- coding:utf-8 -*-
# @Project : beihuo_system
# @File    : crmapp_user_column_preference.py
# @Description: 用户表格列偏好配置 ORM 模型

from sqlalchemy import Column, Integer, String, DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CrmappUserColumnPreference(BaseModels):
    """
    用户表格列偏好配置表
    对应数据库表：crmapp_user_column_preference

    用于保存每个用户在不同页面、不同表格上的列状态（列宽、列顺序、显示/隐藏），
    实现刷新页面后按用户级别恢复表格列展示。
    """
    __tablename__ = 'crmapp_user_column_preference'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    # 关联字段
    user_id = Column(Integer, nullable=False, comment='用户ID，关联 crmapp_users.id')
    page_key = Column(String(64), nullable=False, comment='页面标识，如 ks_inquiry_records')
    grid_key = Column(String(64), nullable=False, comment='表格标识，如 detail_grid / oe_grid')

    # 列状态 JSON：AG Grid columnApi.getColumnState() 的结果
    column_state = Column(JSON, nullable=True, comment='AG Grid 列状态 JSON 数组')

    # 时间字段
    created_time = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    __table_args__ = (
        UniqueConstraint('user_id', 'page_key', 'grid_key', name='uk_user_page_grid'),
        Index('idx_user_id', 'user_id'),
        {
            'comment': '用户表格列偏好配置表'
        }
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'page_key': self.page_key,
            'grid_key': self.grid_key,
            'column_state': self.column_state,
            'created_time': self.created_time.strftime('%Y-%m-%d %H:%M:%S') if self.created_time else None,
            'updated_time': self.updated_time.strftime('%Y-%m-%d %H:%M:%S') if self.updated_time else None,
        }
