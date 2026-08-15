# -*- coding:utf-8 -*-
# @Time    : 2026/07/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : sales_order_history.py
# @Software: trae-cn

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, Index, text

from app.models.orm_models.base_models import BaseModels


class SalesOrderHistory(BaseModels):
    __tablename__ = "sales_order_history"
    __table_args__ = (
        Index('idx_orders_id', 'orders_id'),
        Index('idx_ddno', 'ddno'),
        Index('idx_customer_id', 'customer_id'),
        Index('idx_product_id', 'product_id'),
        Index('idx_create_date', 'create_date'),
        Index('idx_store', 'store'),
        Index('idx_normal_cid', 'order_type_id', text('number(60)'), 'customer_id', text('brand_name(50)'), text('pdname(80)'), text('frey_no(30)'), 'create_date'),
        Index('idx_normal_name', 'order_type_id', text('number(60)'), 'fullname', text('brand_name(50)'), text('pdname(80)'), text('frey_no(30)'), 'create_date'),
    )

    orders_items_id = Column(Integer, primary_key=True, nullable=False, comment="订单明细ID")

    handler = Column(Integer, nullable=True, comment="处理人ID")
    user_id = Column(Integer, nullable=True, comment="用户ID（经收人）")
    seller_id = Column(Integer, nullable=True, comment="销售员ID")
    customer_id = Column(Integer, nullable=True, comment="客户ID")

    order_type_id = Column(Integer, nullable=True, comment="订单类型ID")
    create_date = Column(Integer, nullable=True, comment="创建时间戳")
    send_date = Column(Integer, nullable=True, comment="发货时间戳")

    orders_id = Column(Integer, nullable=True, comment="订单ID")
    ddno = Column(String(255), nullable=True, comment="订单号")
    ddsapno = Column(String(255), nullable=True, comment="订单金蝶号")

    status = Column(String(50), nullable=True, comment="订单状态（中文）")
    origin_status = Column(Integer, nullable=True, comment="原始状态码")

    fullname = Column(String(255), nullable=True, comment="客户全称")

    quantity = Column(Integer, nullable=True, comment="数量")
    sfqty = Column(Integer, nullable=True, comment="实发数量")

    price = Column(Numeric(18, 4), nullable=True, comment="单价")
    cost_price = Column(Numeric(18, 4), nullable=True, comment="成本价")
    total_price = Column(Numeric(18, 4), nullable=True, comment="总价")
    sfje = Column(Numeric(18, 4), nullable=True, comment="实付金额")

    product_id = Column(Integer, nullable=True, comment="产品ID")
    brand_id = Column(Integer, nullable=True, comment="品牌ID")
    pdname = Column(String(255), nullable=True, comment="产品名称")
    frey_no = Column(String(255), nullable=True, comment="菲尔号")
    l_model_zh = Column(Text, nullable=True, comment="车型（中文）")
    number = Column(String(255), nullable=True, comment="OE号")

    is_wms = Column(Integer, nullable=True, comment="是否WMS订单")
    delivery_status = Column(Integer, nullable=True, comment="发货状态")
    logistics_name = Column(String(255), nullable=True, comment="物流公司名称")
    kingdee_status = Column(Integer, nullable=True, comment="金蝶状态")
    logistics_user_id = Column(Integer, nullable=True, comment="物流用户ID")

    warehouse_no = Column(String(255), nullable=True, comment="仓库编号")
    brand_name = Column(String(255), nullable=True, comment="品牌名称")
    order_type_name = Column(String(255), nullable=True, comment="订单类型名称")
    user_name = Column(String(255), nullable=True, comment="用户名")
    creater = Column(String(255), nullable=True, comment="创建人")
    seller_name = Column(String(255), nullable=True, comment="销售员名称")

    deliverysapno = Column(String(255), nullable=True, comment="发货金蝶号")
    deliveryordersno = Column(String(255), nullable=True, comment="发货单号")

    store = Column(String(255), nullable=True, comment="门店标识")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    def __repr__(self):
        return f"<SalesOrderHistory orders_items_id={self.orders_items_id} ddno={self.ddno}>"

    def to_dict(self):
        return {
            "orders_items_id": self.orders_items_id,
            "handler": self.handler,
            "user_id": self.user_id,
            "seller_id": self.seller_id,
            "customer_id": self.customer_id,
            "order_type_id": self.order_type_id,
            "create_date": self.create_date,
            "send_date": self.send_date,
            "orders_id": self.orders_id,
            "ddno": self.ddno,
            "ddsapno": self.ddsapno,
            "status": self.status,
            "origin_status": self.origin_status,
            "fullname": self.fullname,
            "quantity": self.quantity,
            "sfqty": self.sfqty,
            "price": float(self.price) if self.price is not None else None,  # pyright: ignore[reportArgumentType]
            "cost_price": float(self.cost_price) if self.cost_price is not None else None,  # pyright: ignore[reportArgumentType]
            "total_price": float(self.total_price) if self.total_price is not None else None,  # pyright: ignore[reportArgumentType]
            "sfje": float(self.sfje) if self.sfje is not None else None,  # pyright: ignore[reportArgumentType]
            "product_id": self.product_id,
            "brand_id": self.brand_id,
            "pdname": self.pdname,
            "frey_no": self.frey_no,
            "l_model_zh": self.l_model_zh,
            "number": self.number,
            "is_wms": self.is_wms,
            "delivery_status": self.delivery_status,
            "logistics_name": self.logistics_name,
            "kingdee_status": self.kingdee_status,
            "logistics_user_id": self.logistics_user_id,
            "warehouse_no": self.warehouse_no,
            "brand_name": self.brand_name,
            "order_type_name": self.order_type_name,
            "user_name": self.user_name,
            "creater": self.creater,
            "seller_name": self.seller_name,
            "deliverysapno": self.deliverysapno,
            "deliveryordersno": self.deliveryordersno,
            "store": self.store,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
