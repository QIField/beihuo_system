# -*- coding:utf-8 -*-
"""
业务任务主表
"""

from sqlalchemy import Column, BigInteger, String, Text, DateTime, Integer
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class BusinessTask(BaseModels):
    __tablename__ = 'business_task'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False, comment='任务标题')
    content = Column(Text, nullable=True, comment='任务内容')
    assignee_id = Column(BigInteger, nullable=False, comment='负责人ID')
    status = Column(Integer, nullable=False, default=0, comment='0未完成 1已完成')
    start_time = Column(DateTime, nullable=True, default=datetime.now, comment='开始时间')
    deadline = Column(DateTime, nullable=True, comment='截止时间')
    created_by = Column(BigInteger, nullable=True, comment='创建人ID')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'assignee_id': self.assignee_id,
            'status': self.status,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else None,
            'deadline': self.deadline.strftime('%Y-%m-%d %H:%M:%S') if self.deadline else None,
            'created_by': self.created_by,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
