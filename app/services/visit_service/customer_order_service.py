# -*- coding:utf-8 -*-
# @Time    : 2026/10/21
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : customer_order_service.py
# @Software: PyCharm
# 客户详情-拿货订单聚合服务（M5，01-主设计文档 第六节 / 第五节指标口径）
# 接口层见 app/api/visit/visit_detail_api.py（GET /new/api/visit/customers/orders?id=<主键>）；
# DAO 层见 visit_order_dao.py（明细级→订单级聚合基表，金额禁止直接对明细求和）。
# 关联拜访（visit_order_ref）本期未落地，列表"关联拜访"列数据留空显示"无"；
# 汇总卡共 4 张（当前欠款卡已按业务要求删除，欠款数据源 account_receivable_list 表 bbr_test 未建）。
# 线上/线下口径（业务确认 2026-10-21）：不看订单字段，看绑定 CRM 客户等级
# partner_list.level_name —— "开思"或"线上"开头 = 线上，其余等级 = 线下；
# 1:N 绑定下按客户集合求和拆分（DAO 按 customer_id 分组返回，本服务结合等级汇总）。
# 原厂件占比口径（业务确认 2026-10-22）：按件数统计——常规订单中品牌名含"原厂"的明细
# quantity 合计 ÷ 常规订单全部明细 quantity 合计（一条明细的 quantity 即件数）。

from datetime import datetime

from app.dao.visit_dao import visit_amap_customer_dao, visit_customer_relation_dao, visit_order_dao
from app.models.orm_models.crm.partner_list import PartnerList
from app.services.visit_service import order_visit_ref_service
from app.utils.orm.session import orm_session

# 订单类型标签样式（order_type_name 实测值域仅：常规订单/退货订单）
_ORDER_TYPE_CLS = {
    "常规订单": "v-tag--gray",
    "退货订单": "v-tag--orange",
}
# 订单渠道标签样式（按绑定 CRM 客户等级拆分，见 _is_online_level；列表展示格式"线上/线下-客户等级"）
_ORDER_CHANNEL_CLS = {
    "线上": "v-tag--blue",
    "线下": "v-tag--gray",
}
# 订单状态文字样式（status 为库内中文原文：已审核/已拣货/已收货/已确认/已调单）
_GREEN_STATUS = {"已审核", "已拣货", "已收货", "已确认"}


def _fmt_datetime(ts):
    """秒级时间戳 → YYYY-MM-DD HH:MM（空/非法返回 None）"""
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return None


def _fmt_amount(v):
    """金额 → '¥ 1,234.56'（None 返回 '—'）"""
    if v is None:
        return "—"
    return "¥ {:,.2f}".format(float(v))


def is_online_level(level_name):
    """客户等级 → 是否线上：'开思' 或 '线上'开头（如 线上-途虎养车）= 线上，其余 = 线下

    线上/线下判定口径的唯一来源（业务确认 2026-10-21），拿货订单 Tab 与
    详情页指标卡（customer_stats_service）共用本函数，禁止各自重复实现。
    """
    return bool(level_name) and (level_name == "开思" or level_name.startswith("线上"))


def _build_summary_cards(summary):
    """
    汇总卡渲染数据（tpl-order-summary 契约：label/value/valueCls/panelCls/sub/subCls，共 4 张）

    销售额口径 = 常规订单（order_type_id=1，排除退货订单）；
    累计卡副标题 = 线上/线下销售额占比（按绑定 CRM 客户等级拆分，1:N 集合求和）；
    原厂件占比 = 常规订单中品牌名含"原厂"的明细件数 ÷ 常规订单总件数（fetch_oem_qty_stats）。
    """
    total = summary["total_amount"]
    if total > 0:
        online_pct = round(summary["online_amount"] / total * 100)
        sub = "线上 {}% · 线下 {}%".format(online_pct, 100 - online_pct)
        oem_value = "{}%".format(round(summary["oem_qty"] / summary["total_qty"] * 100)) if summary["total_qty"] > 0 else "—"
        oem_sub = "原厂件 {} / 共 {} 件".format(summary["oem_qty"], summary["total_qty"])
    else:
        sub = "暂无订单数据"
        oem_value = "—"
        oem_sub = "暂无订单数据"
    return [
        {
            "label": "累计销售额", "value": _fmt_amount(total),
            "valueCls": "v-green", "panelCls": "v-metric--green",
            "sub": sub, "subCls": "v-metric-sub--gray",
        },
        {
            "label": "本年销售额", "value": _fmt_amount(summary["year_amount"]),
            "valueCls": "v-green", "panelCls": "v-metric--green",
        },
        {
            "label": "本月销售额", "value": _fmt_amount(summary["month_amount"]),
            "valueCls": "v-blue", "panelCls": "v-metric--blue",
        },
        {
            "label": "原厂件占比", "value": oem_value,
            "valueCls": "v-green", "panelCls": "v-metric--green",
            "sub": oem_sub, "subCls": "v-metric-sub--gray",
        },
    ]


