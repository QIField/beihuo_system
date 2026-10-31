# -*- coding:utf-8 -*-
# @Time    : 2026/10/29 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_expense_service.py
# @Software: PyCharm
"""
费用业务逻辑层（visit_expense）

职责：
1. 单条/批量新增：入参校验 + 关联记录/订单存在性校验 + 客户归属冗余字段填充
2. 编辑：仅允许金额/类型/说明
3. 作废/恢复
4. 分页查询
5. 关联记录查费用（拜访时间轴卡片内嵌展示）
6. 订单搜索（费用关联订单选择器用）
7. 汇总聚合（总利益公式 / 月度趋势 / 客户排名 / 类型占比）
"""
from datetime import datetime, date, timedelta

from app.dao.visit_dao import visit_expense_dao
from app.services.visit_service import visit_record_service  # 解析 source_type=1 的客户归属
from app.utils.orm.session import orm_session


# 关联来源类型枚举（visit_expense.source_type）
SOURCE_TYPE_VISIT = 1    # 拜访记录 visit_record.id
SOURCE_TYPE_FOLLOW = 2   # 跟进记录 visit_follow_record.id
SOURCE_TYPE_ORDER = 3    # 订单 sales_order_history.orders_id（如退货索赔）
SOURCE_TYPE_MANUAL = 4   # 手动输入（无关联记录，source_id 为空）

# 费用类型枚举（visit_expense.expense_type）
# 数据库仍为 VARCHAR(50) 字符串存储，不做表结构变更；
# 应用层强约束：新增/编辑只允许以下取值，其余一律拒绝
EXPENSE_TYPE_VISIT = "拜访投入"        # 上门拜访产生的差旅、时间投入等
EXPENSE_TYPE_GIFT = "礼品物料投入"     # 送样、礼品、宣传物料等
EXPENSE_TYPE_RECEPTION = "接待投入"    # 商务宴请、招待等
EXPENSE_TYPE_SERVICE = "服务投入"      # 售后服务、技术支持等
EXPENSE_TYPE_CLAIM = "索赔"            # 退货/质量索赔等
EXPENSE_TYPE_OTHER = "其他"            # 以上分类之外的杂项
EXPENSE_TYPES = (
    EXPENSE_TYPE_VISIT, EXPENSE_TYPE_GIFT, EXPENSE_TYPE_RECEPTION,
    EXPENSE_TYPE_SERVICE, EXPENSE_TYPE_CLAIM, EXPENSE_TYPE_OTHER,
)


def validate_expense_type(value):
    """
    校验费用类型是否在枚举内（service 内部与 API 层共用）

    :param value: 原始费用类型值
    :return: 校验通过的类型字符串（strip 后）
    :raises ValueError: 类型为空或不在枚举内
    """
    t = str(value or "").strip()
    if not t:
        raise ValueError("费用类型不能为空")
    if t not in EXPENSE_TYPES:
        raise ValueError("费用类型只能是: " + " / ".join(EXPENSE_TYPES))
    return t


# 编辑允许修改的字段（客户归属、关联记录、录入人不可改）
EDITABLE_FIELDS = ("expense_type", "amount", "description")


