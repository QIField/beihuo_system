# -*- coding:utf-8 -*-
# @Time    : 2026/09/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : order_delivery_info.py
# @Software: trae-cn

"""
订单物流状态表 ORM 模型

用途：缓存对客扫码订单的物流推进状态，避免每次刷新都从头查 CRM。
表结构 SQL 见：docs/订单加密规则说明.md 或下文注释。
"""

from datetime import datetime

from sqlalchemy import Column, BigInteger, String, DateTime

from app.models.orm_models.base_models import BaseModels


class OrderDeliveryInfo(BaseModels):
    """
    order_delivery_info 表

    SQL 建表语句（MySQL）：
    CREATE TABLE IF NOT EXISTS `order_delivery_info` (
        `id`            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        `orders_id`     BIGINT UNSIGNED NOT NULL,
        `orders_no`     VARCHAR(64) NOT NULL,
        `create_date`   BIGINT COMMENT 'CRM 订单创建时间（秒级时间戳）',
        `delivery_id`   BIGINT COMMENT '发货单 ID',
        `jhdate`        DATETIME COMMENT '拣货日期',
        `ship_date`     DATETIME COMMENT 'WMS 发货日期',
        `status`        VARCHAR(16) NOT NULL COMMENT '已下单 / 仓库已接单 / 已出库',
        `created_at`    DATETIME DEFAULT CURRENT_TIMESTAMP,
        `updated_at`    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY `uk_orders_id` (`orders_id`),
        KEY `idx_orders_no` (`orders_no`),
        KEY `idx_status` (`status`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单物流状态（对客扫码查询用）';
    """

    __tablename__ = "order_delivery_info"

    STATUS_ORDERED = "已下单"
    STATUS_PICKED = "仓库已接单"
    STATUS_SHIPPED = "已出库"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增主键")
    orders_id = Column(BigInteger, nullable=False, comment="CRM 订单 ID")
    orders_no = Column(String(64), nullable=False, comment="CRM 订单号")
    create_date = Column(BigInteger, nullable=True, comment="CRM 订单创建时间（秒级时间戳）")
    delivery_id = Column(BigInteger, nullable=True, comment="发货单 ID")
    jhdate = Column(DateTime, nullable=True, comment="拣货日期")
    ship_date = Column(DateTime, nullable=True, comment="WMS 发货日期")
    status = Column(String(16), nullable=False, comment="已下单 / 仓库已接单 / 已出库")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="记录创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="记录更新时间")

    def to_dict(self):
        return {
            "orders_id": self.orders_id,
            "orders_no": self.orders_no,
            "create_date": self.create_date,
            "delivery_id": self.delivery_id,
            "jhdate": self.jhdate.strftime("%Y-%m-%d %H:%M:%S") if self.jhdate else None,
            "ship_date": self.ship_date.strftime("%Y-%m-%d %H:%M:%S") if self.ship_date else None,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
