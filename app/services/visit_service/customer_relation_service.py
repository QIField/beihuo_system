# -*- coding:utf-8 -*-
# @Time    : 2026/10/13 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : customer_relation_service.py
# @Software: PyCharm
# 客户绑定服务（M8，设计文档 doc/客访管理/03-高德客户档案与客户绑定模块设计.md 第三节）
# 绑定关系为 1:N：一条高德客户可绑定多条CRM客户（追加式绑定，同一对重复绑定幂等），
# 一条CRM客户仅归属一个高德客户（uk_partner_id 兜底）。
# 绑定 = upsert visit_customer_relation（同对更新、新对插入）+ 回写 visit_amap_customer.status=1（同一事务）。

from app.dao.visit_dao import visit_customer_relation_dao, visit_amap_customer_dao
from app.models.orm_models.crm.partner_list import PartnerList
from app.models.orm_models.visit.visit_amap_customer import VisitAmapCustomer
from app.utils.orm.session import orm_session


def _fmt_datetime(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def search_crm_partners(keyword, limit=20):
    """
    绑定表单的 CRM 客户搜索（客户名称/简称/记忆代码模糊匹配）

    :param keyword: 搜索关键词，必填
    :param limit: 返回条数上限（最大 50）
    :return: {'list': [{partner_id, fullname, short_name, remenber_code, region, real_name, level_name}]}
    """
    keyword = (keyword or "").strip()
    if not keyword:
        raise ValueError("请输入搜索关键词")
    try:
        limit = min(max(1, int(limit)), 50)
    except (TypeError, ValueError):
        limit = 20

    with orm_session() as session:
        rows = visit_customer_relation_dao.search_crm_partners(session, keyword, limit)
        # 会话内完成序列化，避免会话关闭后访问过期实例（DetachedInstanceError）
        items = [{
            "partner_id": r.partner_id,
            "fullname": r.fullname,
            "short_name": r.short_name,
            "remenber_code": r.remenber_code,
            "region": r.region,
            "real_name": r.real_name,
            "level_name": r.level_name,
        } for r in rows]
    return {"list": items}


def list_relations(amap_customer_id):
    """
    查询高德客户当前全部绑定（1:N，绑定弹窗展示已绑定列表 + 解绑操作用）

    绑定客户可能已被 partner_list 周刷新删除，跳过缺失项（口径同详情聚合 crm_list）。

    :param amap_customer_id: 高德客户POI编码
    :return: {'list': [{partner_id, fullname, remenber_code, level_name, region, real_name, bind_remark, bind_time}]}
    """
    if not amap_customer_id:
        raise ValueError("缺少高德客户标识")

    with orm_session() as session:
        rows = visit_customer_relation_dao.list_by_amap_customer_id(session, amap_customer_id)
        if not rows:
            return {"list": []}
        partners = session.query(PartnerList).filter(
            PartnerList.partner_id.in_([r.partner_id for r in rows])).all()
        partner_map = {p.partner_id: p for p in partners}

        items = []
        for relation in rows:
            partner = partner_map.get(relation.partner_id)
            if partner is None:
                continue
            items.append({
                "partner_id": partner.partner_id,
                "fullname": partner.fullname,
                "remenber_code": partner.remenber_code,
                "level_name": partner.level_name,
                "region": partner.region,
                "real_name": partner.real_name,
                "bind_remark": relation.bind_remark,
                # created_at 为绑定时间（datetime），转 YYYY-MM-DD HH:mm 展示
                "bind_time": _fmt_datetime(relation.created_at),
            })
    return {"list": items}


def unbind_customer(amap_customer_id, partner_id):
    """
    解绑高德客户与CRM客户（03 文档 3.2 绑定流程的逆向操作；误删恢复 = 重新关联一次）

    校验：高德客户存在、绑定行存在（不存在提示可能已解绑）。
    同一事务：物理删除绑定行 + 重算 visit_amap_customer.status（仍有绑定保持 1，全部解绑回落 0）。

    :param amap_customer_id: 高德客户POI编码
    :param partner_id: CRM客户ID
    :return: {'amap_customer_id': ..., 'partner_id': ..., 'remaining': 解绑后剩余绑定数}
    """
    if not amap_customer_id:
        raise ValueError("缺少高德客户标识")
    try:
        partner_id = int(partner_id)
    except (TypeError, ValueError):
        raise ValueError("请选择要解绑的CRM客户")

    remaining = 0
    with orm_session() as session:
        amap = session.query(VisitAmapCustomer).filter(
            VisitAmapCustomer.amap_poi_id == amap_customer_id).first()
        if not amap:
            raise ValueError("高德客户不存在或已被删除")

        if not visit_customer_relation_dao.get_by_amap_and_partner(session, amap_customer_id, partner_id):
            raise ValueError("该绑定关系不存在，可能已被解绑")

        # 同一事务：删除绑定行 + 重算状态
        visit_customer_relation_dao.delete_relation(session, amap_customer_id, partner_id)
        remaining = len(visit_customer_relation_dao.list_by_amap_customer_id(session, amap_customer_id))
        if remaining == 0:
            amap.status = 0

    return {"amap_customer_id": amap_customer_id, "partner_id": partner_id, "remaining": remaining}


def bind_customer(amap_customer_id, partner_id, bind_remark="", operator=""):
    """
    绑定高德客户与CRM客户（03 文档 3.2 绑定流程；1:N 追加式）

    校验：
    1. 高德客户存在且状态允许绑定（status=0 首次绑定 / 1 追加关联；status=2 无效拒绝）
    2. partner_id 在 partner_list 中仍存在（防每周二全量刷新后失效）
    3. 该 CRM 客户未被其他高德客户绑定（CRM侧 1:1，应用层预检 + uk_partner_id 数据库兜底）
    4. 该 CRM 客户未与当前高德客户重复绑定（搜索接口已排除已绑定客户，此处服务端兜底）

    同一事务：upsert 绑定行（同一对重复绑定更新、新对插入）+ update visit_amap_customer.status = 1。

    :param amap_customer_id: 高德客户POI编码
    :param partner_id: CRM客户ID
    :param bind_remark: 绑定备注（名称差异说明）
    :param operator: 操作人（session.username）
    :return: {'amap_customer_id': ..., 'partner_id': ..., 'appended': 是否追加关联（该高德客户已有其他绑定）}
    """
    if not amap_customer_id:
        raise ValueError("缺少高德客户标识")
    try:
        partner_id = int(partner_id)
    except (TypeError, ValueError):
        raise ValueError("请选择要关联的CRM客户")

    # 幂等建表（首次绑定时自动创建，对应 sql/visit/visit_customer_relation.sql）
    visit_customer_relation_dao.ensure_table()

    appended = False
    try:
        with orm_session() as session:
            # 1. 高德客户状态校验
            amap = session.query(VisitAmapCustomer).filter(
                VisitAmapCustomer.amap_poi_id == amap_customer_id).first()
            if not amap:
                raise ValueError("高德客户不存在或已被删除")
            if amap.status == 2:
                raise ValueError("该客户已标记无效，不可绑定")
            appended = amap.status == 1

            # 2. CRM 客户存在性校验（partner_list 每周二全量刷新可能删除客户）
            partner = session.query(PartnerList).filter(
                PartnerList.partner_id == partner_id).first()
            if not partner:
                raise ValueError("CRM客户不存在（可能已被删除），请重新选择")

            # 3. 冲突预检：CRM侧 1:1，该 CRM 客户已被其他高德客户绑定
            existed = visit_customer_relation_dao.get_by_partner_id(session, partner_id)
            if existed and existed.amap_customer_id != amap_customer_id:
                raise ValueError("该CRM客户已被其他高德客户关联，请重新选择")

            # 4. 冲突预检：同一对（高德 + CRM）重复绑定
            if existed and existed.amap_customer_id == amap_customer_id:
                raise ValueError("该CRM客户已与当前高德客户关联，请勿重复添加")

            # 5. 同一事务：插入或更新绑定行 + 回写状态
            visit_customer_relation_dao.upsert_relation(
                session, amap_customer_id, partner_id, operator, bind_remark)
            amap.status = 1
    except ValueError:
        raise
    except Exception as e:
        # 并发绑定触发 uk_partner_id 唯一键冲突（03 文档 5.3）
        if "Duplicate entry" in str(e):
            raise ValueError("绑定冲突：该客户可能刚被其他人关联，请刷新后重试")
        raise

    return {"amap_customer_id": amap_customer_id, "partner_id": partner_id, "appended": appended}
