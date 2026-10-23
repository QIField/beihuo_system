# -*- coding:utf-8 -*-
"""
个人记事本表
"""

from sqlalchemy import Column, BigInteger, Integer, String, DateTime, Text
from datetime import datetime

from app.models.orm_models.base_models import BaseModels

# sqlite 内存库（单测）不支持 BIGINT 主键自增，用 Integer 变体兼容，MySQL 侧仍为 BIGINT
BigIntPk = BigInteger().with_variant(Integer, 'sqlite')


class NotepadNote(BaseModels):
    __tablename__ = 'crmapp_notepad'

    id = Column(BigIntPk, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True, comment='所属用户ID（数据隔离键）')
    username = Column(String(64), nullable=True, comment='创建人用户名（冗余展示用）')
    title = Column(String(50), nullable=True, comment='标题，选填')
    content = Column(Text, nullable=False, comment='笔记内容')
    created_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    updated_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'created_time': self.created_time.strftime('%Y-%m-%d %H:%M') if self.created_time else None,
            'updated_time': self.updated_time.strftime('%Y-%m-%d %H:%M') if self.updated_time else None,
        }
