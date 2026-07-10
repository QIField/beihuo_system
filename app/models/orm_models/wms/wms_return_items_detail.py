# -*- coding:utf-8 -*-
# @Time    : 2026/7/10
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_return_items_detail.py
# @Software: PyCharm
# @Desc    : WMS 采购入库单明细表（按指定字段抽取）

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.dialects.mysql import insert

from app.models.orm_models.base_models import BaseModels


class WmsReturnItemsDetail(BaseModels):
    """
    WMS 采购入库单明细表

    数据来源：
    1. get_status_orders(type=5, status=2) 取 orders_no / pono / orderdate
    2. get_return_items(orders_no=...) 取 brandname / frey_no / l_name_zh /
       number / poqty / qty / product_id

    对应数据库表：wms_return_items_detail
    """
    __tablename__ = "wms_return_items_detail"

    # 主键 ID
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment="主键ID")
    # 订单号
    orders_no = Column(String(255), nullable=False, comment="订单号")
    # 拣货单号
    pono = Column(String(255), nullable=True, comment="拣货单号")
    # 订单日期
    orderdate = Column(String(255), nullable=True, comment="订单日期")
    # 品牌名称
    brandname = Column(String(255), nullable=True, comment="品牌名称")
    # Frey单号
    frey_no = Column(String(255), nullable=True, comment="Frey单号")
    # 中文名称
    l_name_zh = Column(String(255), nullable=True, comment="中文名称")
    # 编号
    number = Column(String(255), nullable=True, comment="编号")
    # 处理后的编号（删除空格及之后内容）
    number_clean = Column(String(255), nullable=True, comment="处理后的编号")
    # 采购数量
    poqty = Column(Integer, nullable=True, comment="采购数量")
    # 数量
    qty = Column(Integer, nullable=True, comment="数量")
    # 产品ID
    product_id = Column(String(255), nullable=True, comment="产品ID")
    # 创建时间
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="数据创建时间")
    # 更新时间
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="数据更新时间")

    __table_args__ = (
        UniqueConstraint('orders_no', 'number', 'product_id', name='uk_wms_return_items_detail'),
    )

    @classmethod
    def get_existing_orders_nos(cls, session, orders_no_list):
        """
        批量查询已存在的 orders_no

        :param session: SQLAlchemy Session
        :param orders_no_list: orders_no 列表
        :return: 已存在的 orders_no 集合
        """
        if not orders_no_list:
            return set()

        rows = session.query(cls.orders_no).filter(
            cls.orders_no.in_(orders_no_list)
        ).distinct().all()

        return {row[0] for row in rows if row[0]}

    @classmethod
    def bulk_upsert(cls, session, data_list):
        """
        批量插入或更新数据

        唯一键：orders_no + number + product_id
        """
        if not data_list:
            return 0

        stmt = insert(cls).values(data_list)

        update_dict = {}
        for column in cls.__table__.columns:
            col_name = column.name
            if col_name not in ['id', 'created_at']:
                update_dict[col_name] = getattr(stmt.inserted, col_name)

        stmt = stmt.on_duplicate_key_update(update_dict)
        session.execute(stmt)

        return len(data_list)
