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


def _validate_pp_name(pp_name):
    """
    校验品牌主名
    """
    if not pp_name or not pp_name.strip():
        raise ValueError("品牌主名不能为空")
    return pp_name.strip()


def get_paged_aliases(page, page_size, pp_name=None, alias_name=None):
    """
    分页获取别名列表（按品牌主名分组聚合）

    :param page: 页码
    :param page_size: 每页条数
    :param pp_name: 主名模糊搜索
    :param alias_name: 别名模糊搜索
    :return: {"total": 总条数, "data_list": 当前页数据}
    """
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 10), 100))

    with orm_session() as session:
        # 先获取匹配条件的主名列表（去重）
        pp_query = session.query(CrmPpName.pp_name.distinct())
        if pp_name:
            pp_query = pp_query.filter(CrmPpName.pp_name.like(f"%{pp_name}%"))
        if alias_name:
            pp_query = pp_query.filter(CrmPpName.alias_name.like(f"%{alias_name}%"))

        total = pp_query.count()

        pp_names = (
            pp_query.order_by(CrmPpName.pp_name.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
            .all()
        )
        pp_names = [p[0] for p in pp_names]

        if not pp_names:
            return {"total": 0, "data_list": []}

        # 查询这些主名对应的所有别名记录
        all_aliases = (
            session.query(CrmPpName)
            .filter(CrmPpName.pp_name.in_(pp_names))
            .all()
        )

        # 按主名分组
        grouped = {}
        for alias in all_aliases:
            if alias.pp_name not in grouped:
                grouped[alias.pp_name] = []
            grouped[alias.pp_name].append(alias)

        data_list = []
        for name in pp_names:
            aliases = grouped.get(name, [])
            alias_names = [a.alias_name for a in aliases]
            data_list.append({
                "pp_name": name,
                "alias_text": "，".join(alias_names),
                "items": [{"id": a.id, "alias_name": a.alias_name} for a in aliases]
            })

        return {
            "total": total,
            "data_list": data_list
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


def create_aliases_batch(pp_name, alias_names, operator=None):
    """
    批量创建别名映射（为同一主名添加多个别名），并记录操作日志

    :param pp_name: 品牌主名
    :param alias_names: 别名列表
    :param operator: 操作人
    :return: 创建的记录列表
    """
    pp_name = _validate_pp_name(pp_name)

    if not alias_names or not isinstance(alias_names, list):
        raise ValueError("别名列表不能为空")

    results = []
    with orm_session() as session:
        for alias_name in alias_names:
            alias_name = alias_name.strip() if alias_name else ""
            if not alias_name:
                continue

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
            results.append(alias.to_dict())

        session.commit()
        return results


def update_alias_group(old_pp_name, pp_name, aliases, operator=None):
    """
    按品牌主名批量更新别名映射（增删改），并记录操作日志

    :param old_pp_name: 原来的品牌主名
    :param pp_name: 新的品牌主名
    :param aliases: 别名列表，每项包含 id 和 alias_name，id 为空表示新增
    :param operator: 操作人
    :return: 更新后的主名及别名列表
    """
    old_pp_name = old_pp_name.strip() if old_pp_name else ""
    pp_name = _validate_pp_name(pp_name)

    if not aliases or not isinstance(aliases, list):
        raise ValueError("别名列表不能为空")

    with orm_session() as session:
        # 获取该主名下现有的所有别名记录
        existing = CrmPpName.get_by_pp_name(session, old_pp_name)
        existing_map = {a.id: a for a in existing}

        kept_ids = set()

        for item in aliases:
            alias_name = item.get('alias_name', '').strip()
            if not alias_name:
                continue

            alias_id = item.get('id')

            if alias_id and alias_id in existing_map:
                # 更新现有别名
                old_alias = existing_map[alias_id]
                changes = {}
                if old_alias.pp_name != pp_name:
                    changes['pp_name_old'] = old_alias.pp_name
                    changes['pp_name_new'] = pp_name
                    old_alias.pp_name = pp_name
                if old_alias.alias_name != alias_name:
                    changes['alias_name_old'] = old_alias.alias_name
                    changes['alias_name_new'] = alias_name
                    old_alias.alias_name = alias_name

                if changes:
                    session.flush()
                    CrmPpNameLog.create_log(
                        session,
                        record_id=alias_id,
                        action='update',
                        operator=operator,
                        **changes
                    )
                kept_ids.add(alias_id)
            else:
                # 新增别名
                new_alias = CrmPpName.create(session, pp_name, alias_name)
                session.flush()
                CrmPpNameLog.create_log(
                    session,
                    record_id=new_alias.id,
                    action='create',
                    pp_name_new=new_alias.pp_name,
                    alias_name_new=new_alias.alias_name,
                    operator=operator
                )
                kept_ids.add(new_alias.id)

        # 删除未保留的现有别名
        for eid, ealias in existing_map.items():
            if eid not in kept_ids:
                CrmPpNameLog.create_log(
                    session,
                    record_id=eid,
                    action='delete',
                    pp_name_old=ealias.pp_name,
                    alias_name_old=ealias.alias_name,
                    operator=operator
                )
                session.delete(ealias)
                session.flush()

        session.commit()

        # 返回更新后的数据
        updated = CrmPpName.get_by_pp_name(session, pp_name)
        return {
            "pp_name": pp_name,
            "alias_text": "，".join([a.alias_name for a in updated]),
            "items": [{"id": a.id, "alias_name": a.alias_name} for a in updated]
        }


def delete_alias_group(pp_name, operator=None):
    """
    根据品牌主名删除该主名对应的所有别名映射，并记录操作日志

    :param pp_name: 品牌主名
    :param operator: 操作人
    :return: 是否删除成功
    """
    if not pp_name or not pp_name.strip():
        raise ValueError("品牌主名不能为空")

    with orm_session() as session:
        existing = CrmPpName.get_by_pp_name(session, pp_name)
        if not existing:
            return False

        for alias in existing:
            CrmPpNameLog.create_log(
                session,
                record_id=alias.id,
                action='delete',
                pp_name_old=alias.pp_name,
                alias_name_old=alias.alias_name,
                operator=operator
            )
            session.delete(alias)
            session.flush()

        session.commit()
        return True


def update_alias(alias_id, pp_name, alias_name, operator=None):
    """
    更新别名映射（单条），并记录操作日志
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
    删除别名映射（单条），并记录操作日志
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
