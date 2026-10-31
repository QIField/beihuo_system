# -*- coding:utf-8 -*-
# @Time    : 2026/10/29 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_expense_dao.py
# @Software: PyCharm
"""
客访-拜访费用明细表（visit_expense）数据访问层

职责：
1. 幂等建表（对应 sql/visit/visit_expense.sql）
2. 单条/批量新增、编辑、作废、恢复（CRUD）
3. 多条件筛选分页查询
4. 按关联记录查询（拜访时间轴内嵌费用展示）
5. 汇总聚合（总利益公式各项 / 月度趋势 / 客户排名 / 类型占比）
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func

from app.models.orm_models.base_models import BaseModels
from app.models.orm_models.visit.visit_expense import VisitExpense
from app.utils.orm.session import get_engine

# 建表幂等标记（每进程只执行一次）
_table_ensured = False


def ensure_table():
    """幂等建表（IF NOT EXISTS），每进程只执行一次。"""
    global _table_ensured
    if _table_ensured:
        return
    BaseModels.metadata.create_all(get_engine(), tables=[VisitExpense.__table__])
    _table_ensured = True


# ==================== 写操作 ====================

def create_expense(session, data):
    """
    新增单条费用

    :param session: SQLAlchemy Session 对象
    :param data: 数据字典（key 为表字段名）
    :return: VisitExpense ORM 对象
    """
    row = VisitExpense(**data)
    session.add(row)
    session.flush()  # 获取自增 id
    return row


def bulk_create_expenses(session, data_list):
    """
    批量新增费用（在调用方事务内执行，不另起事务）

    :param session: SQLAlchemy Session 对象
    :param data_list: 数据字典列表
    :return: 处理的记录数
    """
    if not data_list:
        return 0
    for data in data_list:
        session.add(VisitExpense(**data))
    session.flush()
    return len(data_list)


def update_expense(session, expense_id, update_fields):
    """
    编辑费用（仅允许金额/类型/说明，由 service 层控制可写字段）

    :param session: SQLAlchemy Session 对象
    :param expense_id: 费用记录 ID
    :param update_fields: 待更新字段 dict
    :return: 更新后的 ORM 对象或 None（未找到）
    """
    row = session.query(VisitExpense).filter(VisitExpense.id == expense_id).first()
    if not row:
        return None
    for col, val in update_fields.items():
        setattr(row, col, val)
    session.flush()
    return row


def set_expense_status(session, expense_id, status):
    """
    设置费用状态（作废/恢复）

    :param session: SQLAlchemy Session 对象
    :param expense_id: 费用记录 ID
    :param status: 1-正常 0-作废
    :return: 更新后的 ORM 对象或 None
    """
    row = session.query(VisitExpense).filter(VisitExpense.id == expense_id).first()
    if not row:
        return None
    row.status = status
    session.flush()
    return row


# ==================== 读操作 ====================

def get_expense_by_id(session, expense_id):
    """按 ID 查询单条"""
    return session.query(VisitExpense).filter(VisitExpense.id == expense_id).first()


def get_by_source(session, source_type, source_id):
    """
    按关联记录查询费用列表（拜访时间轴卡片内嵌展示用）

    :param session: SQLAlchemy Session 对象
    :param source_type: 1-拜访 2-跟进
    :param source_id: visit_record.id 或 visit_follow_record.id
    :return: ORM 对象列表（按 expense_date desc, id desc）
    """
    return (session.query(VisitExpense)
            .filter(VisitExpense.source_type == source_type,
                    VisitExpense.source_id == source_id,
                    VisitExpense.status == 1)
            .order_by(VisitExpense.expense_date.desc(), VisitExpense.id.desc())
            .all())


def page_expenses(session, page=1, limit=20, amap_customer_id=None,
                  amap_customer_ids=None, recorder_id=None, status=None,
                  date_start=None, date_end=None):
    """
    费用明细分页查询（费用分析页列表）

    :param session: SQLAlchemy Session 对象
    :param page: 页码，从 1 开始
    :param limit: 每页条数
    :param amap_customer_id: 按单个客户 POI 筛选，选填
    :param amap_customer_ids: 按多个客户 POI 筛选（客户名称搜索结果），选填
    :param recorder_id: 按录入人筛选，选填
    :param status: 状态筛选（不传默认只看正常）
    :param date_start: 费用日期起（含），格式 'YYYY-MM-DD'
    :param date_end: 费用日期止（含），格式 'YYYY-MM-DD'
    :return: (total, rows) 命中总数与当前页 ORM 对象列表
    """
    page = max(1, page or 1)
    limit = max(1, limit or 20)

    query = session.query(VisitExpense)

    # 状态筛选：默认只看正常；传了则精确匹配
    if status is None:
        query = query.filter(VisitExpense.status == 1)
    else:
        query = query.filter(VisitExpense.status == status)

    if amap_customer_id:
        query = query.filter(VisitExpense.amap_customer_id == amap_customer_id)
    if amap_customer_ids:
        query = query.filter(VisitExpense.amap_customer_id.in_(amap_customer_ids))
    if recorder_id:
        query = query.filter(VisitExpense.recorder_id == recorder_id)
    if date_start:
        query = query.filter(VisitExpense.expense_date >= date_start)
    if date_end:
        query = query.filter(VisitExpense.expense_date <= date_end)

    total = query.count()
    rows = query.order_by(VisitExpense.expense_date.desc(), VisitExpense.id.desc()) \
        .offset((page - 1) * limit).limit(limit).all()
    return total, rows


# ==================== 聚合查询 ====================

def get_expense_sum(session, amap_customer_id=None, date_start=None, date_end=None,
                     exclude_voided=True):
    """
    费用合计（指定时间窗口 + 客户）

    :param session: SQLAlchemy Session 对象
    :param amap_customer_id: 按客户筛选，选填
    :param date_start: 起，选填
    :param date_end: 止，选填
    :param exclude_voided: 是否排除作废，默认 True
    :return: Decimal 金额合计（0 表示无数据）
    """
    query = session.query(func.coalesce(func.sum(VisitExpense.amount), 0))
    if exclude_voided:
        query = query.filter(VisitExpense.status == 1)
    if amap_customer_id:
        query = query.filter(VisitExpense.amap_customer_id == amap_customer_id)
    if date_start:
        query = query.filter(VisitExpense.expense_date >= date_start)
    if date_end:
        query = query.filter(VisitExpense.expense_date <= date_end)
    return query.scalar() or 0


def get_type_breakdown(session, amap_customer_id=None, date_start=None, date_end=None):
    """
    费用类型占比（按 expense_type 分组聚合）

    :param session: SQLAlchemy Session 对象
    :param amap_customer_id: 按客户筛选，选填
    :param date_start: 起，选填
    :param date_end: 止，选填
    :return: [{'type': str, 'amount': float, 'count': int, 'ratio': float}, ...]
             按 amount 降序，ratio 为类型金额占总金额比例（0~1）
    """
    query = (session.query(VisitExpense.expense_type,
                           func.sum(VisitExpense.amount).label('amount'),
                           func.count(VisitExpense.id).label('count'))
             .filter(VisitExpense.status == 1))

    if amap_customer_id:
        query = query.filter(VisitExpense.amap_customer_id == amap_customer_id)
    if date_start:
        query = query.filter(VisitExpense.expense_date >= date_start)
    if date_end:
        query = query.filter(VisitExpense.expense_date <= date_end)

    rows = query.group_by(VisitExpense.expense_type) \
        .order_by(func.sum(VisitExpense.amount).desc()).all()

    total = sum(float(r.amount or 0) for r in rows)
    breakdown = []
    for r in rows:
        amount = float(r.amount or 0)
        breakdown.append({
            "type": r.expense_type,
            "amount": amount,
            "count": int(r.count),
            "ratio": round(amount / total, 4) if total > 0 else 0,
        })
    return breakdown


def get_monthly_trend(session, months=12, amap_customer_id=None):
    """
    月度费用趋势（近 N 个月，按月分组）

    :param session: SQLAlchemy Session 对象
    :param months: 取近几个月，默认 12
    :param amap_customer_id: 按客户筛选，选填
    :return: [{'month': '2026-01', 'amount': float}, ...] 按月份升序
             空月填充 amount=0，保证折线连续
    """
    today = date.today()
    # 生成月份列表（YYYY-MM）
    month_list = []
    for i in range(months - 1, -1, -1):
        d = today.replace(day=1) - timedelta(days=30 * i)
        month_list.append(d.strftime("%Y-%m"))

    # 只查最近 months 个月的费用
    from sqlalchemy import extract
    query = (session.query(
                 func.date_format(VisitExpense.expense_date, '%Y-%m').label('month'),
                 func.coalesce(func.sum(VisitExpense.amount), 0).label('amount'))
             .filter(VisitExpense.status == 1))

    # 时间范围：最早月份的第一天
    earliest = (today.replace(day=1) - timedelta(days=30 * (months - 1))).replace(day=1)
    query = query.filter(VisitExpense.expense_date >= earliest)

    if amap_customer_id:
        query = query.filter(VisitExpense.amap_customer_id == amap_customer_id)

    rows = query.group_by(func.date_format(VisitExpense.expense_date, '%Y-%m')).all()
    row_map = {r.month: float(r.amount or 0) for r in rows}

    # 填充空月
    return [{"month": m, "amount": row_map.get(m, 0.0)} for m in month_list]


def get_customer_expense_totals(session, date_start=None, date_end=None, top_n=20):
    """
    客户费用排名（按客户汇总费用，Top N）

    :param session: SQLAlchemy Session 对象
    :param date_start: 起，选填
    :param date_end: 止，选填
    :param top_n: 返回前 N 个客户，默认 20
    :return: [{'amap_customer_id': str, 'amount': float, 'count': int}, ...]
             按 amount 降序
    """
    query = (session.query(VisitExpense.amap_customer_id,
                           func.sum(VisitExpense.amount).label('amount'),
                           func.count(VisitExpense.id).label('count'))
             .filter(VisitExpense.status == 1,
                     VisitExpense.amap_customer_id.isnot(None)))

    if date_start:
        query = query.filter(VisitExpense.expense_date >= date_start)
    if date_end:
        query = query.filter(VisitExpense.expense_date <= date_end)

    rows = query.group_by(VisitExpense.amap_customer_id) \
        .order_by(func.sum(VisitExpense.amount).desc()) \
        .limit(top_n).all()

    return [
        {
            "amap_customer_id": r.amap_customer_id,
            "amount": float(r.amount or 0),
            "count": int(r.count),
        }
        for r in rows
    ]
