# -*- coding:utf-8 -*-
"""
物料在途库存快照表 ORM 模型

数据来源：B2B 开放平台 Product.ProductStock/getInTransitStockList
每次同步成功后全量重建（物理删除旧快照），表内数据即"当前在途"。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Date, Numeric, UniqueConstraint, Index

from app.models.orm_models.base_models import BaseModels


class B2bIntransitStock(BaseModels):
    """
    物料在途库存明细表

    对应数据库表：b2b_intransit_stock
    """
    __tablename__ = "b2b_intransit_stock"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    company = Column(String(50), nullable=False, comment="公司代码(fsbbr/zhbbr/zsbbr/dgby/dghf)")
    product_id = Column(Integer, nullable=False, comment="产品ID")
    frey_no = Column(String(100), nullable=True, comment="物料编码/条码")
    oe_number = Column(String(100), nullable=True, comment="OE号")
    product_name = Column(String(255), nullable=True, comment="产品名称")
    order_no = Column(String(100), nullable=False, comment="采购单号")
    supplier_name = Column(String(255), nullable=True, comment="供应商名称")
    purchase_quantity = Column(Integer, nullable=True, comment="在途采购数量")
    price = Column(Numeric(12, 2), nullable=True, comment="采购单价")
    order_date = Column(Date, nullable=True, comment="下单日期")
    expected_delivery_date = Column(Date, nullable=True, comment="预计到货日期")
    warehouse_name = Column(String(100), nullable=True, comment="收货仓库名称")
    sync_time = Column(DateTime, nullable=True, comment="本次同步时间")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        UniqueConstraint('company', 'order_no', 'product_id', name='uk_company_order_product'),
        Index('idx_product_id', 'product_id'),
        Index('idx_company', 'company'),
    )
