# -*- coding:utf-8 -*-
# @Time    : 2026/09/13
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_alias.py
# @Software: PyCharm


from sqlalchemy import Column, String, Text, Integer, DateTime
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CarPartsAlias(BaseModels):
    __tablename__ = 'car_parts_alias'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    part_number = Column(String(510), nullable=False, comment='配件编号')
    part_number_alias = Column(String(510), nullable=False, unique=True, comment='配件别名')
    remark = Column(Text, nullable=True, comment='备注')
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')

    def to_dict(self):
        """
        单个对象转字典
        :return: 字典形式的对象数据
        """
        return {
            'id': self.id,
            'part_number': self.part_number,
            'part_number_alias': self.part_number_alias,
            'remark': self.remark,
            'created_at': self.created_at
        }
