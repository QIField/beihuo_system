# -*- coding:utf-8 -*-
"""
CRM 零件品牌别名服务层

负责别名映射的增删改查业务逻辑，并记录操作日志
"""

from app.models.orm_models.crm_pp_name import CrmPpName
from app.models.orm_models.crm_pp_name_log import CrmPpNameLog
from app.utils.orm import orm_session


def _validate_input(pp_name, alias_name):
    """
    校验输入参数
    """
    if not pp_name or not pp_name.strip():
        raise ValueError("品牌主名不能为空")
    if not alias_name or not alias_name.strip():
        raise ValueError("别名不能为空")


def get_paged_aliases(page, page_size, pp_name=None, alias_name=None):
    """
    分页获取别名列表

    :param page: 页码
    :param page_size: 每页条数
    :param pp_name: 主名模糊搜索
    :param alias_name: 别名模糊搜索
    :return: {"total": 总条数, "data_list": 当前页数据}
    """
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 10), 100))

    with orm_session() as session:
        total, items = CrmPpName.get_paged_aliases(
            session, page=page, page_size=page_size,
            pp_name=pp_name, alias_name=alias_name
        )
        return {
            "total": total,
            "data_list": CrmPpName.list_to_dict_list(items)
        }


def create_alias(pp_name, alias_name, operator=None):
    """
    创建别名映射，并记录操作日志
    """
    pp_name = pp_name.strip() if pp_name else ""
    alias_name = alias_name.strip() if alias_name else ""
    _validate_input(pp_name, alias_name)

    with orm_session() as session:
        alias = CrmPpName.create(session, pp_name, alias_name)

        # 记录创建日志
        CrmPpNameLog.create_log(
            session,
            record_id=alias.id,
            action='create',
            pp_name_new=alias.pp_name,
            alias_name_new=alias.alias_name,
            operator=operator
        )

        session.commit()
        return alias.to_dict()


def update_alias(alias_id, pp_name, alias_name, operator=None):
    """
    更新别名映射，并记录操作日志
    """
    if not alias_id:
        raise ValueError("ID 不能为空")

    pp_name = pp_name.strip() if pp_name else ""
    alias_name = alias_name.strip() if alias_name else ""
    _validate_input(pp_name, alias_name)

    with orm_session() as session:
        # 先查询旧数据
        old_alias = CrmPpName.get_by_id(session, alias_id)
        if not old_alias:
            return None

        pp_name_old = old_alias.pp_name
        alias_name_old = old_alias.alias_name

        alias = CrmPpName.update(session, alias_id, pp_name, alias_name)

        # 记录更新日志
        CrmPpNameLog.create_log(
            session,
            record_id=alias_id,
            action='update',
            pp_name_old=pp_name_old,
            alias_name_old=alias_name_old,
            pp_name_new=alias.pp_name,
            alias_name_new=alias.alias_name,
            operator=operator
        )

        session.commit()
        return alias.to_dict()


def delete_alias(alias_id, operator=None):
    """
    删除别名映射，并记录操作日志
    """
    if not alias_id:
        raise ValueError("ID 不能为空")

    with orm_session() as session:
        # 先查询被删数据
        old_alias = CrmPpName.get_by_id(session, alias_id)
        if not old_alias:
            return False

        pp_name_old = old_alias.pp_name
        alias_name_old = old_alias.alias_name

        result = CrmPpName.delete(session, alias_id)

        # 记录删除日志
        CrmPpNameLog.create_log(
            session,
            record_id=alias_id,
            action='delete',
            pp_name_old=pp_name_old,
            alias_name_old=alias_name_old,
            operator=operator
        )

        session.commit()
        return result
