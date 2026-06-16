# -*- coding:utf-8 -*-
# @Time    : 2026/05/26
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_favorite.py
# @Software: PyCharm


from sqlalchemy import Column, String, Integer, DateTime, UniqueConstraint
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CarPartsFavorite(BaseModels):
    __tablename__ = 'car_parts_favorite'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    user_id = Column(Integer, nullable=True, comment='收藏人/操作人用户ID')
    part_number = Column(String(510), nullable=False, comment='配件编号')
    category = Column(String(100), nullable=False, default='主收藏', comment='分类')
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')

    # 唯一约束：同一个配件在同一分类下只能收藏一次（全局共享，不区分用户）
    __table_args__ = (
        UniqueConstraint('part_number', 'category', name='uq_part_category'),
    )

    def to_dict(self):
        """
        单个对象转字典
        :return: 字典形式的对象数据
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'part_number': self.part_number,
            'category': self.category,
            'created_at': self.created_at
        }
