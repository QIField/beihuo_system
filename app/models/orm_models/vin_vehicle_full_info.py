#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VIN 车辆完整信息 ORM 模型

存储 VIN、发动机、底盘信息均齐全的数据，用于后续业务查询。
"""

from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from app.models.orm_models.base_models import BaseModels


class VinVehicleFullInfo(BaseModels):
    """VIN 车辆完整信息表"""

    __tablename__ = 'vin_vehicle_full_info'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='自增ID')
    vin_code = Column(String(100), nullable=False, comment='VIN码')
    engine = Column(String(100), nullable=False, comment='发动机号')
    chassis = Column(String(100), nullable=False, comment='底盘号')
    source = Column(String(50), nullable=True, comment='数据来源：ks_inquiry / vin_vehicle_info / merge')
    created_at = Column(DateTime, nullable=True, server_default=func.now(), comment='创建时间')
    updated_at = Column(
        DateTime,
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
        comment='更新时间',
    )

    __table_args__ = (
        Index('uk_vin_code', 'vin_code', unique=True),
        Index('idx_engine', 'engine'),
        Index('idx_chassis', 'chassis'),
        Index('idx_created_at', 'created_at'),
        {'comment': 'VIN车辆完整信息表'},
    )
