# -*- coding:utf-8 -*-
"""
CRM 品牌别名池服务层

负责别名池的增删改查业务逻辑，并记录操作日志
"""

from app.models.orm_models.crm_pp_alias_pool import CrmPpAliasPool
from app.models.orm_models.crm_pp_alias_pool_log import CrmPpAliasPoolLog
from app.utils.orm import orm_session
from app.services.pp_alias_service.pp_alias_pool_service import clear_pool_cache


def _validate_names(names):
    """
    校验名称列表
    """
    if not names or not isinstance(names, list):
        raise ValueError("名称列表不能为空")
    valid_names = [n.strip() for n in names if n and str(n).strip()]
    if len(valid_names) < 2:
        raise ValueError("别名池至少需要 2 个不同名称")
    if len(set(n.lower() for n in valid_names)) != len(valid_names):
        raise ValueError("名称列表中存在重复项（不区分大小写）")
    return valid_names


def _get_next_pool_id(session):
    """
    获取下一个可用的 pool_id
    """
    from sqlalchemy import func as sql_func
    max_id = session.query(sql_func.max(CrmPpAliasPool.pool_id)).scalar()
    return (max_id or 0) + 1


def _check_names_conflict(session, names, exclude_pool_id=None):
    """
    检查名称是否已存在于其他池中
    :return: 冲突的名称列表 [(name, existing_pool_id), ...]
    """
    conflicts = []
    for name in names:
        existing = session.query(CrmPpAliasPool).filter(
            CrmPpAliasPool.name == name
        ).first()
        if existing and existing.pool_id != exclude_pool_id:
            conflicts.append((name, existing.pool_id))
    return conflicts


def get_paged_pools(page, page_size, name_keyword=None):
    """
    分页获取别名池列表

    :param page: 页码
    :param page_size: 每页条数
    :param name_keyword: 名称关键词模糊搜索
    :return: {"total": 总条数, "data_list": 当前页数据}
    """
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 10), 100))

    with orm_session() as session:
        query = session.query(CrmPpAliasPool)

        if name_keyword:
            # 先查出匹配的名称对应的 pool_id
            matched = session.query(CrmPpAliasPool.pool_id).filter(
                CrmPpAliasPool.name.like(f"%{name_keyword}%")
            ).distinct().all()
            matched_pool_ids = [m[0] for m in matched]
            if not matched_pool_ids:
                return {"total": 0, "data_list": []}
            query = query.filter(CrmPpAliasPool.pool_id.in_(matched_pool_ids))

        # 获取所有涉及的 pool_id（去重）
        all_pool_ids = [r[0] for r in session.query(
            CrmPpAliasPool.pool_id.distinct()
        ).order_by(CrmPpAliasPool.pool_id.desc()).all()]

        total = len(all_pool_ids)

        start = (page - 1) * page_size
        page_pool_ids = all_pool_ids[start:start + page_size]

        if not page_pool_ids:
            return {"total": 0, "data_list": []}

        # 查询这些 pool 的所有成员
        members = session.query(CrmPpAliasPool).filter(
            CrmPpAliasPool.pool_id.in_(page_pool_ids)
        ).all()

        grouped = {}
        for m in members:
            grouped.setdefault(m.pool_id, []).append(m)

        data_list = []
        for pid in page_pool_ids:
            pool_members = grouped.get(pid, [])
            names = [m.name for m in pool_members]
            data_list.append({
                "pool_id": pid,
                "names": names,
                "name_text": ", ".join(names),
                "count": len(names),
                "items": [{"id": m.id, "name": m.name} for m in pool_members]
            })

        return {"total": total, "data_list": data_list}


def create_pool(names, operator=None):
    """
    创建新别名池

    :param names: 名称列表（如 ["博世", "BOSCH"]）
    :param operator: 操作人
    :return: 创建后的池数据 {"pool_id": ..., "names": [...]}
    """
    names = _validate_names(names)

    with orm_session() as session:
        conflicts = _check_names_conflict(session, names)
        if conflicts:
            conflict_names = ", ".join([c[0] for c in conflicts])
            raise ValueError(f"以下名称已存在于其他池中: {conflict_names}")

        pool_id = _get_next_pool_id(session)

        for name in names:
            CrmPpAliasPool.create(session, pool_id, name)

        CrmPpAliasPoolLog.create_log(
            session,
            action='create',
            pool_id=pool_id,
            names_new=names,
            operator=operator
        )

        session.commit()
        clear_pool_cache()

        return {
            "pool_id": pool_id,
            "names": names,
            "name_text": ", ".join(names),
            "count": len(names)
        }


def update_pool(pool_id, names, operator=None):
    """
    更新别名池成员（全量替换）

    :param pool_id: 池编号
    :param names: 新的名称列表
    :param operator: 操作人
    :return: 更新后的池数据
    """
    if not pool_id:
        raise ValueError("池编号不能为空")
    names = _validate_names(names)

    with orm_session() as session:
        existing = CrmPpAliasPool.get_by_pool_id(session, pool_id)
        if not existing:
            raise ValueError("别名池不存在")

        old_names = [e.name for e in existing]

        conflicts = _check_names_conflict(session, names, exclude_pool_id=pool_id)
        if conflicts:
            conflict_names = ", ".join([c[0] for c in conflicts])
            raise ValueError(f"以下名称已存在于其他池中: {conflict_names}")

        # 删除旧成员
        CrmPpAliasPool.delete_by_pool_id(session, pool_id)
        session.flush()

        # 插入新成员
        for name in names:
            CrmPpAliasPool.create(session, pool_id, name)

        CrmPpAliasPoolLog.create_log(
            session,
            action='update',
            pool_id=pool_id,
            names_old=old_names,
            names_new=names,
            operator=operator
        )

        session.commit()
        clear_pool_cache()

        return {
            "pool_id": pool_id,
            "names": names,
            "name_text": ", ".join(names),
            "count": len(names)
        }


def delete_pool(pool_id, operator=None):
    """
    删除整个别名池

    :param pool_id: 池编号
    :param operator: 操作人
    :return: 是否删除成功
    """
    if not pool_id:
        raise ValueError("池编号不能为空")

    with orm_session() as session:
        existing = CrmPpAliasPool.get_by_pool_id(session, pool_id)
        if not existing:
            return False

        old_names = [e.name for e in existing]

        CrmPpAliasPool.delete_by_pool_id(session, pool_id)

        CrmPpAliasPoolLog.create_log(
            session,
            action='delete',
            pool_id=pool_id,
            names_old=old_names,
            operator=operator
        )

        session.commit()
        clear_pool_cache()
        return True


# ============ 兼容旧接口（内部调用仍可用） ============

def create_alias(pp_name, alias_name, operator=None):
    """
    【兼容】创建别名映射（单条）
    实际行为：将 pp_name + alias_name 作为一个 2 成员池创建
    """
    pp_name = (pp_name or "").strip()
    alias_name = (alias_name or "").strip()
    if not pp_name or not alias_name:
        raise ValueError("名称不能为空")
    return create_pool([pp_name, alias_name], operator=operator)


def create_aliases_batch(pp_name, alias_names, operator=None):
    """
    【兼容】批量创建别名映射
    实际行为：将 pp_name + 所有 alias_names 作为一个池创建
    """
    pp_name = (pp_name or "").strip()
    if not pp_name:
        raise ValueError("品牌主名不能为空")
    if not alias_names or not isinstance(alias_names, list):
        raise ValueError("别名列表不能为空")
    names = [pp_name] + [n.strip() for n in alias_names if n and str(n).strip()]
    return create_pool(names, operator=operator)


def update_alias_group(old_pp_name, pp_name, aliases, operator=None):
    """
    【兼容】按品牌主名批量更新别名映射
    实际行为：找到包含 old_pp_name 的池，全量替换为 pp_name + 所有 alias_names
    """
    old_pp_name = (old_pp_name or "").strip()
    pp_name = (pp_name or "").strip()
    if not old_pp_name or not pp_name:
        raise ValueError("品牌主名不能为空")
    if not aliases or not isinstance(aliases, list):
        raise ValueError("别名列表不能为空")

    with orm_session() as session:
        # 查找包含 old_pp_name 的池
        member = session.query(CrmPpAliasPool).filter(
            CrmPpAliasPool.name == old_pp_name
        ).first()
        if not member:
            raise ValueError("记录不存在")

        pool_id = member.pool_id
        names = [pp_name] + [a.get('alias_name', '').strip() for a in aliases if a.get('alias_name')]
        names = list(dict.fromkeys(names))  # 去重保序
        return update_pool(pool_id, names, operator=operator)


def delete_alias_group(pp_name, operator=None):
    """
    【兼容】按品牌主名删除别名组
    实际行为：找到包含 pp_name 的池并删除
    """
    pp_name = (pp_name or "").strip()
    if not pp_name:
        raise ValueError("品牌主名不能为空")

    with orm_session() as session:
        member = session.query(CrmPpAliasPool).filter(
            CrmPpAliasPool.name == pp_name
        ).first()
        if not member:
            return False
        return delete_pool(member.pool_id, operator=operator)


def get_paged_aliases(page, page_size, pp_name=None, alias_name=None):
    """
    【兼容】分页获取别名列表（按品牌主名分组聚合）
    实际行为：调用 get_paged_pools，将 name_keyword 设为 pp_name 或 alias_name
    """
    name_keyword = pp_name or alias_name
    return get_paged_pools(page, page_size, name_keyword=name_keyword)
