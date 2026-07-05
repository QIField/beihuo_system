#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙报价记录表 ORM 模型
对应数据库表：qpl_quote_record
"""

from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, Text
from app.models.orm_models.base_models import BaseModels


class QplQuoteRecord(BaseModels):
    __tablename__ = 'qpl_quote_record'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    supplier_enquiry_no = Column(String(100), nullable=False, comment='询价单号')
    supplier_demand_id = Column(String(100), comment='需求ID')
    enquiry_item_id = Column(String(100), comment='询价产品ID')
    item_oe = Column(String(100), comment='OE号码')
    item_name = Column(String(255), comment='产品名称')
    item_description = Column(Text, comment='产品描述')
    brand_id = Column(String(100), comment='品牌ID')
    brand_name = Column(String(100), comment='品牌名称')
    item_sell_price = Column(DECIMAL(10, 2), comment='销售价格')
    delivery_aging = Column(Integer, comment='交货周期(天)')
    item_quality = Column(String(50), comment='产品品质')
    parts_no = Column(String(100), comment='零件号')
    quote_status = Column(String(50), comment='报价状态')
    submit_result = Column(String(255), comment='提交结果')
    result_source = Column(String(50), comment='报价来源/结果分类')
    submit_time = Column(DateTime, comment='提交时间')
    company = Column(String(100), comment='组织代码')
    created_time = Column(DateTime, comment='询价单创建时间')
    vin_code = Column(String(100), comment='VIN码')
    car_type = Column(Text, comment='车型信息')
    order_status = Column(String(50), comment='汽配龙产品报价状态（quoteStatusStr），如：已下单、已报价')
    created_at = Column(DateTime, server_default='CURRENT_TIMESTAMP', comment='创建时间')

    __table_args__ = {
        'mysql_charset': 'utf8mb4',
        'mysql_collate': 'utf8mb4_unicode_ci'
    }