# -*- coding:utf-8 -*-
# @Time    : 2026/10/22
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : customer_stats_service.py
# 客户详情-指标卡聚合服务（M3，01-主设计文档 第六节）
# 接口层见 app/api/visit/visit_detail_api.py（GET /new/api/visit/customers/stats?id=<主键>）；
# DAO 层见 app/dao/visit_dao/visit_stats_dao.py（指标卡统计专用，与拿货订单/拜访时间轴 DAO 独立）；
# 指标卡（核心 8 项）与近30天动态（8 项）统一由本服务输出渲染契约（label/value/valueCls），
# 前端 tpl-metric-grid 直接渲染，数据源未接入的指标固定返回"暂时无数据"（红色占位）。
# 本期已接入指标（业务确认 2026-10-22）：
#   累计拜访次数 / 最近拜访时间 —— visit_record（status=1，amap_customer_id=POI编码）；
#   累计拿货额 —— sales_order_history 常规订单（order_type_id=1）订单级金额合计（1:N 绑定集合求和）；
#   累计退货金额 —— sales_order_history 退货订单（order_type_id=2）订单级金额合计（逐单取绝对值）；
#   线上订单占比 —— 线上金额 ÷ 常规订单总额，线上/线下按绑定 CRM 客户等级判定
#     （口径唯一来源 customer_order_service.is_online_level："开思"或"线上"开头 = 线上）；
#   退货率（退货金额卡 badge）—— 按件数统计：退货订单明细 ABS(quantity) 合计 ÷ 常规订单明细
#     quantity 合计（退货单退多少开多少，部分退货只记退掉的部分，明细级直接累加无重复累加问题）；
#   欠款余额 —— crm_sales_order 常规订单（order_type_name=1）SUM(no_receive_amount)，
#     数据源有固定更新渠道（每日 02:00 窗口 + 周六 02:00 近一年 + 看板心跳）；
#   近30天动态·退货金额 —— sales_order_history 退货订单（order_type_id=2）近30天
#     （订单级 create_date）订单级金额合计（逐单取绝对值），口径与累计退货金额一致；
#   近30天动态·最近成交时间 —— 常规订单（order_type_id=1）明细 MAX(create_date)，
#     不限 30 天窗口（业务口径：客户最近一次拿货时间）；
#   近30天动态·平台/线下成交次数 —— 一张常规订单 = 一次成交（订单级去重计数），
#     30 天窗口，按绑定 CRM 客户等级拆分：线上（平台）次数 / 线下次数；
#   拜访转化率已按业务要求删除（visit_record 无 converted 字段，转化由订单数据实时统计）。
# 未接入指标及原因：
#   累计利润 / 毛利额 —— sales_order_history 无成本字段；
#   累计拜访投入 —— visit_record 无费用字段（高德同步契约 2.1 未落地）；
#   平台询价类 —— 无询价数据源；近30天动态其余指标 —— 数据源/口径待业务确认。

from datetime import datetime, timedelta

from app.dao.visit_dao import (
    visit_amap_customer_dao,
    visit_customer_relation_dao,
    visit_stats_dao,
)
from app.models.orm_models.crm.partner_list import PartnerList
from app.services.visit_service.customer_order_service import is_online_level
from app.utils.orm.session import orm_session

# 数据源未接入指标的占位渲染（红色"暂时无数据"）
_NO_DATA = {"value": "暂时无数据", "valueCls": "v-red"}

# 近30天动态指标（本期数据源未接入，仅输出占位，01 文档第十一节 / 02 拓展文档 3.2）
_DYNAMIC_LABELS = [
    "平台询价次数", "平台询价转化率", "平台成交次数", "线下成交次数",
    "成交金额", "毛利额", "退货金额", "最近成交时间",
]


def _fmt_amount(v):
    """金额 → '¥ 1,234.56'（None 返回 '—'）"""
    if v is None:
        return "—"
    return "¥ {:,.2f}".format(float(v))


def _fmt_date(dt):
    """datetime → 'YYYY-MM-DD'（空返回 '—'）"""
    return dt.strftime("%Y-%m-%d") if dt else "—"


