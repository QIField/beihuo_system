# -*- coding:utf-8 -*-
# @Time    : 2026/7/9
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_order_push_seen.py
# @Software: PyCharm
# @Desc    : WMS 订单推送 01-09 仓位已见记录表

from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, UniqueConstraint

from app.models.orm_models.base_models import BaseModels


class WmsOrderPushSeen(BaseModels):
    """
    WMS 订单推送 01-09 仓位已见记录表
    用于记录 (订单号 + 库位号 + OE号) 组合首次出现的时间
    """
    __tablename__ = "wms_order_push_seen"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增ID")
    pono = Column(String(255), nullable=False, comment="订单号")
    kwno = Column(String(100), nullable=False, comment="库位号")
    oe_number = Column(String(255), nullable=False, comment="OE号")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="首次发现时间")

    __table_args__ = (
        UniqueConstraint('pono', 'kwno', 'oe_number', name='uk_wms_order_push_seen'),
    )
