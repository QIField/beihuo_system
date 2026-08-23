# -*- coding:utf-8 -*-
# @Time    : 2026/08/04
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : oe_parts_sales.py
# @Software: trae-cn

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Date, BigInteger, DECIMAL, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON

from app.models.orm_models.base_models import BaseModels


class OePartsSales(BaseModels):
    """
    OE零件销量统计表 ORM模型

    对应数据库表：oe_parts_sales
    按OE号汇总的日/月/年销量数据，为安全库存计算提供基础数据支撑。
    包含近一年平均日销量、平均月销量、年总销量、今年销量、上一年销量及销量标准差。
    sales_std_dev_1y 基于近52周周销量计算（周标准差 σ_w），用于安全库存公式 SS = Z × σ_w × √(L/7)。
    monthly_sales_json字段存储近12个月各月销量JSON，用于季节系数计算。
    weekly_sales_json字段存储近52周各周销量JSON，用于周标准差原始数据追溯。
    以 (number, brand_name, frey_no) 为业务唯一键。
    """

    __tablename__ = "oe_parts_sales"
    __table_args__ = (
        UniqueConstraint('number', 'brand_name', 'frey_no', name='uk_number_brand_frey'),
        Index('idx_brand_name', 'brand_name'),
        Index('idx_frey_no', 'frey_no'),
        Index('idx_stat_date', 'stat_date'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    number = Column(String(255), nullable=False, comment="OE号（即sales_order_history表number字段）：零件唯一标识")
    brand_name = Column(String(255), nullable=True, comment="品牌名")
    pdname = Column(String(255), nullable=True, comment="产品名称（即sales_order_history表pdname字段）")
    frey_no = Column(String(255), nullable=False, comment="条码（即sales_order_history表frey_no字段），与number、brand_name共同唯一标识")

    avg_daily_sales_1y = Column(DECIMAL(12, 3), nullable=True, default=0.000, comment="日销量（近一年数据）：近一年平均日销量 = 近一年总销量 / 365，单位：个")
    avg_monthly_sales_1y = Column(DECIMAL(12, 3), nullable=True, default=0.000, comment="月销量（近一年数据）：近一年平均月销量 = 近一年总销量 / 12，单位：个")
    annual_sales_1y = Column(Integer, nullable=True, default=0, comment="年销量（近一年数据）：近一年（过去365天）总销量，单位：个")
    sales_this_year = Column(Integer, nullable=True, default=0, comment="今年销量：当前自然年（1月1日至统计日）总销量，单位：个")
    sales_last_year = Column(Integer, nullable=True, default=0, comment="上一年销量：上一个完整自然年总销量，单位：个")

    sales_std_dev_1y = Column(DECIMAL(12, 3), nullable=True, default=0.000, comment="近一年销量标准差（周标准差 σ_w）：基于近52周各周净销量计算，用于基础安全库存公式 SS = Z × σ_w × √(L/7)，其中 σ_w 为周销量总体标准差（ddof=0）")

    monthly_sales_json = Column(JSON, nullable=True, comment="近12个月各月销量JSON：格式{\"YYYY-MM\": 数量, ...}，用于计算季节系数（当月销量/全年平均月销量），范围限制0.7~1.3")

    weekly_sales_json = Column(JSON, nullable=True, comment="近52周各周销量JSON：格式{\"YYYY-MM-DD\": 数量, ...}，键为周起始日期，用于安全库存计算中的周标准差原始数据追溯")

    stat_date = Column(Date, nullable=True, comment="统计日期：数据统计的时间点，标识这批销量数据的截止日期")

    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    def __repr__(self):
        return f"<OePartsSales id={self.id} number={self.number}>"

    def to_dict(self):
        """将ORM对象转换为字典"""
        return {
            "id": self.id,
            "number": self.number,
            "brand_name": self.brand_name,
            "pdname": self.pdname,
            "frey_no": self.frey_no,
            "avg_daily_sales_1y": float(self.avg_daily_sales_1y) if self.avg_daily_sales_1y is not None else None,  # pyright: ignore[reportArgumentType]
            "avg_monthly_sales_1y": float(self.avg_monthly_sales_1y) if self.avg_monthly_sales_1y is not None else None,  # pyright: ignore[reportArgumentType]
            "annual_sales_1y": self.annual_sales_1y,
            "sales_this_year": self.sales_this_year,
            "sales_last_year": self.sales_last_year,
            "sales_std_dev_1y": float(self.sales_std_dev_1y) if self.sales_std_dev_1y is not None else None,  # pyright: ignore[reportArgumentType]
            "monthly_sales_json": self.monthly_sales_json,
            "weekly_sales_json": self.weekly_sales_json,
            "stat_date": self.stat_date.strftime("%Y-%m-%d") if self.stat_date else None,  # pyright: ignore[reportGeneralTypeIssues]
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }