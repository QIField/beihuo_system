# -*- coding: utf-8 -*-
"""
物料在途库存同步 - 数据库服务

负责建表（幂等）、快照全量重建。
"""

from app.models.orm_models.base_models import BaseModels
from app.models.orm_models.b2b_intransit_stock import B2bIntransitStock
from app.utils.orm.session import get_engine
from .config import BATCH_SIZE


def ensure_tables():
    """幂等建表（IF NOT EXISTS），应用启动/首次执行时调用"""
    engine = get_engine()
    BaseModels.metadata.create_all(
        engine,
        tables=[B2bIntransitStock.__table__]
    )


def replace_snapshot_for_company(session, company, records):
    """
    按公司重建在途快照（须在事务内调用）

    物理删除指定公司的旧记录后批量插入该公司的新记录；
    调用方需保证仅在"接口成功拉取并校验通过"后执行，避免接口抖动清空数据。

    :return: (deleted_count, inserted_count)
    """
    deleted_count = session.query(B2bIntransitStock).filter_by(company=company).delete()

    inserted_count = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        session.bulk_insert_mappings(B2bIntransitStock, batch)
        inserted_count += len(batch)

    return deleted_count, inserted_count
