# -*- coding:utf-8 -*-
"""
WMS 采购入库推送日志头表 ORM 模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.dialects.mysql import insert

from app.models.orm_models.base_models import BaseModels


class WmsPurchaseInventoryPushLog(BaseModels):
    """
    WMS 采购入库推送日志头表

    对应数据库表：wms_purchase_inventory_push_log
    """
    __tablename__ = "wms_purchase_inventory_push_log"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    orders_id = Column(String(255), nullable=False, comment="订单ID")
    orders_no = Column(String(255), nullable=False, comment="入库单号")
    pono = Column(String(255), nullable=True, comment="拣货单号")
    supplier_short_name = Column(String(255), nullable=True, comment="供应商简称")
    total_needqty = Column(Integer, nullable=True, comment="total.needqty")
    total_qty = Column(Integer, nullable=True, comment="total.qty")
    api_response_code = Column(Integer, nullable=True, comment="POST返回code")
    api_response_message = Column(String(500), nullable=True, comment="POST返回message")
    confirm_api_response_code = Column(Integer, nullable=True, comment="确认接口返回code")
    confirm_api_response_message = Column(String(500), nullable=True, comment="确认接口返回message")
    pushed_at = Column(DateTime, nullable=True, comment="本次推送时间")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        UniqueConstraint('orders_id', name='uk_orders_id'),
    )

    @classmethod
    def upsert(cls, session, data: dict) -> int:
        """
        按 orders_id 执行插入或更新
        """
        if not data:
            return 0

        stmt = insert(cls).values(data)
        update_dict = {
            col.name: getattr(stmt.inserted, col.name)
            for col in cls.__table__.columns
            if col.name not in ('id', 'created_at')
        }
        stmt = stmt.on_duplicate_key_update(**update_dict)
        session.execute(stmt)
        return 1
