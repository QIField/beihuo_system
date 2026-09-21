# -*- coding:utf-8 -*-
"""
OE搜索日志表（oe_search_log）ORM 模型

对应数据库表：oe_search_log
存储 CRM 系统中 Product.Product/oeSearchLog 接口返回的 OE 码搜索记录。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Index, UniqueConstraint

from app.models.orm_models.base_models import BaseModels


class OeSearchLog(BaseModels):
    """
    OE搜索日志表 ORM 模型

    对应数据库表：oe_search_log
    用于分析 OE 搜索热度、用户搜索行为等。
    """

    __tablename__ = "oe_search_log"
    __table_args__ = (
        UniqueConstraint('source_biz_id', name='uk_source_biz_id'),
        Index('idx_search_date', 'search_date'),
        Index('idx_oe_number', 'oe_number'),
        Index('idx_search_time', 'search_time'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")

    # 来源追溯
    source_biz_id = Column(String(128), nullable=False, comment="源业务记录ID（CRM日志id）")

    # 产品信息
    brand_name = Column(String(255), nullable=True, comment="品牌名称")
    product_name = Column(String(255), nullable=True, comment="产品名称")
    oe_number = Column(String(255), nullable=True, comment="OE号")
    num = Column(Integer, nullable=True, default=0, comment="搜索结果数量/相关数量")

    # 时间
    search_time = Column(DateTime, nullable=True, comment="搜索发生时间（CRM返回）")
    search_date = Column(String(20), nullable=True, comment="搜索日期（YYYY-MM-DD，冗余方便按天统计）")

    # 时间戳
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    def __repr__(self):
        return f"<OeSearchLog id={self.source_biz_id} oe={self.oe_number}>"

    def to_dict(self):
        """将 ORM 对象转换为字典"""
        return {
            "id": self.id,
            "source_biz_id": self.source_biz_id,
            "brand_name": self.brand_name,
            "product_name": self.product_name,
            "oe_number": self.oe_number,
            "num": self.num,
            "search_time": self.search_time.strftime("%Y-%m-%d %H:%M:%S") if self.search_time else None,
            "search_date": self.search_date,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
