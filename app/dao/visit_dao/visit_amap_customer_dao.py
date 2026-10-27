# -*- coding:utf-8 -*-
# @Time    : 2026/10/12 11:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_amap_customer_dao.py
# @Software: PyCharm
"""
客访-高德端客户表（visit_amap_customer）数据访问层

职责：
1. 批量 upsert 高德客户数据（幂等键 amap_poi_id，仅更新档案字段）
2. 位置编码存在性查询（导入时精确区分新增/更新）
3. 按"名称+地址"查重（无编码行防重，设计文档 2.2）
4. 幂等建表（对应 sql/visit/visit_amap_customer.sql）
"""

from sqlalchemy import func, or_
from sqlalchemy.dialects.mysql import insert

from app.models.orm_models.base_models import BaseModels
from app.models.orm_models.visit.visit_amap_customer import VisitAmapCustomer
from app.utils.orm.session import get_engine

# 建表幂等标记（每进程只执行一次）
_table_ensured = False

# upsert 时允许更新的可变字段（排除主键、status/last_visit_time 由系统维护、created_at 仅首次插入写入）
UPDATABLE_FIELDS = (
    "customer_name", "address",
    "longitude", "latitude", "color", "tag", "description", "folder",
    "business_circle", "created_by", "photo_url", "contact_person",
    "main_repair_brands", "customer_type", "staff_count", "station_count",
    "purchase_channels", "goods_habit", "coop_merchants",
    "focus_points", "remark", "visit_time",
)


def ensure_table():
    """幂等建表（IF NOT EXISTS），每进程只执行一次。"""
    global _table_ensured
    if _table_ensured:
        return
    BaseModels.metadata.create_all(get_engine(), tables=[VisitAmapCustomer.__table__])
    _table_ensured = True


def get_existing_poi_ids(session, poi_ids, chunk_size=500):
    """
    查询已存在的 amap_poi_id 集合（用于导入时精确区分新增/更新）

    :param session: SQLAlchemy Session 对象
    :param poi_ids: amap_poi_id 列表
    :param chunk_size: 分批 IN 查询大小
    :return: set[str]
    """
    existing = set()
    poi_ids = [p for p in poi_ids if p]
    for i in range(0, len(poi_ids), chunk_size):
        chunk = poi_ids[i:i + chunk_size]
        rows = session.query(VisitAmapCustomer.amap_poi_id).filter(
            VisitAmapCustomer.amap_poi_id.in_(chunk)).all()
        existing.update(r[0] for r in rows)
    return existing


def get_by_id(session, customer_id):
    """
    按物理主键查询客户（详情页聚合用）

    :param session: SQLAlchemy Session 对象
    :param customer_id: visit_amap_customer.id（BIGINT 自增主键）
    :return: VisitAmapCustomer 或 None
    """
    return session.query(VisitAmapCustomer).filter(
        VisitAmapCustomer.id == customer_id).first()


def find_poi_id_by_name_address(session, customer_name, address):
    """
    按"名称+地址"查重，返回已存在客户的 amap_poi_id（无编码行防重，设计文档 2.2）

    :param session: SQLAlchemy Session 对象
    :param customer_name: 客户名称
    :param address: 地址
    :return: amap_poi_id 或 None
    """
    row = session.query(VisitAmapCustomer.amap_poi_id).filter_by(
        customer_name=customer_name,
        address=address,
    ).first()
    return row[0] if row else None


def bulk_upsert(session, data_list, chunk_size=500, update_fields=None):
    """
    批量插入或更新（幂等键 amap_poi_id）

    - 已存在：仅更新白名单字段；status / last_visit_time / created_at 永不覆盖
    - 不存在：插入，status 默认 0（未关联CRM）
    - update_fields: 冲突时更新的字段白名单，默认全量 UPDATABLE_FIELDS；
      仅写部分字段的调用方（如拜访记录建档只写名称）必须传入，
      否则未传字段会以 None 覆盖档案既有值

    :param session: SQLAlchemy Session 对象
    :param data_list: 数据字典列表（key 为表字段名）
    :param chunk_size: 分批提交大小
    :param update_fields: 冲突更新字段白名单（元组），None = 全量可变档案字段
    :return: 处理的记录数
    """
    if not data_list:
        return 0

    fields = tuple(update_fields) if update_fields else UPDATABLE_FIELDS
    for i in range(0, len(data_list), chunk_size):
        chunk = data_list[i:i + chunk_size]
        stmt = insert(VisitAmapCustomer).values(chunk)
        update_dict = {
            col: getattr(stmt.inserted, col)
            for col in fields
        }
        stmt = stmt.on_duplicate_key_update(update_dict)
        session.execute(stmt)

    return len(data_list)


# 多值字段筛选哨兵值：表示筛选项为"无"（字段为空 NULL 或 ''）
# 前端下拉的「无」选项传此值，正常类型名与之冲突的概率可忽略（Excel 导入自由文本）
EMPTY_MULTI = "__empty__"