def _validate_expense_data(data, bulk=False):
    """校验费用数据（dict 单条或 list 批量的单条）"""
    # 必填字段
    for f in ("expense_type", "amount", "source_type"):
        if f not in data or data[f] is None:
            raise ValueError(f"缺少必填字段: {f}")

    # 费用类型：必须在枚举内（拜访投入/礼品物料投入/接待投入/服务投入/索赔/其他）
    data["expense_type"] = validate_expense_type(data.get("expense_type"))

    # 金额 > 0
    try:
        amount = float(data["amount"])
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("金额必须是正数")

    # 关联来源类型：必须是 1/2/3/4
    try:
        data["source_type"] = int(data["source_type"])
    except (TypeError, ValueError):
        raise ValueError("source_type 必须是整数(1-拜访 2-跟进 3-订单 4-手动输入)")
    if data["source_type"] not in (
            SOURCE_TYPE_VISIT, SOURCE_TYPE_FOLLOW, SOURCE_TYPE_ORDER, SOURCE_TYPE_MANUAL):
        raise ValueError("source_type 只能是 1(拜访) 2(跟进) 3(订单) 4(手动输入)")

    # source_id 约束：1/2/3 必填；4（手动输入）强制置空
    if data["source_type"] == SOURCE_TYPE_MANUAL:
        data["source_id"] = None
    elif data.get("source_id") is None:
        raise ValueError("source_type=1/2/3 时 source_id 必填")

    # 费用日期：没传默认今天
    if not data.get("expense_date"):
        data["expense_date"] = date.today().strftime("%Y-%m-%d")

    # 日期格式校验
    try:
        if isinstance(data["expense_date"], str):
            data["expense_date"] = datetime.strptime(data["expense_date"], "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("expense_date 格式应为 YYYY-MM-DD")


def _fill_customer_info(session, data):
    """
    关联记录存在性校验 + 客户归属冗余字段 amap_customer_id 填充（调用前须先 _validate_expense_data）：
    - source_type=1/2：校验拜访/跟进记录存在；客户未传时从记录反查
    - source_type=3：校验订单（sales_order_history.orders_id）存在；客户必须显式传入
    - source_type=4：无关联记录；客户必须显式传入
    最终 amap_customer_id 必填，否则抛 ValueError
    """
    source_type = data["source_type"]
    source_id = data.get("source_id")

    if source_type == SOURCE_TYPE_VISIT:
        # 关联 visit_record：存在性校验 + 反查客户归属
        from app.models.orm_models.visit.visit_record import VisitRecord
        rec = session.query(VisitRecord).filter(VisitRecord.id == source_id).first()
        if rec is None:
            raise ValueError(f"关联的拜访记录不存在: id={source_id}")
        if not (data.get("amap_customer_id") or "").strip():
            data["amap_customer_id"] = rec.amap_customer_id
    elif source_type == SOURCE_TYPE_FOLLOW:
        # 关联 visit_follow_record：存在性校验 + 反查客户归属
        from app.models.orm_models.visit.visit_follow_record import VisitFollowRecord
        rec = session.query(VisitFollowRecord).filter(VisitFollowRecord.id == source_id).first()
        if rec is None:
            raise ValueError(f"关联的跟进记录不存在: id={source_id}")
        if not (data.get("amap_customer_id") or "").strip():
            data["amap_customer_id"] = rec.amap_customer_id
    elif source_type == SOURCE_TYPE_ORDER:
        # 关联订单：存在性校验按 sales_order_history（订单选择器数据源，全量历史订单）；
        # crm_sales_order 仅同步近期订单，老订单不在其中，按它校验会误拒（客户由前端显式选择）
        from app.models.orm_models.crm.sales_order_history import SalesOrderHistory
        order_exists = session.query(SalesOrderHistory.orders_id) \
            .filter(SalesOrderHistory.orders_id == source_id).first() is not None
        if not order_exists:
            raise ValueError(f"关联的订单不存在: orders_id={source_id}")

    # 客户归属必填（1/2 反查兜底后仍为空则报错）
    if not (data.get("amap_customer_id") or "").strip():
        raise ValueError("客户(amap_customer_id)必填")
    data["amap_customer_id"] = data["amap_customer_id"].strip()


# ==================== 单条/批量新增 ====================

def create_expense(data, recorder_id):
    """
    新增单条费用

    :param data: 请求体 dict
    :param recorder_id: 当前登录用户 ID
    :return: 新增记录的 dict
    """
    visit_expense_dao.ensure_table()
    _validate_expense_data(data)

    with orm_session() as session:
        _fill_customer_info(session, data)

        row = visit_expense_dao.create_expense(session, {
            "source_type": data["source_type"],
            "source_id": data.get("source_id"),
            "amap_customer_id": data["amap_customer_id"],
            "expense_date": data["expense_date"],
            "expense_type": data["expense_type"].strip(),
            "amount": float(data["amount"]),
            "description": (data.get("description") or "").strip() or None,
            "recorder_id": recorder_id,
            "status": 1,
        })
        return row.to_dict()


def batch_create_expenses(items, recorder_id):
    """
    批量新增费用（一个事务）

    :param items: 数据字典列表
    :param recorder_id: 当前登录用户 ID
    :return: {'count': N}
    """
    visit_expense_dao.ensure_table()
    if not items:
        raise ValueError("items 不能为空")

    # 逐条校验，有问题一起返回
    for i, item in enumerate(items):
        try:
            _validate_expense_data(item)
        except ValueError as e:
            raise ValueError(f"第 {i + 1} 条: {e}")

    with orm_session() as session:
        prepared = []
        for item in items:
            _fill_customer_info(session, item)
            prepared.append({
                "source_type": item["source_type"],
                "source_id": item.get("source_id"),
                "amap_customer_id": item["amap_customer_id"],
                "expense_date": item["expense_date"],
                "expense_type": item["expense_type"].strip(),
                "amount": float(item["amount"]),
                "description": (item.get("description") or "").strip() or None,
                "recorder_id": recorder_id,
                "status": 1,
            })
        count = visit_expense_dao.bulk_create_expenses(session, prepared)

    return {"count": count}


# ==================== 订单搜索（费用关联订单选择器用） ====================

def search_orders(keyword, limit=20, amap_customer_id=None):
    """
    按订单号搜索订单（口径与拿货订单 Tab 一致：sales_order_history 明细 → 订单级聚合）

    匹配字段：发货金蝶号(deliverysapno) / 订单号(ddno) / 订单金蝶号(ddsapno)；
    传入 amap_customer_id（客户详情场景）时进一步限定：仅返回该客访客户当前绑定的
    CRM 客户（visit_customer_relation → partner_id）名下的订单，防止搜到无关客户订单。

    注意：数据源为 sales_order_history（全量历史订单，15w+ 单），不 JOIN crm_sales_order
    （其仅同步近期 3w+ 单，老订单不在其中，JOIN 会漏单）。费用保存时 source_id 的
    存在性校验同样按 sales_order_history 校验（见 _fill_customer_info），口径闭环。

    :param keyword: 搜索关键词（订单号）
    :param limit: 返回条数上限（1~50，默认 20）
    :param amap_customer_id: 高德客户POI编码（visit_amap_customer.amap_poi_id，选填；
                             传入后按绑定 CRM 客户过滤订单范围）
    :return: [{'orders_id': int, 'deliverysapno': str, 'ddno': str, 'fullname': str}, ...]
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    try:
        limit = min(max(1, int(limit)), 50)
    except (TypeError, ValueError):
        limit = 20

    from sqlalchemy import func, or_

    from app.dao.visit_dao import visit_customer_relation_dao
    from app.models.orm_models.crm.sales_order_history import SalesOrderHistory

    like = f"%{keyword}%"
    with orm_session() as session:
        filters = [or_(SalesOrderHistory.deliverysapno.like(like),
                       SalesOrderHistory.ddno.like(like),
                       SalesOrderHistory.ddsapno.like(like))]

        # 客户详情场景：限定为该客访客户绑定 CRM 客户（1:N）名下的订单；
        # 未绑定任何 CRM 客户时无可搜订单，直接返回空
        amap_customer_id = (amap_customer_id or "").strip()
        if amap_customer_id:
            relations = visit_customer_relation_dao.list_by_amap_customer_id(session, amap_customer_id)
            partner_ids = [r.partner_id for r in relations if r.partner_id is not None]
            if not partner_ids:
                return []
            filters.append(SalesOrderHistory.customer_id.in_(partner_ids))

        # 明细级 → 订单级聚合（口径同 visit_order_dao._order_level_subquery）
        rows = (session.query(
                   SalesOrderHistory.orders_id.label("orders_id"),
                   func.max(SalesOrderHistory.deliverysapno).label("deliverysapno"),
                   func.max(SalesOrderHistory.ddno).label("ddno"),
                   func.max(SalesOrderHistory.fullname).label("fullname"),
                ).filter(*filters)
                .group_by(SalesOrderHistory.orders_id)
                .order_by(SalesOrderHistory.orders_id.desc())
                .limit(limit).all())

    return [
        {
            "orders_id": r.orders_id,
            "deliverysapno": r.deliverysapno,
            "ddno": r.ddno,
            "fullname": r.fullname,
        }
        for r in rows
    ]


# ==================== 编辑/作废/恢复 ====================

def update_expense(expense_id, data):
    """
    编辑费用（仅允许日期/金额/类型/说明）

    :param expense_id: 费用记录 ID
    :param data: 待更新 dict（允许包含任意字段，内部过滤）
    :return: 更新后的 dict 或 None
    """
    visit_expense_dao.ensure_table()
    update_fields = {}

    if "expense_date" in data and data["expense_date"]:
        # 日期格式校验并转为 date 对象
        try:
            if isinstance(data["expense_date"], str):
                update_fields["expense_date"] = datetime.strptime(
                    data["expense_date"], "%Y-%m-%d").date()
            else:
                update_fields["expense_date"] = data["expense_date"]
        except ValueError:
            raise ValueError("expense_date 格式应为 YYYY-MM-DD")

    if "amount" in data and data["amount"] is not None:
        try:
            amount = float(data["amount"])
            if amount <= 0:
                raise ValueError
            update_fields["amount"] = amount
        except ValueError:
            raise ValueError("金额必须是正数")

    if "expense_type" in data and data["expense_type"] is not None:
        # 费用类型：必须在枚举内（拜访投入/礼品物料投入/接待投入/服务投入/索赔/其他）
        update_fields["expense_type"] = validate_expense_type(data["expense_type"])

    if "description" in data:
        update_fields["description"] = (data.get("description") or "").strip() or None

    if not update_fields:
        raise ValueError("没有可更新的字段")

    with orm_session() as session:
        row = visit_expense_dao.update_expense(session, expense_id, update_fields)
        if row is None:
            raise ValueError(f"费用记录不存在: id={expense_id}")
        return row.to_dict()


def void_expense(expense_id):
    """作废费用"""
    visit_expense_dao.ensure_table()
    with orm_session() as session:
        row = visit_expense_dao.set_expense_status(session, expense_id, status=0)
        if row is None:
            raise ValueError(f"费用记录不存在: id={expense_id}")
        return row.to_dict()


def restore_expense(expense_id):
    """恢复已作废费用"""
    visit_expense_dao.ensure_table()
    with orm_session() as session:
        row = visit_expense_dao.set_expense_status(session, expense_id, status=1)
        if row is None:
            raise ValueError(f"费用记录不存在: id={expense_id}")
        return row.to_dict()


# ==================== 查询 ====================

def get_expense_detail(expense_id):
    """按 ID 查询单条"""
    visit_expense_dao.ensure_table()
    with orm_session() as session:
        row = visit_expense_dao.get_expense_by_id(session, expense_id)
        if not row:
            raise ValueError(f"费用记录不存在: id={expense_id}")
        return row.to_dict()


def get_expense_list(page=1, limit=20, amap_customer_id=None,
                     recorder_id=None, status=None,
                     date_start=None, date_end=None, keyword=None):
    """
    费用明细分页查询

    :param keyword: 高德客户名称关键词（按名称模糊匹配客户，再按其 POI 过滤费用）
    :return: {'list': [...], 'total': N, 'page': p, 'limit': l}
    """
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        limit = min(max(1, int(limit)), 200)
    except (TypeError, ValueError):
        limit = 20

    # 空白视为未筛选
    visit_expense_dao.ensure_table()
    amap_customer_id = (amap_customer_id or "").strip() or None
    keyword = (keyword or "").strip() or None

    with orm_session() as session:
        # 客户名称搜索：先按名称模糊查出 POI 码列表，再用其过滤费用
        amap_customer_ids = None
        if keyword:
            from app.models.orm_models.visit.visit_amap_customer import VisitAmapCustomer
            poi_rows = (session.query(VisitAmapCustomer.amap_poi_id)
                        .filter(VisitAmapCustomer.customer_name.like(f"%{keyword}%"))
                        .all())
            amap_customer_ids = [p.amap_poi_id for p in poi_rows if p.amap_poi_id]
            if not amap_customer_ids:
                # 无匹配客户，直接返回空列表
                return {"list": [], "total": 0, "page": page, "limit": limit}

        total, rows = visit_expense_dao.page_expenses(
            session, page=page, limit=limit,
            amap_customer_id=amap_customer_id,
            amap_customer_ids=amap_customer_ids,
            recorder_id=recorder_id,
            status=status,
            date_start=date_start,
            date_end=date_end,
        )
        items = [r.to_dict() for r in rows]

        # 批量填充高德客户名称（前端优先展示名称，POI 码仅兜底）
        from app.dao.visit_dao import visit_amap_customer_dao
        poi_ids = list({it.get("amap_customer_id") for it in items if it.get("amap_customer_id")})
        if poi_ids:
            name_map = visit_amap_customer_dao.get_customer_name_map(session, poi_ids)
            for it in items:
                it["customer_name"] = name_map.get(it.get("amap_customer_id"))

    return {
        "list": items,
        "total": total,
        "page": page,
        "limit": limit,
    }


def get_expenses_by_source(source_type, source_id):
    """
    按关联记录查询费用列表（拜访时间轴卡片内嵌展示）

    :return: 费用 dict 列表 + 合计金额
    """
    visit_expense_dao.ensure_table()
    with orm_session() as session:
        rows = visit_expense_dao.get_by_source(session, source_type, source_id)
        items = [r.to_dict() for r in rows]
        total_amount = sum(r.amount or 0 for r in rows)

    return {
        "items": items,
        "total_amount": float(total_amount),
        "count": len(items),
    }


# ==================== 聚合（分析页用） ====================

def get_summary(amap_customer_id=None, month=None, year=None, all_time=False):
    """
    费用汇总（费用分析页汇总卡 + 总利益公式）

    :param amap_customer_id: 按客户筛选（选填）
    :param month: 月份 'YYYY-MM'（选填，不传则取本年）
    :param year: 年份 'YYYY'（选填，不传取当前）
    :param all_time: True 时不限时间窗口，统计全部历史费用（客户累计投入场景）
    :return: {
        'metrics': {
            'visit_expense':      费用合计,
            'expense_count':      费用笔数,
            'customer_count':     涉及客户数,
        },
        'type_breakdown': [...] 费用类型占比,
        'trend': [...] 近 12 月趋势,
    }

    注意：总利益公式的"拿货额/退货金/成本"由调用方（前端或其他 service）
    传入或另查，此处只负责费用侧聚合。
    """
    visit_expense_dao.ensure_table()
    today = date.today()
    if all_time:
        # 不限时间窗口：统计全部历史费用（date_start/date_end=None 时 DAO 不加时间条件）
        date_start = None
        date_end = None
    elif month:
        # 按月份
        try:
            dt = datetime.strptime(month, "%Y-%m")
        except ValueError:
            raise ValueError("month 格式应为 YYYY-MM")
        date_start = dt.replace(day=1)
        # 下月第一天减一
        if dt.month == 12:
            date_end = dt.replace(year=dt.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            date_end = dt.replace(month=dt.month + 1, day=1) - timedelta(days=1)
    elif year:
        date_start = date(int(year), 1, 1)
        date_end = date(int(year), 12, 31)
    else:
        # 默认：本年
        date_start = date(today.year, 1, 1)
        date_end = today

    with orm_session() as session:
        # 费用合计
        total_amount = visit_expense_dao.get_expense_sum(
            session, amap_customer_id=amap_customer_id,
            date_start=date_start, date_end=date_end)

        # 笔数（复用 get_type_breakdown 的 count 汇总）
        type_breakdown = visit_expense_dao.get_type_breakdown(
            session, amap_customer_id=amap_customer_id,
            date_start=date_start, date_end=date_end)
        expense_count = sum(t["count"] for t in type_breakdown)

        # 涉及客户数（当前筛选窗口内有费用的去重客户数）
        customer_count = _count_distinct_customers(
            session, amap_customer_id=amap_customer_id,
            date_start=date_start, date_end=date_end)

        # 月度趋势（近 12 月）
        trend = visit_expense_dao.get_monthly_trend(
            session, months=12, amap_customer_id=amap_customer_id)

    return {
        # all_time 模式不限窗口，两端返回 None
        "window_start": date_start.strftime("%Y-%m-%d") if date_start else None,
        "window_end": date_end.strftime("%Y-%m-%d") if date_end else None,
        "metrics": {
            "visit_expense": float(total_amount),
            "expense_count": expense_count,
            "customer_count": customer_count,
        },
        "type_breakdown": type_breakdown,
        "trend": trend,
    }


def get_ranking(date_start=None, date_end=None, top_n=20):
    """
    客户费用排名

    :return: [{'amap_customer_id': str, 'customer_name': str,
               'amount': float, 'count': int}, ...]
    """
    visit_expense_dao.ensure_table()
    try:
        top_n = int(top_n)
    except (TypeError, ValueError):
        top_n = 20
    top_n = min(max(1, top_n), 100)

    with orm_session() as session:
        rows = visit_expense_dao.get_customer_expense_totals(
            session, date_start=date_start, date_end=date_end, top_n=top_n)

        # 批量查客户名称
        from app.dao.visit_dao import visit_amap_customer_dao
        poi_ids = [r["amap_customer_id"] for r in rows]
        name_map = visit_amap_customer_dao.get_customer_name_map(session, poi_ids)

    return [
        {
            "amap_customer_id": r["amap_customer_id"],
            "customer_name": name_map.get(r["amap_customer_id"], r["amap_customer_id"]),
            "amount": r["amount"],
            "count": r["count"],
        }
        for r in rows
    ]


# ==================== 内部辅助 ====================

def _count_distinct_customers(session, amap_customer_id=None,
                              date_start=None, date_end=None):
    """筛选窗口内有费用的去重客户数"""
    from sqlalchemy import func
    from app.models.orm_models.visit.visit_expense import VisitExpense

    query = session.query(func.count(func.distinct(VisitExpense.amap_customer_id))) \
        .filter(VisitExpense.status == 1)
    if amap_customer_id:
        query = query.filter(VisitExpense.amap_customer_id == amap_customer_id)
    if date_start:
        query = query.filter(VisitExpense.expense_date >= date_start)
    if date_end:
        query = query.filter(VisitExpense.expense_date <= date_end)

    return int(query.scalar() or 0)
