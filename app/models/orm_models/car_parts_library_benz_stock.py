# -*- coding:utf-8 -*-
# @Time    : 2026/5/23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library_benz_stock.py
# @Software: PyCharm


from sqlalchemy import Column, String, Float, DateTime, BigInteger
from datetime import datetime
from sqlalchemy.dialects.mysql import insert

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

    @classmethod
    def bulk_upsert(cls, session, data_list):
        """
        批量插入或更新数据（以 part_number 和 warehouse 为组合主键）
        
        使用 SQLAlchemy 的 insert ... on_duplicate_key_update 方法
        底层调用 MySQL 的 INSERT ... ON DUPLICATE KEY UPDATE
        一次插入多条数据，性能更优

        :param session: SQLAlchemy Session 对象
        :param data_list: 数据字典列表
        :return: 处理的记录数
        """
        if not data_list:
            return 0

        # 构建插入语句
        stmt = insert(cls).values(data_list)

        # 构建更新字典：排除不需要更新的列
        update_dict = {}
        for column in cls.__table__.columns:
            col_name = column.name
            if col_name not in ['part_number', 'warehouse', 'created_at']:
                update_dict[col_name] = getattr(stmt.inserted, col_name)

        # 使用 on_duplicate_key_update
        stmt = stmt.on_duplicate_key_update(update_dict)

        # 执行批量插入
        session.execute(stmt)
        
        return len(data_list)
