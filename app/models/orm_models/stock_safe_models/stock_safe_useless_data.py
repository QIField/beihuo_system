# -*- coding:utf-8 -*-
# @Time    : 2026/08/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_useless_data.py
# @Software: trae-cn

from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, UniqueConstraint

from app.models.orm_models.base_models import BaseModels


class StockSafeUselessData(BaseModels):
    """
    安全库存无效数据记录表 ORM模型

    对应数据库表：stock_safe_useless_data
    用于记录在安全库存计算/处理流程中判定为无效、需要排除的零件数据。
    典型场景：数据缺失、格式异常、长期无销售且库存异常等被人工或算法标记的记录。
    以 (number, brand_name, pdname) 为业务唯一键，frey_no 单独唯一，避免重复插入同一条无效记录。
    """

    __tablename__ = "stock_safe_useless_data"
    __table_args__ = (
        # 联合唯一索引：number + brand_name + pdname 三字段共同唯一
        UniqueConstraint('number', 'brand_name', 'pdname', name='uk_number_brand_pdname'),
        # 唯一索引：条码单独唯一
        UniqueConstraint('frey_no', name='uk_frey_no'),
        # TODO: frey_no 字段当前为必填，如业务允许条码缺失，需调整唯一约束以兼容 NULL
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    number = Column(String(255), nullable=False, comment="OE号，零件唯一标识")
    brand_name = Column(String(255), nullable=False, comment="品牌名，与number、frey_no共同唯一")
    frey_no = Column(String(255), nullable=False, comment="条码，与number、brand_name共同唯一")
    pdname = Column(String(255), nullable=True, comment="产品名称（冗余存储，便于查阅）")

    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    def __repr__(self):
        return f"<StockSafeUselessData id={self.id} number={self.number} brand={self.brand_name} frey={self.frey_no}>"

    def to_dict(self):
        """将ORM对象转换为字典"""
        return {
            "id": self.id,
            "number": self.number,
            "brand_name": self.brand_name,
            "frey_no": self.frey_no,
            "pdname": self.pdname,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
