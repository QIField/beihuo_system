# -*- coding:utf-8 -*-
# @Time    : 2026/10/18
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_sync_queue.py
# @Software: trae-cn

from datetime import datetime

from sqlalchemy import Column, BigInteger, String, DateTime, Integer, UniqueConstraint, Index

from app.models.orm_models.base_models import BaseModels


class StockSafeSyncQueue(BaseModels):
    """
    安全库存同步CRM队列表 ORM模型

    对应数据库表：stock_safe_sync_queue
    管理需要推送到 CRM 的安全库存商品，以 (number, brand_name) 为业务唯一键。
    队列不存储推送参数，同步执行时实时从 stock_safe 表读取 safety_stock /
    stock_upper_limit / season_coefficient 等推送值。

    同步状态通过 synced_at 字段判定：
      - synced_at IS NULL      → 待同步
      - synced_at IS NOT NULL  → 已同步（最后一次同步成功）
    同步失败时 synced_at 保持 NULL，下次任务自动重试，不限制重试次数。
    """

    __tablename__ = "stock_safe_sync_queue"
    __table_args__ = (
        UniqueConstraint('number', 'brand_name', name='uk_number_brand'),
        Index('idx_synced_at', 'synced_at'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    number = Column(String(255), nullable=False, comment="OE号（CRM匹配键）")
    brand_name = Column(String(255), nullable=False, comment="品牌名（CRM匹配键）")
    frey_no = Column(String(255), nullable=True, comment="条码（取自stock_safe第一条，仅供参考）")
    pdname = Column(String(255), nullable=True, comment="产品名称（冗余展示）")
    sync_enabled = Column(Integer, nullable=False, default=1, comment="是否开启同步：1=开启，0=关闭")

    synced_at = Column(DateTime, nullable=True, comment="最后一次成功同步时间；NULL表示待同步")

    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    def __repr__(self):
        return f"<StockSafeSyncQueue id={self.id} number={self.number} brand={self.brand_name} synced_at={self.synced_at}>"

    def to_dict(self):
        """将ORM对象转换为字典"""
        return {
            "id": self.id,
            "number": self.number,
            "brand_name": self.brand_name,
            "frey_no": self.frey_no,
            "pdname": self.pdname,
            "sync_enabled": self.sync_enabled,
            "synced_at": self.synced_at.strftime("%Y-%m-%d %H:%M:%S") if self.synced_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
        }
