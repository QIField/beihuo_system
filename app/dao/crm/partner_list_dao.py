# -*- coding:utf-8 -*-
# @Time    : 2026/4/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : partner_list_dao.py
# @Software: PyCharm

from sqlalchemy.dialects.mysql import insert

from app.models.orm_models.crm.partner_list import PartnerList


def get_by_partner_id(session, partner_id):
    """
    根据 partner_id 获取合作伙伴

    :param session: SQLAlchemy Session 对象
    :param partner_id: 合作伙伴 ID
    :return: Partner 对象或 None
    """
    return session.query(PartnerList).filter_by(partner_id=partner_id).first()


def get_by_sap_no(session, sap_no):
    """
    根据 sap_no 获取合作伙伴

    :param session: SQLAlchemy Session 对象
    :param sap_no: SAP编号
    :return: Partner 对象或 None
    """
    return session.query(PartnerList).filter_by(sap_no=sap_no).first()


def get_by_fullname(session, fullname):
    """
    根据 fullname 获取合作伙伴列表

    :param session: SQLAlchemy Session 对象
    :param fullname: 全名
    :return: Partner 对象列表
    """
    return session.query(PartnerList).filter_by(fullname=fullname).all()


def count_all(session):
    """
    统计合作伙伴总数

    :param session: SQLAlchemy Session 对象
    :return: 总记录数
    """
    return session.query(PartnerList).count()


def list_by_page(session, offset, limit):
    """
    分页读取合作伙伴记录

    :param session: SQLAlchemy Session 对象
    :param offset: 偏移量
    :param limit: 每页大小
    :return: Partner 对象列表
    """
    return session.query(PartnerList).offset(offset).limit(limit).all()


def search_by_fullname(session, keyword, limit=10):
    """
    根据客户名称关键词对 fullname（全名）进行模糊搜索

    :param session: SQLAlchemy Session 对象
    :param keyword: 客户名称关键词
    :param limit: 返回条数上限
    :return: 查询结果行列表（含 partner_id、fullname、short_name 等字段）
    """
    return session.query(
        PartnerList.partner_id,
        PartnerList.fullname,
        PartnerList.short_name,
        PartnerList.contacts,
        PartnerList.contacts_phone
    ).filter(
        PartnerList.fullname.like(f"%{keyword}%")
    ).order_by(
        PartnerList.fullname
    ).limit(limit).all()


def bulk_insert(session, data_list):
    """
    批量插入数据

    :param session: SQLAlchemy Session 对象
    :param data_list: 数据字典列表
    :return: 插入的记录数
    """
    if not data_list:
        return 0

    objects = [PartnerList(**data) for data in data_list]
    session.bulk_save_objects(objects)
    return len(objects)


def bulk_upsert(session, data_list):
    """
    批量插入或更新数据（以 partner_id 为唯一索引）

    使用 SQLAlchemy 的 insert ... on_duplicate_key_update 方法
    底层调用 MySQL 的 INSERT ... ON DUPLICATE KEY UPDATE
    一次插入多条数据，性能更优

    :param session: SQLAlchemy Session 对象
    :param data_list: 数据字典列表
    :return: 处理的记录数
    """
    if not data_list:
        return 0

    # 构建插入语句
    stmt = insert(PartnerList).values(data_list)

    # 构建更新字典：排除不需要更新的列
    update_dict = {}
    for column in PartnerList.__table__.columns:
        col_name = column.name
        if col_name not in ['partner_id', 'created_at']:
            update_dict[col_name] = getattr(stmt.inserted, col_name)

    # 使用 on_duplicate_key_update
    stmt = stmt.on_duplicate_key_update(update_dict)

    # 执行批量插入
    session.execute(stmt)

    return len(data_list)


def list_to_dict_list(obj_list):
    """
    将对象列表转换为字典列表

    支持两种输入类型：
    1. PartnerList 模型对象列表
    2. SQLAlchemy Row 对象列表（原生SQL查询结果）

    :param obj_list: PartnerList 对象列表 或 Row 对象列表
    :return: 字典列表
    """
    if not obj_list:
        return []

    result = []
    for obj in obj_list:
        if hasattr(obj, 'to_dict'):
            # 是模型对象，调用 to_dict 方法
            result.append(obj.to_dict())
        else:
            # 是 Row 对象，转换为字典并处理特殊类型
            try:
                # 尝试使用 _asdict() 方法（适用于 SQLAlchemy 1.4+）
                row_dict = obj._asdict()
            except AttributeError:
                # 备用方法：手动构建字典
                row_dict = {}
                for key in obj.keys():
                    row_dict[key] = obj[key]
            # 处理 Numeric 类型，转换为 float
            for key, value in row_dict.items():
                if hasattr(value, 'real') and hasattr(value, 'imag'):
                    # Decimal/Numeric 类型
                    row_dict[key] = float(value)
            result.append(row_dict)
    return result