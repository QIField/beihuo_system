# -*- coding:utf-8 -*-
# @Time    : 2026/09/13
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : benz_error_oe.py
# @Software: PyCharm


from sqlalchemy import Column, Text, Integer, DateTime
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class BenzErrorOe(BaseModels):
    __tablename__ = 'benz_error_oe'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    oe = Column(Text, nullable=False, comment='OE编号')
    status = Column(Integer, nullable=False, default=0, comment='状态：是否已入别名库，0-未入 1-已入')
    remark = Column(Text, nullable=True, comment='备注')
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')

    def to_dict(self):
        """
        单个对象转字典
        :return: 字典形式的对象数据
        """
        return {
            'id': self.id,
            'oe': self.oe,
            'status': self.status,
            'remark': self.remark,
            'created_at': self.created_at
        }
