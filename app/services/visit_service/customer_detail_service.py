# -*- coding:utf-8 -*-
# @Time    : 2026/10/14
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : customer_detail_service.py
# @Software: PyCharm
# 客户详情聚合服务（详情头部 + 基础档案，01-主设计文档 第六节）
# 接口层见 app/api/visit/visit_detail_api.py（GET /new/api/visit/customers/<poi>）；
# 列表服务见 amap_customer_service.py，CRM 绑定桥接见 customer_relation_service.py，
# 指标卡与近30天动态（/stats 实时聚合）待后续接入。

from datetime import datetime

from app.dao.visit_dao import visit_amap_customer_dao, visit_customer_relation_dao
from app.models.orm_models.crm.partner_list import PartnerList
from app.services.visit_service.amap_customer_service import STATUS_LABELS
from app.utils.orm.session import orm_session


def _fmt_datetime(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def _fmt_date_ts(ts):
    """秒级时间戳 → YYYY-MM-DD（空/非法返回 None，防全零幽灵时间）"""
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return None


def get_customer_detail(customer_id):
    """
    客户详情聚合（详情头部 + 基础档案，01 文档第六节）

    - customer：头部展示字段（id、双名称、关联状态、类型·主修品牌）
    - amap：高德端采集信息（visit_amap_customer 采集原文透传）
    - crm_list：CRM端销售信息列表（visit_customer_relation 绑定桥接 partner_list 只读字段，
      1:N 绑定，按绑定时间倒序）；未关联或绑定客户已被 partner_list 周刷新删除时为空数组
      （03 文档第五节降级展示）
    - 流失预警判定暂不开放（阈值 A30/B45/C60/D90 待业务给数），指标卡（/stats）待后续接入

    :param customer_id: visit_amap_customer 物理主键 id（URL 中避免透传含逗号的 POI 编码）
    :return: {'customer': {...}, 'amap': {...}, 'crm_list': [{...}]}
    """
    try:
        customer_id = int(str(customer_id).strip())
    except (TypeError, ValueError):
        raise ValueError("客户标识不合法")
    if customer_id <= 0:
        raise ValueError("缺少客户标识")

    with orm_session() as session:
        row = visit_amap_customer_dao.get_by_id(session, customer_id)
        if not row:
            raise ValueError("客户不存在或已被删除")

        # 1:N 绑定：一条高德客户可关联多条CRM客户，按绑定时间倒序
        relations = visit_customer_relation_dao.list_by_amap_customer_id(session, row.amap_poi_id)
        partner_map = {}
        if relations:
            partners = session.query(PartnerList).filter(
                PartnerList.partner_id.in_([r.partner_id for r in relations])).all()
            partner_map = {p.partner_id: p for p in partners}

        # 会话内完成序列化，避免会话关闭后访问过期实例（DetachedInstanceError）
        customer = {
            "id": row.id,
            "poi": row.amap_poi_id,
            "customer_name": row.customer_name,
            "address": row.address,
            "tag": row.tag,
            "status": row.status,
            "status_label": STATUS_LABELS.get(row.status, "未知"),  # pyright: ignore[reportCallIssue, reportArgumentType]
            "customer_type": row.customer_type,
            "main_repair_brands": row.main_repair_brands,
            "business_circle": row.business_circle,
            "last_visit_time": _fmt_datetime(row.last_visit_time),
        }
        amap = {
            "customer_name": row.customer_name,
            "address": row.address,
            "contact_person": row.contact_person,
            "customer_type": row.customer_type,
            "staff_count": row.staff_count,
            "station_count": row.station_count,
            "purchase_channels": row.purchase_channels,
            "goods_habit": row.goods_habit,
            "coop_merchants": row.coop_merchants,
            "focus_points": row.focus_points,
            "main_repair_brands": row.main_repair_brands,
            "remark": row.remark,
            "visit_time": _fmt_datetime(row.visit_time),
        }
        # 绑定行按绑定时间倒序；绑定客户可能已被 partner_list 周刷新删除，跳过缺失项
        crm_list = []
        for relation in relations:
            partner = partner_map.get(relation.partner_id)
            if partner is None:
                continue
            crm_list.append({
                "partner_id": partner.partner_id,
                "fullname": partner.fullname,
                "short_name": partner.short_name,
                "remenber_code": partner.remenber_code,
                "contacts_phone": partner.contacts_phone,
                "level_name": partner.level_name,
                "real_name": partner.real_name,
                "region": partner.region,
                "payment_description": partner.payment_description,
                # create_time 为秒级时间戳（partner_list 创建时间），转 YYYY-MM-DD 展示
                "create_time": _fmt_date_ts(partner.create_time),
                "order_count": partner.orderTimes,
                "bind_remark": relation.bind_remark,
                "bind_time": _fmt_datetime(relation.created_at),
            })

    return {"customer": customer, "amap": amap, "crm_list": crm_list}