def _build_metrics(visit_count, last_visit_time, total_amount, refund_amount,
                   refund_qty, total_qty, online_amount, unpaid_amount):
    """核心指标卡 8 项渲染契约（拜访转化率已删除；退货率 badge 按件数口径）"""
    # 退货率 = 退货件数 ÷ 常规订单件数（业务确认按件数统计）；无常规订单时不展示
    refund_badge = None
    if total_qty > 0:
        refund_badge = {
            "text": "退货率：{:.2f}%".format(refund_qty / total_qty * 100),
            "cls": "v-metric-extra--red",
        }
    # 线上订单占比 = 线上金额 ÷ 常规订单总额（按绑定 CRM 客户等级判定，同拿货订单 Tab 口径）；
    # 副标题不放线上/线下金额——8 列窄卡同行放不下长文本会挤压 label（金额明细在拿货订单 Tab 汇总卡）
    if total_amount > 0:
        online_pct = round(online_amount / total_amount * 100)
        online_item = {"label": "线上订单占比", "value": "{}%".format(online_pct), "valueCls": "v-blue"}
    else:
        online_item = {"label": "线上订单占比", "value": "—", "valueCls": "v-red"}
    # 欠款余额 = 常规订单未结算金额（crm_sales_order.no_receive_amount 合计）：
    # 正数红色（存在欠款），0/负数绿色（已结清/多结冲抵）；副标题标注口径
    if unpaid_amount > 0:
        unpaid_item = {
            "label": "欠款余额", "value": _fmt_amount(unpaid_amount), "valueCls": "v-red",
            "sub": "常规订单未结算", "subCls": "v-metric-sub--gray",
        }
    else:
        unpaid_item = {"label": "欠款余额", "value": _fmt_amount(unpaid_amount), "valueCls": "v-green"}
    return [
        {"label": "累计拜访次数", "value": "{} 次".format(visit_count)},
        {"label": "最近拜访时间", "value": _fmt_date(last_visit_time)},
        {"label": "累计拿货额", "value": _fmt_amount(total_amount), "valueCls": "v-green"},
        {"label": "累计退货金额", "value": _fmt_amount(refund_amount), "valueCls": "v-red", "badge": refund_badge},
        dict({"label": "累计利润"}, **_NO_DATA),
        online_item,
        dict({"label": "累计拜访投入"}, **_NO_DATA),
        unpaid_item,
    ]


def _build_dynamics(refund_amount_30d, sales_amount_30d, last_order_ts, online_count, offline_count):
    """近30天动态 8 项渲染（退货金额/成交金额/最近成交时间/平台·线下成交次数已接入，其余数据源接入后在此补充）"""
    items = []
    for label in _DYNAMIC_LABELS:
        if label == "退货金额":
            # 近30天退货订单金额合计（口径同累计退货金额 + 30天窗口）；0 表示近30天无退货
            items.append({"label": label, "value": _fmt_amount(refund_amount_30d), "valueCls": "v-red"})
        elif label == "成交金额":
            # 近30天累计拿货额（常规订单订单级金额 + 30天窗口，业务口径 2026-10-23）
            items.append({"label": label, "value": _fmt_amount(sales_amount_30d), "valueCls": "v-green"})
        elif label == "最近成交时间":
            # 常规订单最近下单时间（不限窗口），秒级时间戳 → 日期
            dt = datetime.fromtimestamp(last_order_ts) if last_order_ts else None
            items.append({"label": label, "value": _fmt_date(dt)})
        elif label == "平台成交次数":
            # 近30天线上常规订单数（订单级去重计数，按绑定 CRM 客户等级判定）
            items.append({"label": label, "value": "{} 次".format(online_count)})
        elif label == "线下成交次数":
            # 近30天线下常规订单数
            items.append({"label": label, "value": "{} 次".format(offline_count)})
        else:
            items.append(dict({"label": label}, **_NO_DATA))
    return items