def get_customer_orders(customer_id, page=1, limit=10):
    """
    拿货订单 Tab 聚合（汇总卡 + 订单分页列表，切到该 Tab 时前端才请求）

    - customer_id 为 visit_amap_customer 物理主键（与详情头部一致，URL 不透传 POI 编码）
    - 1:N 绑定：经 visit_customer_relation 取全部 partner_id 后按客户集合取数；
      未关联 CRM 时返回空数据（前端按空态展示）
    - 订单级聚合口径见 visit_order_dao._order_level_subquery

    :param customer_id: visit_amap_customer 物理主键 id
    :param page: 页码（1 起）
    :param limit: 每页条数（1-100）
    :return: {'summary': [...], 'list': [...], 'total': n, 'page': p, 'limit': l}
    """
    try:
        customer_id = int(str(customer_id).strip())
    except (TypeError, ValueError):
        raise ValueError("客户标识不合法")
    if customer_id <= 0:
        raise ValueError("缺少客户标识")
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        limit = min(max(1, int(limit)), 100)
    except (TypeError, ValueError):
        limit = 10

    now = datetime.now()
    year_start_ts = int(datetime(now.year, 1, 1).timestamp())
    month_start_ts = int(datetime(now.year, now.month, 1).timestamp())

    with orm_session() as session:
        row = visit_amap_customer_dao.get_by_id(session, customer_id)
        if not row:
            raise ValueError("客户不存在或已被删除")
        # 会话内取值，避免会话外访问 ORM 实例触发 DetachedInstanceError
        amap_customer_id = row.amap_poi_id

        # 1:N 绑定 → 全部 partner_id；未关联 CRM 时直接返回空数据，不查订单
        relations = visit_customer_relation_dao.list_by_amap_customer_id(session, row.amap_poi_id)
        partner_ids = [r.partner_id for r in relations]
        if not partner_ids:
            return {
                "summary": _build_summary_cards({
                    "total_amount": 0, "year_amount": 0, "month_amount": 0,
                    "normal_count": 0, "online_amount": 0,
                    "oem_qty": 0, "total_qty": 0,
                }),
                "list": [], "total": 0, "page": page, "limit": limit,
                "amapCustomerId": amap_customer_id,
            }

        # 绑定 CRM 客户信息：等级 = 线上/线下拆分口径；名称 = 列表"CRM客户"列；
        # 同时供绑定失效校验（partner_list 中已删除的客户查不到，列表侧显示"—"）
        partner_map = {
            p.partner_id: {"level_name": p.level_name or "", "fullname": p.fullname or ""}
            for p in session.query(PartnerList.partner_id, PartnerList.level_name, PartnerList.fullname).filter(
                PartnerList.partner_id.in_(partner_ids)).all()
        }

        # DAO 按 customer_id 分组返回，本服务结合客户等级求和拆分线上/线下；
        # 原厂件占比按件数统计（fetch_oem_qty_stats 返回 原厂件数/总件数）
        summary_rows = visit_order_dao.fetch_order_summary(session, partner_ids, year_start_ts, month_start_ts)
        oem_qty, total_qty = visit_order_dao.fetch_oem_qty_stats(session, partner_ids)
        summary = {
            "total_amount": 0, "year_amount": 0, "month_amount": 0,
            "normal_count": 0, "online_amount": 0,
            "oem_qty": oem_qty, "total_qty": total_qty,
        }
        for r in summary_rows:
            summary["total_amount"] += r["total_amount"]
            summary["year_amount"] += r["year_amount"]
            summary["month_amount"] += r["month_amount"]
            summary["normal_count"] += r["normal_count"]
            if is_online_level((partner_map.get(r["customer_id"]) or {}).get("level_name", "")):
                summary["online_amount"] += r["total_amount"]
        total, rows = visit_order_dao.fetch_order_page(session, partner_ids, page, limit)

        # "关联拜访"列装配（M5，05 文档）：按当前页发货金蝶号批量取关联行
        # （业务确认 2026-10-24：常规/退货订单均可关联，仅要求发货金蝶号非空）
        orders_ids = [r["deliverysapno"] for r in rows if r["deliverysapno"]]
        visit_ref_map = order_visit_ref_service.build_visit_ref_map(session, orders_ids)

    # 会话外仅操作已序列化的 dict，避免 DetachedInstanceError
    # 订单渠道 = "线上/线下-客户等级"（如 线上-开思、线下-维修厂），按订单所属 CRM 客户等级判定；
    # 订单类型 = order_type_name（常规/退货）；crmName = 订单所属 CRM 客户名称（1:N 绑定区分用）
    list_items = []
    for r in rows:
        p_info = partner_map.get(r["customer_id"]) or {}
        lvl = p_info.get("level_name", "")
        online = is_online_level(lvl)
        list_items.append({
            # "订单号"列展示发货金蝶号（deliverysapno），空值回退 ddno
            "ddno": r["deliverysapno"] or r["ddno"] or "—",
            "time": _fmt_datetime(r["create_date"]) or "—",
            "crmName": p_info.get("fullname") or "—",
            "orderChannel": ("线上" if online else "线下") + "-" + (lvl or "未分级"),
            "orderChannelCls": _ORDER_CHANNEL_CLS["线上"] if online else _ORDER_CHANNEL_CLS["线下"],
            "orderType": r["order_type_name"] or "未知类型",
            "orderTypeCls": _ORDER_TYPE_CLS.get(r["order_type_name"], "v-tag--gray"),
            "items": r["items_text"] or "—",
            "amount": _fmt_amount(r["order_amount"]),
            "status": r["status"] or "—",
            "statusCls": "v-green" if r["status"] in _GREEN_STATUS else "",
            # 发货金蝶号原文（关联/取消关联接口按号寻址，05 文档第三节）
            "ordersId": r["deliverysapno"] or "",
            # 关联拜访（05 文档）：{recordId, visitTime, recorder} 或 None（无关联/拜访已作废均 None）；
            # 常规/退货订单均可关联（业务确认 2026-10-24）
            "visitRef": visit_ref_map.get(r["deliverysapno"]),
        })

    return {
        "summary": _build_summary_cards(summary),
        "list": list_items,
        "total": total,
        "page": page,
        "limit": limit,
        "amapCustomerId": amap_customer_id,
    }
