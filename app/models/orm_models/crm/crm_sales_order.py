# -*- coding:utf-8 -*-
# @Time    : 2026/06/15 09:18
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crm_sales_order.py
# @Software: trae-cn

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Numeric, text, func
from sqlalchemy.dialects.mysql import insert

from app.models.orm_models.base_models import BaseModels
from app.utils.orm.type_decorators import StringToIntType


class MergeOrderList(BaseModels):
    """
    crm销售订单表 ORM 模型
    
    对应数据库表：crm_sales_order
    """
    
    __tablename__ = "crm_sales_order"

    
    

    # 定义订单类型映射：销售订单=1，退货订单=2
    ORDER_TYPE_ID_MAPPING = {
       
        '销售订单': 1,
        '退货订单': 2
    }

    # 定义业务类型映射：外购=1，普通=2，调货=3
    ORDER_SOURCE_NAME_MAPPING = {
        '外购': 1,
        '普通': 2,
        '调货': 3
    }

    orders_id = Column(Integer, primary_key=True, nullable=False, comment="主键ID")
    customer_id = Column(Integer, nullable=True, comment="客户ID")
    partner_id = Column(Integer, nullable=True, comment="合作伙伴ID")
    level_id = Column(Integer, nullable=True, comment="客户等级")
    is_wms = Column(Integer, nullable=True, comment="是否WMS")
    sap_no = Column(String(255), nullable=True, comment="订单号")
    d_sap_no = Column(String(255), nullable=True, comment="金蝶单号")
    fullname = Column(String(255), nullable=True, comment="客户名称")
    customer_phone = Column(String(50), nullable=True, comment="电话")
    sku_num = Column(Integer, nullable=True, comment="SKU数")
    total_quantity = Column(Integer, nullable=True, comment="产品件数")
    realqty = Column(Integer, nullable=True, comment="实发件数")
    total_price = Column(Numeric(10, 2), nullable=True, comment="订单金额")
    sfje = Column(Numeric(10, 2), nullable=True, comment="实发金额")
    no_receive_amount = Column(Numeric(10, 2), nullable=True, comment="未结算金额")
    status = Column(Integer, nullable=True, comment="订单状态")
    order_type_name = Column(StringToIntType(ORDER_TYPE_ID_MAPPING), nullable=True, comment="订单类型")
    order_source_name = Column(StringToIntType(ORDER_SOURCE_NAME_MAPPING), nullable=True, comment="业务类型")
    handler = Column(String(255), nullable=True, comment="经手人")
    create_date = Column(Integer, nullable=True, comment="创建时间（秒级时间戳）")
    user_id = Column(String(255), nullable=True, comment="创建人")
    remark = Column(Text, nullable=True, comment="备注")
    street = Column(String(500), nullable=True, comment="街道地址")
    warehouse = Column(String(255), nullable=True, comment="仓库")
    order_error = Column(Text, nullable=True, comment="订单错误信息")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

  



    def __repr__(self):
        """
        打印对象时显示的友好格式
        """
        return f"<MergeOrderList orders_id={self.orders_id} d_sap_no={self.d_sap_no}>"

    def to_dict(self):
        """
        将模型对象转换为字典
        
        方便接口返回 JSON 数据
        DateTime 类型会转换为字符串
        
        :return: 包含所有字段的字典
        """
        return {
            "orders_id": self.orders_id,
            "customer_id": self.customer_id,
            "partner_id" :self.partner_id,
            "level_id": self.level_id,
            "is_wms": self.is_wms,
            "sap_no": self.sap_no,
            "d_sap_no": self.d_sap_no,
            "fullname": self.fullname,
            "customer_phone": self.customer_phone,
            "sku_num": self.sku_num,
            "total_quantity": self.total_quantity,
            "realqty": self.realqty,
            "total_price": self.total_price,
            "sfje": self.sfje,
            "no_receive_amount": self.no_receive_amount,
            "status": self.status,
            "order_type_id": self.order_type_id,
            "order_source_name": self.order_source_name,
            "handler": self.handler,
            "create_date": self.create_date,
            "user_id": self.user_id,
            "remark": self.remark,
            "street": self.street,
            "warehouse": self.warehouse,
            "order_error": self.order_error,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }

