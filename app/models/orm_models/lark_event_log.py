# -*- coding:utf-8 -*-
"""
飞书回调事件幂等日志表
"""

from sqlalchemy import Column, BigInteger, String, DateTime, UniqueConstraint
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class LarkEventLog(BaseModels):
    __tablename__ = 'lark_event_log'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(64), nullable=False, comment='飞书事件唯一ID')
    event_type = Column(String(64), nullable=False, comment='事件类型')
    event_time = Column(BigInteger, nullable=False, comment='飞书事件时间戳')
    handled_at = Column(DateTime, nullable=False, default=datetime.now, comment='处理时间')

    __table_args__ = (
        UniqueConstraint('event_id', name='uk_event_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'event_type': self.event_type,
            'event_time': self.event_time,
            'handled_at': self.handled_at.strftime('%Y-%m-%d %H:%M:%S') if self.handled_at else None,
        }