def get_customer_stats(customer_id):
    """
    客户详情指标卡聚合（进入详情页时前端请求一次，切 Tab 不重复请求）

    - customer_id 为 visit_amap_customer 物理主键（与详情头部一致）
    - 拜访维度按 POI 编码统计 visit_record；订单维度经 visit_customer_relation（1:N）
      取全部 partner_id 后按客户集合聚合，未关联 CRM 时订单指标为 0
    - 金额口径与拿货订单 Tab 一致：明细级 → 订单级聚合（见 visit_order_dao）；
      退货率按件数口径：退货明细 ABS(quantity) 合计 ÷ 常规订单明细 quantity 合计

    :param customer_id: visit_amap_customer 物理主键 id
    :return: {'metrics': [...8项...], 'dynamics': [...8项...]}
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

        # 拜访维度：按 POI 编码统计（status=1 排除作废），单次扫描同时取次数与最近拜访时间
        visit_count, last_visit_time = visit_stats_dao.fetch_visit_stats(session, row.amap_poi_id)

        # 订单维度：1:N 绑定 → 全部 partner_id 集合聚合；未关联 CRM 时订单指标为 0
        relations = visit_customer_relation_dao.list_by_amap_customer_id(session, row.amap_poi_id)
        partner_ids = [r.partner_id for r in relations]
        total_amount = 0.0
        online_amount = 0.0
        refund_amount = 0.0
        refund_qty = 0
        total_qty = 0
        unpaid_amount = 0.0
        refund_amount_30d = 0.0
        sales_amount_30d = 0.0
        last_order_ts = 0
        online_count = 0
        offline_count = 0
        if partner_ids:
            # 近30天动态窗口起始（成交金额/退货金额/成交次数共用）
            since_30d = int((datetime.now() - timedelta(days=30)).timestamp())
            # 绑定 CRM 客户等级（线上/线下判定，口径同拿货订单 Tab）
            level_map = {
                p.partner_id: (p.level_name or "")
                for p in session.query(PartnerList.partner_id, PartnerList.level_name).filter(
                    PartnerList.partner_id.in_(partner_ids)).all()
            }
            # 拿货额 + 线上/线下拆分 + 近30天成交金额：按客户分组返回，单次扫描三用
            for r in visit_stats_dao.fetch_sales_amount_grouped(session, partner_ids, since_30d):
                total_amount += r["total_amount"]
                sales_amount_30d += r["amount_30d"]
                if is_online_level(level_map.get(r["customer_id"], "")):
                    online_amount += r["total_amount"]
            refund_amount = visit_stats_dao.fetch_refund_amount(session, partner_ids)
            # 退货率按件数口径：退货件数 ÷ 常规订单件数（条件聚合单次扫描）
            refund_qty, total_qty = visit_stats_dao.fetch_refund_qty_stats(session, partner_ids)
            # 欠款余额：crm_sales_order 常规订单未结算金额合计（独立数据源，有固定更新渠道）
            unpaid_amount = visit_stats_dao.fetch_unpaid_amount(session, partner_ids)
            # 近30天动态·退货金额：退货订单订单级金额合计（30天窗口，口径同累计退货金额）
            refund_amount_30d = visit_stats_dao.fetch_refund_amount(session, partner_ids, since_ts=since_30d)
            # 近30天动态·最近成交时间：常规订单最后下单时间（不限窗口）
            last_order_ts = visit_stats_dao.fetch_last_order_time(session, partner_ids)
            # 近30天动态·平台/线下成交次数：订单级去重计数，按客户等级拆线上/线下
            for r in visit_stats_dao.fetch_order_count_grouped(session, partner_ids, since_30d):
                if is_online_level(level_map.get(r["customer_id"], "")):
                    online_count += r["order_count"]
                else:
                    offline_count += r["order_count"]

    # 会话外仅操作已序列化的标量值，避免 DetachedInstanceError
    return {
        "metrics": _build_metrics(visit_count, last_visit_time, total_amount, refund_amount,
                                  refund_qty, total_qty, online_amount, unpaid_amount),
        "dynamics": _build_dynamics(refund_amount_30d, sales_amount_30d, last_order_ts, online_count, offline_count),
    }
