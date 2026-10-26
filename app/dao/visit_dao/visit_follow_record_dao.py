# -*- coding:utf-8 -*-
# @Time    : 2026/10/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_follow_record_dao.py
# @Software: PyCharm
"""
客访-跟进记录表（visit_follow_record）数据访问层

职责：
1. 幂等建表（对应 sql/visit/visit_follow_record.sql）
2. 跟进记录新增（纯手动写入，无幂等去重诉求，无唯一键）
3. 跟进记录分页查询（M7 跟进时间轴）
"""

from sqlalchemy import update

from app.models.orm_models.base_models import BaseModels
from app.models.orm_models.visit.visit_follow_record import VisitFollowRecord
from app.utils.orm.session import get_engine

# 建表幂等标记（每进程只执行一次）
_table_ensured = False


def ensure_table():
    """幂等建表（IF NOT EXISTS），每进程只执行一次。"""
    global _table_ensured
    if _table_ensured:
        return
    BaseModels.metadata.create_all(get_engine(), tables=[VisitFollowRecord.__table__])
    _table_ensured = True


def get_by_id(session, follow_id):
    """
    按主键查跟进记录

    :param session: SQLAlchemy Session 对象
    :param follow_id: 跟进记录主键 id
    :return: ORM 对象 或 None
    """
    return session.query(VisitFollowRecord).filter(
        VisitFollowRecord.id == follow_id).first()


def insert_follow(session, data):
    """
    新增跟进记录（纯手动写入）

    :param session: SQLAlchemy Session 对象
    :param data: 数据字典（key 为表字段名）
    :return: VisitFollowRecord ORM 对象
    """
    row = VisitFollowRecord(**data)
    session.add(row)
    session.flush()  # 取回自增 id
    return row


def update_fields(session, follow_id, fields):
    """
    按主键更新指定字段（编辑内容 / 作废置 status=0）

    :param session: SQLAlchemy Session 对象
    :param follow_id: 跟进记录主键 id
    :param fields: 待更新字段 dict（key 为表字段名）
    :return: 更新行数
    """
    if not fields:
        return 0
    result = session.execute(
        update(VisitFollowRecord)
        .where(VisitFollowRecord.id == follow_id)
        .values(**fields)
    )
    return result.rowcount


def page_follows(session, page=1, limit=20, amap_customer_id=None, channel=None):
    """
    跟进记录分页查询（M7 跟进时间轴，按跟进时间倒序，固定排除作废记录）

    :param session: SQLAlchemy Session 对象
    :param page: 页码，从 1 开始
    :param limit: 每页条数
    :param amap_customer_id: 高德客户POI编码，必填（时间轴按客户挂载）
    :param channel: 跟进渠道筛选，选填
    :return: (total, rows) 命中总数与当前页 ORM 对象列表
    """
    page = max(1, page or 1)
    limit = max(1, limit or 20)

    query = session.query(VisitFollowRecord).filter(VisitFollowRecord.status == 1)
    if amap_customer_id:
        query = query.filter(VisitFollowRecord.amap_customer_id == amap_customer_id)
    if channel:
        query = query.filter(VisitFollowRecord.channel == channel)
    total = query.count()

    query = query.order_by(VisitFollowRecord.follow_time.desc(), VisitFollowRecord.id.desc())
    rows = query.offset((page - 1) * limit).limit(limit).all()
    return total, rows
