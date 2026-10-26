# -*- coding:utf-8 -*-
# @Time    : 2026/10/13 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_record_dao.py
# @Software: PyCharm
"""
客访-拜访记录表（visit_record）数据访问层

职责：
1. 幂等建表（对应 sql/visit/visit_record.sql）
2. 批量 upsert：不预查、不区分新增/更新，由数据库按唯一键
   uk_visit_dedup (amap_customer_id, visit_time) 自动插入/更新
3. 拜访记录分页查询（M2 拜访历史时间轴）
"""
from sqlalchemy.dialects.mysql import insert

from app.models.orm_models.base_models import BaseModels
from app.models.orm_models.visit.visit_record import VisitRecord
from app.utils.orm.session import get_engine

# 建表幂等标记（每进程只执行一次）
_table_ensured = False


def ensure_table():
    """幂等建表（IF NOT EXISTS），每进程只执行一次。"""
    global _table_ensured
    if _table_ensured:
        return
    BaseModels.metadata.create_all(get_engine(), tables=[VisitRecord.__table__])
    _table_ensured = True


# upsert 冲突时更新的字段：仅记录内容本身；
# status / source / created_at 不被导入覆盖（保留人工与渠道状态）
RECORD_UPDATABLE_FIELDS = ("recorder", "content", "images", "updated_at")


def bulk_upsert(session, data_list, chunk_size=500):
    """
    批量插入或更新（幂等键 uk_visit_dedup (amap_customer_id, visit_time)）

    - 不存在：插入（status=1/source 等由数据显式给定）
    - 已存在：仅更新 RECORD_UPDATABLE_FIELDS（记录人、记录文字、照片、updated_at）；
      status / source / created_at 保持既有值，
      人工作废、渠道标识不会被重复导入冲掉

    :param session: SQLAlchemy Session 对象
    :param data_list: 数据字典列表（key 为表字段名）
    :param chunk_size: 分批提交大小
    :return: 处理的记录数
    """
    if not data_list:
        return 0
    for i in range(0, len(data_list), chunk_size):
        chunk = data_list[i:i + chunk_size]
        stmt = insert(VisitRecord).values(chunk)
        update_dict = {
            col: getattr(stmt.inserted, col)
            for col in RECORD_UPDATABLE_FIELDS
        }
        stmt = stmt.on_duplicate_key_update(update_dict)
        session.execute(stmt)
    return len(data_list)


def page_records(session, page=1, limit=20, amap_customer_id=None):
    """
    拜访记录分页查询（M2 拜访历史时间轴，按记录时间倒序，固定排除作废记录）

    :param session: SQLAlchemy Session 对象
    :param page: 页码，从 1 开始
    :param limit: 每页条数
    :param amap_customer_id: 按客户筛选，选填
    :return: (total, rows) 命中总数与当前页 ORM 对象列表
    """
    page = max(1, page or 1)
    limit = max(1, limit or 20)

    query = session.query(VisitRecord).filter(VisitRecord.status == 1)
    if amap_customer_id:
        query = query.filter(VisitRecord.amap_customer_id == amap_customer_id)
    total = query.count()

    query = query.order_by(VisitRecord.visit_time.desc(), VisitRecord.id.desc())
    rows = query.offset((page - 1) * limit).limit(limit).all()
    return total, rows
