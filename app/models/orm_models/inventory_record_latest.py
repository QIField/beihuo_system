# -*- coding:utf-8 -*-
"""
库存变动记录表 ORM 模型
对应数据库表：inventory_record_latest
数据来自 CRM inventoryRecordList 接口，以 stock_log_id + company 为唯一键，只插入不覆盖
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric, text

from .base_models import BaseModels


class InventoryRecordLatest(BaseModels):
    """
    库存变动记录表
    """
    __tablename__ = "inventory_record_latest"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    stock_log_id = Column(Integer, nullable=False, comment="CRM日志ID")
    product_id = Column(Integer, nullable=True, comment="产品ID")
    record_type = Column(Integer, nullable=True, comment="变动类型：1=入库/增加，-1=出库/减少")
    user_id = Column(Integer, nullable=True, comment="操作人ID")
    kw_id = Column(Integer, nullable=True, comment="库位ID")
    batch_no = Column(String(100), nullable=True, comment="批次号")
    create_log_date = Column(Integer, nullable=True, comment="创建时间戳")
    change_number = Column(Integer, nullable=True, comment="变动数量")
    original_number = Column(Integer, nullable=True, comment="原始数量")
    note = Column(String(255), nullable=True, comment="备注")
    orders_id = Column(Integer, nullable=True, comment="订单ID")
    process_type_id = Column(Integer, nullable=True, comment="处理类型ID")
    pono = Column(String(100), nullable=True, comment="单号")
    device_type = Column(Integer, nullable=True, comment="设备类型")
    warehouse_id = Column(Integer, nullable=True, comment="仓库ID")
    frey_no = Column(String(100), nullable=True, comment="Frey编号")
    product_name = Column(String(255), nullable=True, comment="产品名称")
    number = Column(String(100), nullable=True, comment="OE号")
    brand_name = Column(String(100), nullable=True, comment="品牌")
    operator_name = Column(String(100), nullable=True, comment="操作人姓名")
    kw_no = Column(String(100), nullable=True, comment="库位号")
    warehouse_name = Column(String(100), nullable=True, comment="仓库名称")
    warehouse_no = Column(String(100), nullable=True, comment="仓库编号")
    workdate = Column(DateTime, nullable=True, comment="操作时间")
    names = Column(String(255), nullable=True, comment="供应商/客户名称")
    common_order_id = Column(String(100), nullable=True, comment="关联订单ID")
    company = Column(String(50), nullable=True, comment="门店代码")
    sync_time = Column(DateTime, nullable=True, default=datetime.now, comment="同步时间")

    @classmethod
    def exists_by_stock_log(cls, session, stock_log_id, company):
        """
        检查指定 stock_log_id + company 是否已存在

        :param session: SQLAlchemy Session 对象
        :param stock_log_id: CRM 日志ID
        :param company: 门店代码
        :return: True/False
        """
        result = session.query(cls).filter_by(
            stock_log_id=stock_log_id,
            company=company
        ).first()
        return result is not None

    @classmethod
    def bulk_insert_ignore(cls, session, data_list):
        """
        批量插入，忽略已存在记录（以 stock_log_id + company 为唯一键）
        先逐条检查是否存在，不存在才插入

        :param session: SQLAlchemy Session 对象
        :param data_list: 数据字典列表
        :return: 实际插入的记录数
        """
        if not data_list:
            return 0

        inserted_count = 0
        for data in data_list:
            if not cls.exists_by_stock_log(
                session,
                data.get('stock_log_id'),
                data.get('company')
            ):
                obj = cls(**data)
                session.add(obj)
                inserted_count += 1

        return inserted_count
