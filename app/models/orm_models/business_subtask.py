# -*- coding:utf-8 -*-
"""
业务子任务表
"""

from sqlalchemy import Column, BigInteger, String, DateTime, Integer
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class BusinessSubtask(BaseModels):
    __tablename__ = 'business_subtask'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, nullable=False, index=True, comment='父业务任务ID')
    title = Column(String(255), nullable=False, comment='子任务标题（飞书summary）')
    status = Column(Integer, nullable=False, default=0, comment='0未完成 1已完成')
    sort_order = Column(Integer, nullable=False, default=0, comment='清单内排序')
    lark_subtask_guid = Column(String(64), nullable=True, unique=True, comment='飞书子任务GUID')
    completed_at = Column(DateTime, nullable=True, comment='完成时间')
    created_by = Column(BigInteger, nullable=True, comment='创建人ID')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'title': self.title,
            'status': self.status,
            'sort_order': self.sort_order,
            'lark_subtask_guid': self.lark_subtask_guid,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M:%S') if self.completed_at else None,
            'created_by': self.created_by,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
