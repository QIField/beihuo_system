# -*- coding:utf-8 -*-
# @Time    : 2026/07/25
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_refund_ref.py
# @Software: trae-cn

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, SmallInteger, Index, UniqueConstraint, text

from app.models.orm_models.base_models import BaseModels


class StockSafeRefundRef(BaseModels):
    """
    安全库存退货关联表 ORM模型
    
    用于建立常规订单（order_type_id=1）与退货订单（order_type_id=2）的关联关系，
    支持多对多匹配：一条退货订单可匹配多条常规订单，一条常规订单也可被多条退货订单匹配。
    
    type字段两位数编码规则：
    - 十位（第一位）：匹配状态分类
      1=完全退货（processed_quantity=0）
      2=部分退货（processed_quantity>0）
      3=退货数量超出（processed_quantity<0）
      4=未匹配
      5=未进行匹配
    - 个位（第二位）：匹配模式
      1=一对一匹配
      2=一对多-常规订单视角（一条常规订单被多条退货订单分摊）
      3=一对多-退货订单视角（一条退货订单分摊到多条常规订单）
    """
    __tablename__ = "stock_safe_refund_ref"
    __table_args__ = (
        UniqueConstraint('normal_order_items_id', 'refund_order_items_id', name='uk_normal_refund'),
        Index('idx_customer_id', 'customer_id'),
        Index('idx_number', 'number'),
        Index('idx_type', 'type'),
        Index('idx_created_at', 'created_at'),
        Index('idx_match_count', 'match_count'),
        Index('idx_normal_match', 'normal_order_items_id', 'match_count'),
        Index('idx_refund_match', 'refund_order_items_id', 'match_count'),
        Index('idx_match_refund', 'customer_id', text('frey_no(50)'), text('number(60)'), text('brand_name(50)'), 'type', 'refund_create_date'),
        Index('idx_order_type_date', 'type', 'refund_create_date'),
        Index('idx_normal_type', 'normal_order_items_id', 'type'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")

    normal_order_items_id = Column(Integer, nullable=True, comment="常规订单明细ID（sales_order_history表orders_items_id），未匹配时为NULL")
    refund_order_items_id = Column(Integer, nullable=False, comment="退货订单明细ID（sales_order_history表orders_items_id）")

    number = Column(String(255), nullable=True, comment="OE号（即sales_order_history表number字段）")
    brand_name = Column(String(255), nullable=True, comment="品牌名（即sales_order_history表brand_name字段）")
    pdname = Column(String(255), nullable=True, comment="产品名称（即sales_order_history表pdname字段）")
    frey_no = Column(String(255), nullable=True, comment="条码（即sales_order_history表frey_no字段）")
    customer_id = Column(Integer, nullable=True, comment="客户ID（即sales_order_history表customer_id字段）")

    normal_quantity = Column(Integer, nullable=True, comment="常规订单数量")
    refund_quantity = Column(Integer, nullable=True, comment="退货订单数量")
    refund_create_date = Column(Integer, nullable=True, comment="退货订单创建时间戳（sales_order_history表create_date字段）")

    processed_quantity = Column(Integer, nullable=True, comment="处理数量（常规订单quantity + 退货订单quantity）")

    match_count = Column(Integer, nullable=True, default=0, comment="匹配次数（标识本条记录是第几次匹配产生的）")

    type = Column(SmallInteger, nullable=True, comment="类型（两位数编码：十位=匹配状态，个位=匹配模式）：11-完全退货一对一，12-完全退货一对多常规，13-完全退货一对多退货，21-部分退货一对一，22-部分退货一对多常规，23-部分退货一对多退货，31-退货数量超出一对一，32-退货数量超出一对多常规，33-退货数量超出一对多退货，40-未匹配，50-未进行匹配")

    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    def __repr__(self):
        return f"<StockSafeRefundRef id={self.id} normal_order={self.normal_order_items_id} refund_order={self.refund_order_items_id}>"

    def to_dict(self):
        """将ORM对象转换为字典"""
        return {
            "id": self.id,
            "normal_order_items_id": self.normal_order_items_id,
            "refund_order_items_id": self.refund_order_items_id,
            "number": self.number,
            "brand_name": self.brand_name,
            "pdname": self.pdname,
            "frey_no": self.frey_no,
            "customer_id": self.customer_id,
            "normal_quantity": self.normal_quantity,
            "refund_quantity": self.refund_quantity,
            "refund_create_date": self.refund_create_date,
            "processed_quantity": self.processed_quantity,
            "match_count": self.match_count,
            "type": self.type,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }