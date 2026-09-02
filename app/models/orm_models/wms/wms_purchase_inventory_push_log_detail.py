# -*- coding:utf-8 -*-
"""
WMS 采购入库推送日志明细表 ORM 模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, Index
from sqlalchemy.dialects.mysql import insert

from app.models.orm_models.base_models import BaseModels


class WmsPurchaseInventoryPushLogDetail(BaseModels):
    """
    WMS 采购入库推送日志明细表

    对应数据库表：wms_purchase_inventory_push_log_detail
    """
    __tablename__ = "wms_purchase_inventory_push_log_detail"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    orders_id = Column(String(255), nullable=False, comment="订单ID")
    frey_no = Column(String(255), nullable=True, comment="货运单号")
    warehouse_name = Column(String(255), nullable=True, comment="仓库名称")
    brandname = Column(String(255), nullable=True, comment="品牌名称")
    l_name_zh = Column(String(255), nullable=True, comment="中文名称")
    number = Column(String(255), nullable=True, comment="编号/OE号")
    needqty = Column(Integer, nullable=True, comment="需求数量")
    qty = Column(Integer, nullable=True, comment="实际数量")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        UniqueConstraint('orders_id', 'number', 'brandname', name='uk_orders_id_number_brandname'),
        Index('idx_orders_id', 'orders_id'),
    )

    @classmethod
    def bulk_upsert(cls, session, data_list: list) -> int:
        """
        按 orders_id + number + brandname 批量插入或更新
        """
        if not data_list:
            return 0

        stmt = insert(cls).values(data_list)
        update_dict = {
            col.name: getattr(stmt.inserted, col.name)
            for col in cls.__table__.columns
            if col.name not in ('id', 'created_at')
        }
        stmt = stmt.on_duplicate_key_update(**update_dict)
        session.execute(stmt)
        return len(data_list)
