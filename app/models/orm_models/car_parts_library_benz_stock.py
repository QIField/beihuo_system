# -*- coding:utf-8 -*-
# @Time    : 2026/5/23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library_benz_stock.py
# @Software: PyCharm


from sqlalchemy import Column, String, Float, DateTime, BigInteger
from datetime import datetime

from app.models.orm_models.base_models import BaseModels


class CarPartsLibraryBenzStock(BaseModels):
    __tablename__ = 'car_parts_library_benz_stock'

    # 主键 - 使用组合主键
    part_number = Column(String(510), primary_key=True, comment='配件编号')
    warehouse = Column(String(100), primary_key=True, comment='仓库代码')

    # 库存信息
    description = Column(String(510), nullable=True, comment='零件描述')
    quantity_available = Column(BigInteger, nullable=True, comment='可用数量')
    unit = Column(String(50), nullable=True, comment='单位')

    # 时间字段
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def to_dict(self):
        """
        单个对象转字典
        :return: 字典形式的对象数据
        """
        return {
            'part_number': self.part_number,
            'warehouse': self.warehouse,
            'description': self.description,
            'quantity_available': self.quantity_available,
            'unit': self.unit,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

