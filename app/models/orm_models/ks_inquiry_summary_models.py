# -*- coding:utf-8 -*-
# @Time    : 2026/09/02
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : ks_inquiry_summary_models.py
# @Software: trae-cn

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Date, Integer, BigInteger, UniqueConstraint, Index

from app.models.orm_models.base_models import BaseModels


class KsInquiryOeMonthlySummary(BaseModels):
    """
    OE军备统计月度汇总表 ORM模型

    对应数据库表：ks_inquiry_oe_monthly_summary
    按 自然月+门店+OE号+车辆品牌 预汇总 crmapp_ks_inquiry_detail 的询价统计数据，
    用于 OE军备统计 标签页的快速查询。
    """

    __tablename__ = "ks_inquiry_oe_monthly_summary"
    __table_args__ = (
        UniqueConstraint('summary_month', 'company', 'resolve_parts_num', 'car_brand_name', name='uk_summary'),
        Index('idx_month_company', 'summary_month', 'company'),
        Index('idx_oe', 'resolve_parts_num'),
        Index('idx_brand', 'car_brand_name'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False, comment="自增ID")
    summary_month = Column(Date, nullable=False, comment="自然月首日")
    company = Column(String(50), nullable=False, comment="门店/组织")
    resolve_parts_num = Column(String(100), nullable=False, comment="OE号")
    car_brand_name = Column(String(100), nullable=False, default='', comment="车辆品牌")
    parts_name = Column(String(255), nullable=True, comment="配件名称")
    inquiry_count = Column(Integer, nullable=False, default=0, comment="询价单数")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<KsInquiryOeMonthlySummary id={self.id} month={self.summary_month} oe={self.resolve_parts_num}>"


class KsInquiryCustomerByOeMonthlySummary(BaseModels):
    """
    OE客户统计月度汇总表 ORM模型

    对应数据库表：ks_inquiry_customer_by_oe_monthly_summary
    按 自然月+门店+OE号+客户名称 预汇总 crmapp_ks_inquiry_detail 的询价统计数据，
    用于 OE军备统计 标签页点击 OE 行后右侧客户统计副表的快速查询。
    """

    __tablename__ = "ks_inquiry_customer_by_oe_monthly_summary"
    __table_args__ = (
        UniqueConstraint('summary_month', 'company', 'resolve_parts_num', 'garage_company_name', name='uk_customer_summary'),
        Index('idx_month_oe', 'summary_month', 'company', 'resolve_parts_num'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False, comment="自增ID")
    summary_month = Column(Date, nullable=False, comment="自然月首日")
    company = Column(String(50), nullable=False, comment="门店/组织")
    resolve_parts_num = Column(String(100), nullable=False, comment="OE号")
    garage_company_name = Column(String(255), nullable=False, default='', comment="客户名称")
    inquiry_count = Column(Integer, nullable=False, default=0, comment="询价单数")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<KsInquiryCustomerByOeMonthlySummary id={self.id} month={self.summary_month} oe={self.resolve_parts_num} customer={self.garage_company_name}>"
