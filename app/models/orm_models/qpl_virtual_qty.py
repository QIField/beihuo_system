#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙虚拟库存采集数据 ORM 模型
对应数据库表：qpl_virtual_qty
"""

from sqlalchemy import Column, Integer, String, Text
from .base_models import BaseModels


class QplVirtualQty(BaseModels):
    """
    汽配龙虚拟库存采集数据
    """

    __tablename__ = "qpl_virtual_qty"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    spider_date = Column(String(255), nullable=True, comment="采集日期")
    ys_oe1 = Column(String(255), nullable=True, comment="OE")
    update = Column(String(255), nullable=True, comment="更新时间")
    product_name1 = Column(String(255), nullable=True, comment="零件名称")
    brand_name1 = Column(String(255), nullable=True, comment="品质")
    seller_name1 = Column(String(255), nullable=True, comment="供应商名称")
    price1 = Column(String(255), nullable=True, comment="价格")
    quantity1 = Column(String(255), nullable=True, comment="库存")
    city_name = Column(String(255), nullable=True, comment="地区")
    pp = Column(String(255), nullable=True, comment="对应开思要求的品牌")
    merchant_code = Column(String(255), nullable=True, comment="条码")
    cpd_original_brand = Column(String(255), nullable=True, comment="对应原厂品牌")
    cpd_original_part_number = Column(String(255), nullable=True, comment="对应原厂零件号")
    no_mark_up = Column(String(255), nullable=True, comment="未加价")
    Increased_price = Column(String(255), nullable=True, comment="已加价")
    number_of_suppliers = Column(String(255), nullable=True, comment="供应商个数")
    number_of_inventories = Column(String(255), nullable=True, comment="总库存")
    make_vehicle1 = Column(Text, nullable=True, comment="备注")
    is_cassmall = Column(String(255), nullable=True, comment="上传开思的数据")
    brand_id = Column(Integer, nullable=True, comment="中台品牌ID")
    l_name_zh = Column(String(255), nullable=True, comment="中台品牌名称")
    company_id = Column(Integer, nullable=True, comment="中台公司id")
    reference_price = Column(String(10), nullable=True, comment="参考加价")

    def __repr__(self):
        return f"<QplVirtualQty {self.ys_oe1} - {self.merchant_code}>"