def _multi_value_cond(column, value):
    """
    多值字段（| 分隔，如 customer_type="专修店|杂修店"）筛选条件

    - EMPTY_MULTI：字段为空（IS NULL 或 ''），对应下拉「无」选项
    - 其他值：整词包含匹配（| 包边后 LIKE），"专修店"可命中"专修店|杂修店"，
      且不会误命中含该词子串的其他值
    """
    if value == EMPTY_MULTI:
        return or_(column.is_(None), column == '')
    return func.concat('|', column, '|').like(f'%|{value}|%')


def page_customers(session, page=1, limit=20, customer_type=None, purchase_channels=None, keyword=None):
    """
    客户列表分页查询（M1，设计文档 doc/客访管理/01-主设计文档.md 第六节）
    支持客户类型/拿货渠道筛选 + 客户名称/地址关键词搜索；固定排除 status=2（无效客户不参与列表）。

    :param session: SQLAlchemy Session 对象
    :param page: 页码，从 1 开始
    :param limit: 每页条数
    :param customer_type: 客户类型筛选，选填（多值字段，见 _multi_value_cond）
    :param purchase_channels: 拿货渠道筛选，选填（多值字段，见 _multi_value_cond）
    :param keyword: 搜索关键词，选填（客户名称/地址模糊匹配，任一命中即返回）
    :return: (total, rows) 命中总数与当前页 ORM 对象列表
    """
    page = max(1, page or 1)
    limit = max(1, limit or 20)

    query = session.query(VisitAmapCustomer).filter(VisitAmapCustomer.status != 2)
    if customer_type:
        query = query.filter(_multi_value_cond(VisitAmapCustomer.customer_type, customer_type))
    if purchase_channels:
        query = query.filter(_multi_value_cond(VisitAmapCustomer.purchase_channels, purchase_channels))
    if keyword:
        like = f'%{keyword}%'
        query = query.filter(or_(
            VisitAmapCustomer.customer_name.like(like),
            VisitAmapCustomer.address.like(like),
        ))
    total = query.count()

    # 默认排序：最近拜访时间倒序（从未拜访排最后），时间相同时按更新时间倒序
    query = query.order_by(
        VisitAmapCustomer.last_visit_time.is_(None).asc(),
        VisitAmapCustomer.last_visit_time.desc(),
        VisitAmapCustomer.updated_at.desc(),
    )
    rows = query.offset((page - 1) * limit).limit(limit).all()
    return total, rows


def count_by_status(session, status=0):
    """
    统计指定关联状态的客户数（用于列表头"未关联CRM N 家"提示）

    :param session: SQLAlchemy Session 对象
    :param status: 关联状态 0-未关联CRM 1-已关联CRM
    :return: 数量
    """
    return session.query(VisitAmapCustomer.amap_poi_id).filter(
        VisitAmapCustomer.status == status).count()


def get_distinct_multi_values(session, column):
    """
    查询多值字段原始值（去重，排除无效客户与空值）

    多值字段（| 分隔，如 customer_type="专修店|杂修店"），此处返回原始组合值，
    由服务层拆分为单值下拉选项。

    :param session: SQLAlchemy Session 对象
    :param column: ORM 列（如 VisitAmapCustomer.customer_type）
    :return: list[str] 去重后的原始值
    """
    rows = session.query(column).filter(
        VisitAmapCustomer.status != 2,
        column.isnot(None),
        column != '',
    ).distinct().all()
    return [r[0] for r in rows]


def get_distinct_customer_types(session):
    """客户类型原始值（多值字段下拉选项，见 get_distinct_multi_values）"""
    return get_distinct_multi_values(session, VisitAmapCustomer.customer_type)


def get_distinct_purchase_channels(session):
    """拿货渠道原始值（多值字段下拉选项，见 get_distinct_multi_values）"""
    return get_distinct_multi_values(session, VisitAmapCustomer.purchase_channels)


def bump_last_visit_times(session, poi_max_times):
    """
    回写最近拜访时间（冗余字段，设计文档 4.1；仅当新拜访时间更大时更新，避免旧数据回拨）

    :param session: SQLAlchemy Session 对象
    :param poi_max_times: {amap_poi_id: 该客户本次导入中的最大记录时间}
    """
    for poi_id, max_dt in poi_max_times.items():
        if not poi_id or not max_dt:
            continue
        session.query(VisitAmapCustomer).filter(
            VisitAmapCustomer.amap_poi_id == poi_id,
            or_(VisitAmapCustomer.last_visit_time.is_(None),
                VisitAmapCustomer.last_visit_time < max_dt),
        ).update({"last_visit_time": max_dt}, synchronize_session=False)


def get_customer_name_map(session, poi_ids, chunk_size=500):
    """
    批量查询客户名称（拜访历史时间轴展示用）

    :param session: SQLAlchemy Session 对象
    :param poi_ids: amap_poi_id 列表
    :return: {amap_poi_id: customer_name}
    """
    name_map = {}
    poi_ids = [p for p in poi_ids if p]
    for i in range(0, len(poi_ids), chunk_size):
        chunk = poi_ids[i:i + chunk_size]
        rows = session.query(
            VisitAmapCustomer.amap_poi_id, VisitAmapCustomer.customer_name,
        ).filter(VisitAmapCustomer.amap_poi_id.in_(chunk)).all()
        name_map.update(rows)
    return name_map
