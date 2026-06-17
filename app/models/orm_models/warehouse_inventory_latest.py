# -*- coding:utf-8 -*-
"""
仓库库存最新表 ORM 模型
对应数据库表：warehouse_inventory_latest
数据来自 CRM getProductList 接口，以 product_id + company 为唯一键，覆盖更新
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric
from sqlalchemy.dialects.mysql import insert

from .base_models import BaseModels


class WarehouseInventoryLatest(BaseModels):
    """
    仓库库存最新表
    """
    __tablename__ = "warehouse_inventory_latest"

    product_id = Column(Integer, primary_key=True, nullable=False, comment="产品ID")
    product_name = Column(String(255), nullable=True, comment="产品名称")
    l_name_zh_default = Column(String(255), nullable=True, comment="默认中文名")
    frey_no = Column(String(100), nullable=True, comment="Frey编号")
    number = Column(String(100), nullable=True, comment="OE号")
    cass_oebrand_name = Column(String(100), nullable=True, comment="车辆品牌")
    brand_name = Column(String(100), nullable=True, comment="配件品牌")
    link_brand_code = Column(String(100), nullable=True, comment="品牌关联码")
    vehicle_model = Column(String(255), nullable=True, comment="车型")
    cost_price = Column(Numeric(10, 2), nullable=True, default=0.00, comment="成本价")
    stock_quantity = Column(Integer, nullable=True, default=0, comment="库存数量")
    cost_price_total = Column(Numeric(10, 2), nullable=True, default=0.00, comment="成本总价")
    kw_nos = Column(String(500), nullable=True, comment="库位信息")
    warehouse_name = Column(String(100), nullable=True, comment="仓库名称")
    company = Column(String(50), primary_key=True, nullable=False, comment="门店代码")
    sync_time = Column(DateTime, nullable=True, default=datetime.now, comment="同步时间")

    @classmethod
    def bulk_upsert(cls, session, data_list, batch_size=100):
        """
        批量插入或更新（以 product_id + company 为唯一键）
        使用 INSERT ... ON DUPLICATE KEY UPDATE
        分批处理避免 SQL 参数过多

        :param session: SQLAlchemy Session 对象
        :param data_list: 数据字典列表
        :param batch_size: 每批处理数量，默认100
        :return: 处理的记录数
        """
        if not data_list:
            return 0

        total = 0
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            stmt = insert(cls).values(batch)

            update_dict = {}
            for column in cls.__table__.columns:
                col_name = column.name
                if col_name not in ['product_id', 'company']:
                    update_dict[col_name] = getattr(stmt.inserted, col_name)

            stmt = stmt.on_duplicate_key_update(update_dict)
            session.execute(stmt)
            total += len(batch)

        return total

    @classmethod
    def delete_by_company(cls, session, company):
        """
        按门店删除所有记录（全量同步前使用）

        :param session: SQLAlchemy Session 对象
        :param company: 门店代码
        :return: 删除的记录数
        """
        result = session.query(cls).filter_by(company=company).delete()
        return result
