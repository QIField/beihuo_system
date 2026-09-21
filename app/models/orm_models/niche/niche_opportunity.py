# -*- coding:utf-8 -*-
"""
商机表（niche_opportunity）ORM 模型

对应数据库表：niche_opportunity
基于微信询价数据预计算的商机结果，每日全量刷新，以 (oe_code, stat_date) 为业务唯一键。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, DECIMAL, Index, UniqueConstraint

from app.models.orm_models.base_models import BaseModels


class NicheOpportunity(BaseModels):
    """
    商机表 ORM 模型

    对应数据库表：niche_opportunity
    从 wechat_daily_quote_detail 表聚合 OE 码维度的询价热度、缺货率、客户广度、需求趋势，
    结合 crmapp_beihuo 库存数据生成商机评分和补货建议，每日全量刷新。
    """

    __tablename__ = "niche_opportunity"
    __table_args__ = (
        UniqueConstraint('oe_code', 'stat_date', name='uk_oe_code_stat_date'),
        Index('idx_opportunity_level', 'opportunity_level'),
        Index('idx_out_of_stock_rate', 'out_of_stock_rate_30d'),
        Index('idx_opportunity_score', 'opportunity_score'),
        Index('idx_stat_date', 'stat_date'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")

    # 产品标识
    oe_code = Column(String(255), nullable=False, comment="OE码（产品标识）")
    part_name = Column(String(255), nullable=True, comment="配件名称（冗余，取最近一条询价记录）")
    brand_name = Column(String(255), nullable=True, comment="品牌名称（冗余，取最近一条询价记录）")

    # 询价统计（近30天）
    inquiry_count_30d = Column(Integer, nullable=True, default=0, comment="近30天询价次数")
    inquiry_count_prev_30d = Column(Integer, nullable=True, default=0, comment="上一个30天询价次数（用于趋势）")
    inquiry_trend_rate = Column(DECIMAL(6, 4), nullable=True, default=0.0000, comment="询价趋势增长率")
    out_of_stock_count_30d = Column(Integer, nullable=True, default=0, comment="近30天缺货次数")
    out_of_stock_rate_30d = Column(DECIMAL(5, 4), nullable=True, default=0.0000, comment="近30天缺货率")
    customer_count_30d = Column(Integer, nullable=True, default=0, comment="近30天询价客户数")

    # 商机评分（0~100）
    inquiry_score = Column(DECIMAL(6, 2), nullable=True, default=0.00, comment="询价热度分（0~100）")
    out_of_stock_score = Column(DECIMAL(6, 2), nullable=True, default=0.00, comment="缺货强度分（0~100）")
    customer_score = Column(DECIMAL(6, 2), nullable=True, default=0.00, comment="客户广度分（0~100）")
    trend_score = Column(DECIMAL(6, 2), nullable=True, default=0.00, comment="需求趋势分（0~100）")
    opportunity_score = Column(DECIMAL(6, 2), nullable=True, default=0.00, comment="综合商机评分（0~100）")
    opportunity_level = Column(String(10), nullable=True, comment="商机等级（S/A/B/C/D）")

    # 库存与补货建议
    available_stock = Column(Integer, nullable=True, default=0, comment="当前可用库存（来自 crmapp_beihuo）")
    transit_quantity = Column(Integer, nullable=True, default=0, comment="在途数量（来自 crmapp_beihuo）")
    suggested_stock_qty = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="建议备货量")
    replenish_suggestion = Column(Integer, nullable=True, default=0, comment="建议补货数量（0表示无需补货）")

    # OE 搜索日志维度
    search_count_30d = Column(Integer, nullable=True, default=0, comment="近30天OE搜索次数")
    search_count_prev_30d = Column(Integer, nullable=True, default=0, comment="上一个30天OE搜索次数")
    search_score = Column(DECIMAL(6, 2), nullable=True, default=0.00, comment="搜索热度分（0~100）")

    # 近7天询价次数（用于加权需求预测）
    inquiry_count_7d = Column(Integer, nullable=True, default=0, comment="近7天询价次数")

    # 统计日期与时间戳
    stat_date = Column(String(20), nullable=True, comment="统计日期，格式 YYYY-MM-DD")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    def __repr__(self):
        return f"<NicheOpportunity oe_code={self.oe_code} score={self.opportunity_score} level={self.opportunity_level}>"

    def to_dict(self):
        """将 ORM 对象转换为字典"""
        return {
            "id": self.id,
            "oe_code": self.oe_code,
            "part_name": self.part_name,
            "brand_name": self.brand_name,
            "inquiry_count_30d": self.inquiry_count_30d,
            "inquiry_count_prev_30d": self.inquiry_count_prev_30d,
            "inquiry_count_7d": self.inquiry_count_7d,
            "inquiry_trend_rate": float(self.inquiry_trend_rate) if self.inquiry_trend_rate is not None else None,  # pyright: ignore[reportArgumentType]
            "out_of_stock_count_30d": self.out_of_stock_count_30d,
            "out_of_stock_rate_30d": float(self.out_of_stock_rate_30d) if self.out_of_stock_rate_30d is not None else None,  # pyright: ignore[reportArgumentType]
            "customer_count_30d": self.customer_count_30d,
            "inquiry_score": float(self.inquiry_score) if self.inquiry_score is not None else None,  # pyright: ignore[reportArgumentType]
            "out_of_stock_score": float(self.out_of_stock_score) if self.out_of_stock_score is not None else None,  # pyright: ignore[reportArgumentType]
            "customer_score": float(self.customer_score) if self.customer_score is not None else None,  # pyright: ignore[reportArgumentType]
            "trend_score": float(self.trend_score) if self.trend_score is not None else None,  # pyright: ignore[reportArgumentType]
            "opportunity_score": float(self.opportunity_score) if self.opportunity_score is not None else None,  # pyright: ignore[reportArgumentType]
            "opportunity_level": self.opportunity_level,
            "available_stock": self.available_stock,
            "transit_quantity": self.transit_quantity,
            "suggested_stock_qty": float(self.suggested_stock_qty) if self.suggested_stock_qty is not None else None,  # pyright: ignore[reportArgumentType]
            "replenish_suggestion": self.replenish_suggestion,
            "search_count_30d": self.search_count_30d,
            "search_count_prev_30d": self.search_count_prev_30d,
            "search_score": float(self.search_score) if self.search_score is not None else None,  # pyright: ignore[reportArgumentType]
            "stat_date": self.stat_date,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
