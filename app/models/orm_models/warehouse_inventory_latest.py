# -*- coding:utf-8 -*-
"""
仓库库存最新表 ORM 模型
对应数据库表：warehouse_inventory_latest
数据来自 CRM getProductList 接口，以 product_id + company + sync_date + kw_nos 为唯一键
按仓位拆行存储，同一天覆盖，不同日期保留
"""

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Date, Numeric
from sqlalchemy.dialects.mysql import insert

from .base_models import BaseModels


class WarehouseInventoryLatest(BaseModels):
    """
    仓库库存最新表（按天快照、按仓位拆行）
    同一 product_id + company + sync_date + kw_nos 每天覆盖，不同日期保留
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
    kw_nos = Column(String(500), primary_key=True, nullable=False, comment="库位号（单条记录只存一个仓位）")
    warehouse_name = Column(String(100), nullable=True, comment="仓库名称")
    company = Column(String(50), primary_key=True, nullable=False, comment="门店代码")
    sync_date = Column(Date, primary_key=True, nullable=False, default=date.today, comment="同步日期")
    sync_time = Column(DateTime, nullable=True, default=datetime.now, comment="同步时间")

    @classmethod
    def bulk_upsert(cls, session, data_list, batch_size=100):
        """
        批量插入或更新（以 product_id + company + sync_date + kw_nos 为唯一键）
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
                if col_name not in ['product_id', 'company', 'sync_date', 'kw_nos']:
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

    @classmethod
    def delete_old_snapshots(cls, session, company, keep_days=30):
        """
        删除指定门店超过保留天数的旧快照

        :param session: SQLAlchemy Session 对象
        :param company: 门店代码
        :param keep_days: 保留天数，默认 30
        :return: 删除的记录数
        """
        from datetime import date, timedelta
        cutoff_date = date.today() - timedelta(days=keep_days)
        result = session.query(cls).filter(
            cls.company == company,
            cls.sync_date < cutoff_date
        ).delete(synchronize_session=False)
        return result

    @classmethod
    def get_kw_no_sku_count(cls, session, company, target_date):
        """
        按仓位统计指定日期的 SKU 种类数（仓位库存 > 0）

        :param session: SQLAlchemy Session 对象
        :param company: 门店代码
        :param target_date: 目标日期
        :return: dict {kw_no: sku_count}
        """
        from sqlalchemy import func
        rows = session.query(
            cls.kw_nos,
            func.count(func.distinct(cls.product_id)).label('sku_count')
        ).filter(
            cls.company == company,
            cls.sync_date == target_date,
            cls.stock_quantity > 0
        ).group_by(cls.kw_nos).all()
        return {row.kw_nos: row.sku_count for row in rows if row.kw_nos}

