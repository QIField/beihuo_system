# -*- coding:utf-8 -*-
# @Time    : 2026/09/13
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : benz_error_oe_dao.py

"""
奔驰错误 OE 记录 DAO

职责：benz_error_oe 表的批量查询与批量插入。
"""

from app.models.orm_models.car_parts_library.benz_error_oe import BenzErrorOe



def batch_query_existing(oes,session):
    """
    批量查询已存在的 OE 编号

    :param oes: OE 编号列表
    :return: 已存在于表中的 OE 编号列表
    """
    if not oes:
        return []
    rows = session.query(BenzErrorOe.oe).filter(BenzErrorOe.oe.in_(oes)).all()
    return [row[0] for row in rows]


def batch_insert(oes,session, remark=None):
    """
    批量插入 OE 记录，返回插入条数

    :param oes: OE 编号列表
    :param remark: 备注（可选）
    """
    if not oes:
        return 0
    records = [BenzErrorOe(oe=oe, remark=remark) for oe in oes]
    session.add_all(records)
    return len(records)


def query_page(session, page=1, page_size=10, keyword=None):
    """
    分页查询错误 OE 记录（仅查询状态为 0-未入别名库 的记录）

    :param session: ORM Session
    :param page: 页码，默认1
    :param page_size: 每页条数，默认10
    :param keyword: 关键字筛选（可选），模糊匹配 OE 编号
    :return: (总条数, 记录字典列表)
    """
    query = session.query(BenzErrorOe).filter(BenzErrorOe.status == 0)
    if keyword:
        query = query.filter(BenzErrorOe.oe.like(f'%{keyword}%'))

    total = query.count()
    offset = (page - 1) * page_size
    rows = query.order_by(BenzErrorOe.id.desc()).offset(offset).limit(page_size).all()
    return total, [row.to_dict() for row in rows]


def update_status_by_oe(session, oe, status):
    """
    更新指定 OE 记录的状态

    :param session: ORM Session
    :param oe: OE 编号
    :param status: 状态，0-未入别名库 1-已入
    :return: 更新的记录数
    """
    if not oe:
        return 0
    return session.query(BenzErrorOe).filter(
        BenzErrorOe.oe == oe
    ).update({'status': status}, synchronize_session=False)
