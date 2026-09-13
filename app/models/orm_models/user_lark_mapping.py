# -*- coding:utf-8 -*-
"""
业务用户与飞书用户映射表
"""

from sqlalchemy import Column, BigInteger, String, DateTime, Integer, UniqueConstraint
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class UserLarkMapping(BaseModels):
    __tablename__ = 'user_lark_mapping'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, comment='业务系统用户ID')
    lark_open_id = Column(String(64), nullable=False, comment='飞书用户open_id')
    lark_union_id = Column(String(64), nullable=True, comment='飞书union_id')
    status = Column(Integer, nullable=False, default=1, comment='1有效 0无效')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('user_id', name='uk_user_id'),
        UniqueConstraint('lark_open_id', name='uk_lark_open_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'lark_open_id': self.lark_open_id,
            'lark_union_id': self.lark_union_id,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
