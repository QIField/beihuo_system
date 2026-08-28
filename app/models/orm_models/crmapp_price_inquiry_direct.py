# -*- coding: utf-8 -*-
"""
询价直接入库数据表 ORM 模型
对应数据库表：crmapp_price_inquiry_direct
"""

from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, Text

from app.models.orm_models.base_models import BaseModels


class CrmappPriceInquiryDirect(BaseModels):
    """
    询价直接入库数据表
    用于存储跳过 B2B 推送直接入库的询价数据
    """
    __tablename__ = "crmapp_price_inquiry_direct"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    oe = Column(String(50), nullable=False, comment="OE号")
    brand = Column(String(100), comment="品牌")
    supplier = Column(String(200), comment="供应商")
    price = Column(DECIMAL(10, 2), comment="价格（加价后）")
    original_price = Column(DECIMAL(10, 2), comment="原始价格")
    markup_rate = Column(DECIMAL(6, 4), comment="加价率（倍数，如1.1表示加价10%）")
    markup_amount = Column(DECIMAL(10, 2), comment="加价金额（售价-原价）")
    warehouse = Column(String(200), comment="仓库")
    expire_time = Column(DateTime, comment="失效时间")
    remark = Column(Text, comment="备注")
    stock_quantity = Column(Integer, comment="库存数量")
    common_number = Column(String(500), comment="通用号")
    ks_sync = Column(Integer, comment="是否同步开思 0-否 1-是")
    company = Column(String(50), comment="公司")
    import_time = Column(DateTime, comment="导入时间")
    creator = Column(String(100), comment="导入人")
    matched_barcode = Column(String(255), comment="匹配条码")
    product_id = Column(String(100), comment="产品编号")
    source_file = Column(String(255), comment="来源文件名")
