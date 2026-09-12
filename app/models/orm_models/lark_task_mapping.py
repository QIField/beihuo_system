# -*- coding:utf-8 -*-
"""
业务任务与飞书任务映射表
"""

from sqlalchemy import Column, BigInteger, String, DateTime, Integer, UniqueConstraint
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class LarkTaskMapping(BaseModels):
    __tablename__ = 'lark_task_mapping'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    business_id = Column(BigInteger, nullable=False, comment='业务任务ID')
    business_type = Column(String(32), nullable=False, default='business_task', comment='业务任务类型')
    lark_task_guid = Column(String(64), nullable=False, comment='飞书任务GUID')
    lark_summary = Column(String(255), nullable=True, comment='飞书任务标题快照')
    owner_open_id = Column(String(64), nullable=True, comment='负责人飞书open_id')
    status = Column(Integer, nullable=False, default=1, comment='1有效 0无效')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('business_id', 'business_type', name='uk_business'),
        UniqueConstraint('lark_task_guid', name='uk_lark_guid'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'business_id': self.business_id,
            'business_type': self.business_type,
            'lark_task_guid': self.lark_task_guid,
            'lark_summary': self.lark_summary,
            'owner_open_id': self.owner_open_id,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
