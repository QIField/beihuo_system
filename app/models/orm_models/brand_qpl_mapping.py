# -*- coding:utf-8 -*-
"""
品牌与汽配龙品牌映射 ORM 模型
对应数据库表：brand_qpl_mapping
"""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, String

from app.models.orm_models.base_models import BaseModels


class BrandQplMapping(BaseModels):
    """
    品牌与汽配龙品牌映射表
    """

    __tablename__ = "brand_qpl_mapping"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增ID")
    data_brand = Column(String(100), nullable=False, unique=True, comment="数据原品牌")
    qpl_brand = Column(String(255), nullable=False, comment="汽配龙对应品牌")
    qpl_quality = Column(String(50), nullable=False, comment="汽配龙品质（国内品牌/国际品牌）")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )

    def to_dict(self):
        """
        将模型对象转换为字典
        """
        return {
            "id": self.id,
            "data_brand": self.data_brand,
            "qpl_brand": self.qpl_brand,
            "qpl_quality": self.qpl_quality,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    @classmethod
    def list_to_dict_list(cls, items):
        """
        对象列表转字典列表
        """
        return [item.to_dict() for item in items]
