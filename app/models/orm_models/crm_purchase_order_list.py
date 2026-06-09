# -*- coding:utf-8 -*-
# @Time    : 2026/6/6
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crm_purchase_order_list.py
# @Software: PyCharm

from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, Text, Numeric, text
from sqlalchemy.dialects.mysql import insert

from .base_models import BaseModels


class CrmPurchaseOrderList(BaseModels):
    """
    采购订单数据表 ORM 模型
    
    对应数据库表：crm_purchase_order_list
    """
    
    __tablename__ = "crm_purchase_order_list"

    purchase_order_id = Column(BigInteger, primary_key=True, nullable=False, comment="采购订单ID")
    pono = Column(String(100), nullable=True, comment="采购单号")
    partner_id = Column(BigInteger, nullable=True, comment="供应商ID")
    fullname = Column(String(255), nullable=True, comment="供应商名称")
    supplier_phone = Column(String(50), nullable=True, comment="供应商电话")
    status = Column(Integer, nullable=True, comment="订单状态")
    order_type_id = Column(Integer, nullable=True, comment="订单类型")
    order_source_type = Column(Integer, nullable=True, comment="订单来源类型")
    total = Column(Integer, nullable=True, comment="商品总数量")
    amount_money = Column(Numeric(12, 2), nullable=True, comment="订单总金额")
    received_quantity = Column(Numeric(12, 2), nullable=True, comment="已收货数量")
    received = Column(Numeric(12, 2), nullable=True, comment="已收货金额")
    shipping_fee = Column(Numeric(10, 2), nullable=True, comment="运费")
    packing_fee = Column(Numeric(10, 2), nullable=True, comment="包装费")
    create_date = Column(String(255), nullable=True, comment="创建时间")
    expected_delivery_date = Column(String(255), nullable=True, comment="预计交货时间")
    e_date = Column(String(255), nullable=True, comment="实际完成时间")
    name = Column(String(255), nullable=True, comment="操作人")
    payment_description = Column(String(255), nullable=True, comment="支付方式描述")
    is_wms = Column(Integer, nullable=True, comment="是否WMS订单")
    store = Column(String(50), nullable=True, comment="门店")
    remarks = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<CrmPurchaseOrderList purchase_order_id={self.purchase_order_id} pono={self.pono}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        Numeric 类型会转换为 float
        
        :return: 包含所有字段的字典
        """
        return {
            "list_purchase_order_id": self.purchase_order_id,
            "list_pono": self.pono,
            "list_partner_id": self.partner_id,
            "list_fullname": self.fullname,
            "list_supplier_phone": self.supplier_phone,
            "list_status": self.status,
            "list_order_type_id": self.order_type_id,
            "list_order_source_type": self.order_source_type,
            "list_total": self.total,
            "list_amount_money": self.amount_money,
            "list_received_quantity": self.received_quantity,
            "list_received": self.received,
            "list_shipping_fee": self.shipping_fee,
            "list_packing_fee": self.packing_fee,
            "list_create_date": self.create_date,
            "list_expected_delivery_date": self.expected_delivery_date,
            "list_e_date": self.e_date,
            "list_name": self.name,
            "list_payment_description": self.payment_description,
            "list_is_wms": self.is_wms,
            "list_store": self.store,
            "list_remarks": self.remarks,
            "list_created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "list_updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
