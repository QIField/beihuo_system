# -*- coding:utf-8 -*-
# @Time    : 2026/09/13
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_alias_dao.py

"""
配件别名 DAO

职责：car_parts_alias 表的查询与插入。
"""

from app.models.orm_models.car_parts_library.car_parts_alias import CarPartsAlias
from app.utils.orm.session import orm_session


def query_by_part_number_alias(part_number_alias, session):
    """
    根据配件别名查询记录，返回一条

    :param part_number_alias: 配件别名
    :param session: ORM Session
    :return: CarPartsAlias 对象，不存在时返回 None
    """
    if not part_number_alias:
        return None
    return session.query(CarPartsAlias).filter(
        CarPartsAlias.part_number_alias == part_number_alias
    ).first()


def query_page_group_by_part_number(session, page=1, page_size=10, keyword=None):
    """
    按配件编号去重分页查询，返回当前页的 part_number 及其别名原始数据

    :param session: ORM Session
    :param page: 页码，默认1
    :param page_size: 每页条数，默认10
    :param keyword: 关键字筛选（可选），模糊匹配配件编号
    :return: (聚合后的总条数, part_number 列表, (part_number, part_number_alias) 元组列表)
    """
    query = session.query(CarPartsAlias.part_number).group_by(CarPartsAlias.part_number)
    if keyword:
        query = query.filter(CarPartsAlias.part_number.like(f'%{keyword}%'))

    total = query.count()
    offset = (page - 1) * page_size
    part_number_rows = query.order_by(
        CarPartsAlias.part_number.asc()
    ).offset(offset).limit(page_size).all()
    part_numbers = [row[0] for row in part_number_rows]

    if not part_numbers:
        return total, part_numbers, []

    alias_rows = session.query(
        CarPartsAlias.part_number,
        CarPartsAlias.part_number_alias,
    ).filter(
        CarPartsAlias.part_number.in_(part_numbers)
    ).order_by(
        CarPartsAlias.id.asc()
    ).all()
    return total, part_numbers, [(row[0], row[1]) for row in alias_rows]


def insert(session, part_number, part_number_alias, remark=None):
    """
    新增一条别名记录

    :param session: ORM Session
    :param part_number: 配件编号
    :param part_number_alias: 配件别名
    :param remark: 备注（可选）
    :return: CarPartsAlias 对象
    """
    record = CarPartsAlias(
        part_number=part_number,
        part_number_alias=part_number_alias,
        remark=remark,
    )
    session.add(record)
    return record


def batch_insert(session, records):
    """
    批量新增别名记录

    :param session: ORM Session
    :param records: [{'part_number': ..., 'part_number_alias': ..., 'remark': ...}, ...]
    :return: 新增记录数
    """
    if not records:
        return 0
    objs = [
        CarPartsAlias(
            part_number=r.get('part_number'),
            part_number_alias=r.get('part_number_alias'),
            remark=r.get('remark'),
        )
        for r in records
    ]
    session.add_all(objs)
    return len(objs)


def query_by_part_number(part_number, session):
    """
    根据配件编号查询其下的所有别名记录

    :param part_number: 配件编号
    :param session: ORM Session
    :return: CarPartsAlias 对象列表
    """
    if not part_number:
        return []
    return session.query(CarPartsAlias).filter(
        CarPartsAlias.part_number == part_number
    ).order_by(CarPartsAlias.id.asc()).all()
