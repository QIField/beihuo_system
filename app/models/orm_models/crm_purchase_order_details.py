# -*- coding:utf-8 -*-
# @Time    : 2026/6/7
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crm_purchase_order_details.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, Text, Numeric, text
from sqlalchemy.dialects.mysql import insert

from .base_models import BaseModels


class CrmPurchaseOrderDetails(BaseModels):
    """
    采购订单明细表 ORM 模型
    
    对应数据库表：crm_purchase_order_details
    """
    
    __tablename__ = "crm_purchase_order_details"

    purchase_order_line_id = Column(BigInteger, primary_key=True, nullable=False, comment="订单明细ID")
    purchase_order_id = Column(BigInteger, nullable=True, comment="采购订单ID")
    no = Column(Integer, nullable=True, comment="明细序号")
    product_id = Column(BigInteger, nullable=True, comment="产品ID")
    number = Column(String(100), nullable=True, comment="产品编号")
    l_model_zh = Column(Text, nullable=True, comment="适用车型")
    brand = Column(String(100), nullable=True, comment="品牌名称")
    l_name_zh = Column(String(255), nullable=True, comment="产品名称")
    brand_code = Column(String(100), nullable=True, comment="品牌代码")
    frey_no = Column(String(100), nullable=True, comment="Frey编号")
    user_code = Column(String(100), nullable=True, comment="用户编码")
    unit = Column(String(20), nullable=True, comment="单位")
    purchase_quantity = Column(Numeric(12, 2), nullable=True, comment="采购数量")
    price = Column(Numeric(12, 2), nullable=True, comment="单价")
    amount_money = Column(Numeric(12, 2), nullable=True, comment="金额小计")
    unit_cost = Column(Numeric(12, 2), nullable=True, comment="单位成本")
    received_quantity = Column(Numeric(12, 2), nullable=True, comment="已收货数量")
    gift = Column(Integer, nullable=True, comment="是否赠品")
    shipping_fee = Column(Numeric(10, 2), nullable=True, comment="运费")
    unit_shipping_fee = Column(Numeric(10, 2), nullable=True, comment="单位运费")
    packing_fee = Column(Numeric(10, 2), nullable=True, comment="包装费")
    unit_packing_fee = Column(Numeric(10, 2), nullable=True, comment="单位包装费")
    delivery_date = Column(String(255), nullable=True, comment="交货日期")
    company_remark = Column(Text, nullable=True, comment="公司备注")
    is_unsalable = Column(Integer, nullable=True, comment="是否滞销")
    ks_price = Column(String(50), nullable=True, comment="开思价")
    store = Column(String(50), nullable=True, comment="门店")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")
    operator = Column(String(255), nullable=True, comment="操作人")
    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<CrmPurchaseOrderDetails purchase_order_line_id={self.purchase_order_line_id} product_id={self.product_id}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        Numeric 类型会转换为 float
        
        :return: 包含所有字段的字典
        """
        return {
            "detail_purchase_order_line_id": self.purchase_order_line_id,
            "detail_purchase_order_id": self.purchase_order_id,
            "detail_no": self.no,
            "detail_product_id": self.product_id,
            "detail_number": self.number,
            "detail_l_model_zh": self.l_model_zh,
            "detail_brand": self.brand,
            "detail_l_name_zh": self.l_name_zh,
            "detail_brand_code": self.brand_code,
            "detail_frey_no": self.frey_no,
            "detail_user_code": self.user_code,
            "detail_unit": self.unit,
            "detail_purchase_quantity": self.purchase_quantity,
            "detail_price": self.price,
            "detail_amount_money": self.amount_money,
            "detail_unit_cost": self.unit_cost,
            "detail_received_quantity": self.received_quantity,
            "detail_gift": self.gift,
            "detail_shipping_fee": self.shipping_fee,
            "detail_unit_shipping_fee": self.unit_shipping_fee,
            "detail_packing_fee": self.packing_fee,
            "detail_unit_packing_fee": self.unit_packing_fee,
            "detail_delivery_date": self.delivery_date,
            "detail_company_remark": self.company_remark,
            "detail_is_unsalable": self.is_unsalable,
            "detail_ks_price": self.ks_price,
            "detail_store": self.store,
            "detail_operator": self.operator,
            "detail_created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "detail_updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
