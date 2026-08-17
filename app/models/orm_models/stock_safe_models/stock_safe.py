# -*- coding:utf-8 -*-
# @Time    : 2026/08/08
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe.py
# @Software: trae-cn

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, DECIMAL, Index, UniqueConstraint
from app.models.orm_models.base_models import BaseModels


class StockSafe(BaseModels):
    """
    安全库存表 ORM模型

    对应数据库表：stock_safe
    存储安全库存计算结果与库存状态，供前端展示和Excel报表导出。
    采用预计算存储模式（每日定时任务刷新），以 (number, brand_name, frey_no) 为业务唯一键。
    available_stock 从 crmapp_beihuo 表获取，使用三字段匹配。
    """

    __tablename__ = "stock_safe"
    __table_args__ = (
        UniqueConstraint('number', 'brand_name', 'frey_no', name='uk_number_brand_frey'),
        Index('idx_abc_classification', 'abc_classification'),
        Index('idx_stock_status', 'stock_status'),
        Index('idx_brand_name', 'brand_name'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    number = Column(String(255), nullable=False, comment="OE号，关联销量表")
    brand_name = Column(String(255), nullable=False, comment="品牌名，与number共同唯一")
    frey_no = Column(String(255), nullable=False, comment="条码，与number、brand_name共同唯一")
    pdname = Column(String(255), nullable=True, comment="产品名称（冗余）")

    abc_classification = Column(String(1), nullable=True, comment="ABC分类（A/B/C），决定Z系数与覆盖天数")
    avg_daily_sales = Column(DECIMAL(12, 2), nullable=True, default=0.00, comment="平均日销量（从销量表同步）")
    base_safety_stock = Column(DECIMAL(12, 2), nullable=True, default=0.00, comment="基础安全库存：Z系数 × 销量标准差 × 补货周期")
    season_coefficient = Column(DECIMAL(4, 2), nullable=True, default=1.00, comment="季节系数（范围0.7~1.3）")
    safety_stock = Column(DECIMAL(12, 2), nullable=True, default=0.00, comment="调整后安全库存：基础安全库存 × 季节系数")
    stock_lower_limit = Column(DECIMAL(12, 2), nullable=True, default=0.00, comment="库存下限：平均日销量 × 补货周期 + 安全库存")
    stock_upper_limit = Column(DECIMAL(12, 2), nullable=True, default=0.00, comment="库存上限：平均日销量 × (补货周期 + 覆盖天数) + 安全库存")

    available_stock = Column(Integer, nullable=True, default=0, comment="可用库存：每日快照从crmapp_beihuo表获取，使用number+brand_name+frey_no匹配")
    transit_quantity = Column(Integer, nullable=True, default=0, comment="在途数量：从crmapp_beihuo表同步")
    sellable_days = Column(DECIMAL(12, 2), nullable=True, default=0.00, comment="可卖天数：可用库存 / 平均日销量")

    stock_status = Column(String(20), nullable=True, default='正常', comment="库存状态：呆滞清库/慢动销去库/紧急补货/需补货/库存积压/正常")

    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    def __repr__(self):
        return f"<StockSafe number={self.number} brand={self.brand_name} frey={self.frey_no}>"

    def to_dict(self):
        """将ORM对象转换为字典"""
        return {
            "id": self.id,
            "number": self.number,
            "brand_name": self.brand_name,
            "frey_no": self.frey_no,
            "pdname": self.pdname,
            "abc_classification": self.abc_classification,
            "avg_daily_sales": float(self.avg_daily_sales) if self.avg_daily_sales is not None else None,
            "base_safety_stock": float(self.base_safety_stock) if self.base_safety_stock is not None else None,
            "season_coefficient": float(self.season_coefficient) if self.season_coefficient is not None else None,
            "safety_stock": float(self.safety_stock) if self.safety_stock is not None else None,
            "stock_lower_limit": float(self.stock_lower_limit) if self.stock_lower_limit is not None else None,
            "stock_upper_limit": float(self.stock_upper_limit) if self.stock_upper_limit is not None else None,
            "available_stock": self.available_stock,
            "transit_quantity": self.transit_quantity,
            "sellable_days": float(self.sellable_days) if self.sellable_days is not None else None,
            "stock_status": self.stock_status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }