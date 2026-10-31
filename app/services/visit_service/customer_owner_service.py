# -*- coding:utf-8 -*-
# @Time    : 2026/10/28 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : customer_owner_service.py
# @Software: PyCharm
# 负责人绑定服务（设计文档 doc/客访管理/07-负责人绑定.md 第三节）
# 负责人（crmapp_users 系统用户）与高德客户（visit_amap_customer）多对多绑定；
# 只存当前有效关系，解绑即物理删除该行、不留历史。
# 绑定 = INSERT visit_customer_owner（同一对重复绑定幂等返回成功，uk_customer_user 兜底并发）。

from sqlalchemy import or_

from app.dao.visit_dao import visit_amap_customer_dao, visit_customer_owner_dao
from app.models.orm_models.system_models.crmapp_users import CrmappUsers
from app.models.orm_models.visit.visit_amap_customer import VisitAmapCustomer
from app.utils.orm.session import orm_session


def _fmt_datetime(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def _parse_customer_id(visit_amap_customer_id):
    """客户物理主键解析与校验（visit_amap_customer.id，与详情页 ?id= 口径一致）"""
    try:
        customer_id = int(str(visit_amap_customer_id).strip())
    except (TypeError, ValueError):
        raise ValueError("客户标识不合法")
    if customer_id <= 0:
        raise ValueError("缺少客户标识")
    return customer_id


def _parse_user_id(user_id):
    """负责人ID解析与校验（crmapp_users.id）"""
    try:
        uid = int(str(user_id).strip())
    except (TypeError, ValueError):
        raise ValueError("请选择负责人")
    if uid <= 0:
        raise ValueError("请选择负责人")
    return uid


def search_owner_candidates(keyword="", limit=50):
    """
    负责人候选搜索（绑定弹层选用户，来源 crmapp_users，用户名/部门模糊匹配）

    :param keyword: 搜索关键词，选填（空 = 返回前 limit 个用户）
    :param limit: 返回条数上限（最大 100）
    :return: {'list': [{user_id, username, department, job_level}]}
    """
    keyword = (keyword or "").strip()
    try:
        limit = min(max(1, int(limit)), 100)
    except (TypeError, ValueError):
        limit = 50

    with orm_session() as session:
        query = session.query(CrmappUsers)
        if keyword:
            kw = f"%{keyword}%"
            query = query.filter(or_(
                CrmappUsers.username.like(kw),
                CrmappUsers.department.like(kw),
            ))
        rows = query.order_by(CrmappUsers.id).limit(limit).all()
        # 会话内完成序列化，避免会话关闭后访问过期实例（DetachedInstanceError）
        items = [{
            "user_id": u.id,
            "username": u.username,
            "department": u.department,
            "job_level": u.job_level,
        } for u in rows]
    return {"list": items}


def list_owners(visit_amap_customer_id):
    """
    查询某客户的负责人列表（详情页"负责人"区域展示）

    负责人已被 crmapp_users 删除的行跳过（系统自有表极少发生，防御性降级）。

    :param visit_amap_customer_id: visit_amap_customer.id（物理主键）
    :return: {'list': [{user_id, username, department, job_level, bind_time}]}
    """
    customer_id = _parse_customer_id(visit_amap_customer_id)

    with orm_session() as session:
        rows = visit_customer_owner_dao.list_by_customer_id(session, customer_id)
        if not rows:
            return {"list": []}
        users = session.query(CrmappUsers).filter(
            CrmappUsers.id.in_([r.user_id for r in rows])).all()
        user_map = {u.id: u for u in users}

        items = []
        for owner in rows:
            user = user_map.get(owner.user_id)
            if user is None:
                continue
            items.append({
                "user_id": user.id,
                "username": user.username,
                "department": user.department,
                "job_level": user.job_level,
                # created_at 为绑定时间（datetime），转 YYYY-MM-DD HH:mm 展示
                "bind_time": _fmt_datetime(owner.created_at),
            })
    return {"list": items}


def bind_owner(visit_amap_customer_id, user_id, operator):
    """
    绑定负责人（07 文档 绑定流程；多对多，可绑定多个负责人）

    校验：
    1. visit_amap_customer_id 在 visit_amap_customer 中存在且 status != 2（无效客户不可绑）
    2. user_id 在 crmapp_users 中存在（系统自有表，仍校验后写入防脏数据）
    3. 同对已绑定 → 幂等返回成功（不重复建行）

    :param visit_amap_customer_id: visit_amap_customer.id（物理主键）
    :param user_id: 负责人ID（crmapp_users.id）
    :param operator: 操作用户id（当前登录用户 session.user_id，不从请求参数传入）
    :return: {'visit_amap_customer_id': ..., 'user_id': ..., 'idempotent': 是否为重复绑定幂等成功}
    """
    customer_id = _parse_customer_id(visit_amap_customer_id)
    uid = _parse_user_id(user_id)
    try:
        operator = int(operator)
    except (TypeError, ValueError):
        raise ValueError("当前登录状态异常，请重新登录后再试")

    # 幂等建表（首次绑定时自动创建，对应 sql/visit/visit_customer_owner.sql）
    visit_customer_owner_dao.ensure_table()

    idempotent = False
    try:
        with orm_session() as session:
            # 1. 客户存在性与状态校验（无效客户不可绑）
            amap = visit_amap_customer_dao.get_by_id(session, customer_id)
            if not amap:
                raise ValueError("高德客户不存在或已被删除")
            if amap.status == 2:
                raise ValueError("该客户已标记无效，不可绑定负责人")

            # 2. 负责人存在性校验（crmapp_users 系统自有表，校验后写入防脏数据）
            user = session.query(CrmappUsers).filter(CrmappUsers.id == uid).first()
            if not user:
                raise ValueError("负责人不存在，请重新选择")

            # 3. 同对已绑定 → 幂等返回成功（不重复建行）
            existed = visit_customer_owner_dao.get_by_customer_and_user(session, customer_id, uid)
            if existed:
                idempotent = True
            else:
                visit_customer_owner_dao.insert_owner(session, customer_id, uid, operator)
    except ValueError:
        raise
    except Exception as e:
        # 并发绑定触发 uk_customer_user 唯一键冲突 → 兜底按幂等成功处理
        if "Duplicate entry" in str(e):
            idempotent = True
        else:
            raise

    return {"visit_amap_customer_id": customer_id, "user_id": uid, "idempotent": idempotent}


def unbind_owner(visit_amap_customer_id, user_id):
    """
    解绑负责人 = 物理删除该行（uk_customer_user 定位唯一行，解绑后可随时重新绑定）

    校验：绑定行存在（不存在提示可能已解绑）。

    :param visit_amap_customer_id: visit_amap_customer.id（物理主键）
    :param user_id: 负责人ID（crmapp_users.id）
    :return: {'visit_amap_customer_id': ..., 'user_id': ..., 'remaining': 解绑后剩余负责人数}
    """
    customer_id = _parse_customer_id(visit_amap_customer_id)
    uid = _parse_user_id(user_id)

    remaining = 0
    with orm_session() as session:
        if not visit_customer_owner_dao.get_by_customer_and_user(session, customer_id, uid):
            raise ValueError("该绑定关系不存在，可能已被解绑")

        visit_customer_owner_dao.delete_owner(session, customer_id, uid)
        remaining = len(visit_customer_owner_dao.list_by_customer_id(session, customer_id))

    return {"visit_amap_customer_id": customer_id, "user_id": uid, "remaining": remaining}
