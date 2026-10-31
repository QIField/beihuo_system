# -*- coding:utf-8 -*-
# @Time    : 2026/10/12 17:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : amap_customer_service.py
# @Software: PyCharm
# 高德客户查询服务：M1 客户列表（分页 + 客户类型/拿货渠道筛选 + 关键词搜索
# + 拜访时间筛选 + 累计拿货额筛选，08-客户筛选功能.md）
# 列表查询见 app/dao/visit_dao/visit_amap_customer_dao.py page_customers；
# 客户详情聚合（头部 + 基础档案）拆分至 customer_detail_service.py，
# CRM 侧数据经 visit_customer_relation 绑定桥接 partner_list（只读）。

from datetime import datetime, timedelta
import re

from app.dao.visit_dao import visit_amap_customer_dao, visit_customer_owner_dao
from app.models.orm_models.system_models.crmapp_users import CrmappUsers
from app.utils.orm.session import orm_session

# 拜访状态口径（设计文档 2.4：last_visit_time 驱动 30天内已拜访/超期未拜访）
VISIT_VALID_DAYS = 30
VISIT_STATUS_VISITED = "visited_30d"   # 30天内已拜访
VISIT_STATUS_OVERDUE = "overdue"       # 超期未拜访（含从未拜访，last_visit_time 为空）

STATUS_LABELS = {0: "未关联CRM", 1: "已关联CRM", 2: "无效"}

# ==================== 地址解析（省市区镇级联下拉选项用） ====================
# 高德地址为"省+市+区县+镇街+详址"连续文本，如"广东省佛山市禅城区张槎街道玉带路41号"；
# 逐级前缀正则解析，各级均限制长度上限防止详址中的"市/区/镇"字样过度吞并；
# 解析结果仅用于生成下拉选项，筛选本身仍是对 address 的 LIKE 模糊匹配（自洽）。
_RE_PROVINCE = re.compile(r'^(?P<name>[^省]{1,10}省|.+?自治区|北京市|天津市|上海市|重庆市)')
_RE_CITY = re.compile(r'^(?P<name>.{1,12}?(?:市|自治州|地区|盟))')
_RE_DISTRICT = re.compile(r'^(?P<name>.{1,8}?(?:区|县|旗|市))')
_RE_TOWN = re.compile(r'^(?P<name>.{1,10}?(?:街道|镇|乡|苏木))')


def _parse_region(address):
    """
    地址 → (省, 市, 区县, 镇街)，逐级前缀匹配；任一级无法识别返回 None

    :param address: 地址原文，如"广东省佛山市禅城区张槎街道玉带路41号"
    :return: tuple(str|None, str|None, str|None, str|None)
    """
    text = (address or "").strip()
    province = city = district = town = None
    m = _RE_PROVINCE.match(text)
    if m:
        province = m.group("name")
        text = text[m.end():]
    m = _RE_CITY.match(text)
    if m:
        city = m.group("name")
        text = text[m.end():]
    m = _RE_DISTRICT.match(text)
    if m:
        district = m.group("name")
        # 直筒子市（东莞/中山等）无区县层级，区县位实为镇街：截断为镇街名，
        # 避免详址中的"区/市"字样被并入区县选项（如"小榄镇菊城E区" → "小榄镇"）
        m_town = _RE_TOWN.match(district)
        if m_town:
            district = m_town.group("name")
            text = text[m_town.end():]
        else:
            text = text[m.end():]
    m = _RE_TOWN.match(text)
    if m:
        town = m.group("name")
    return province, city, district, town


def _fmt_datetime(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def _serialize(row, visited_threshold, owner_names=None):
    """ORM 对象 → 列表行 dict（含拜访状态判定与展示标签）"""
    last_visit = row.last_visit_time
    if last_visit and last_visit >= visited_threshold:
        visit_status, visit_cls, visit_label = (
            VISIT_STATUS_VISITED, "v-tag--green", "30天内已拜访")
    else:
        visit_status, visit_cls, visit_label = (
            VISIT_STATUS_OVERDUE, "v-tag--red", "超期未拜访")

    return {
        "id": row.id,
        "poi": row.amap_poi_id,
        "customer_name": row.customer_name,
        "tag": row.tag,
        "address": row.address,
        "customer_type": row.customer_type,
        "business_circle": row.business_circle,
        "contact_person": row.contact_person,
        "status": row.status,
        "status_label": STATUS_LABELS.get(row.status, "未知"),
        "visit_status": visit_status,
        "visit_status_label": visit_label,
        "visit_status_cls": visit_cls,
        # 负责人姓名/用户名，逗号分割展示（07-负责人绑定.md 查询场景），如"张三,李四"
        "owner_names": owner_names or "",
        "last_visit_time": _fmt_datetime(last_visit),
        "visit_time": _fmt_datetime(row.visit_time),
        "created_at": _fmt_datetime(row.created_at),
    }


def get_customer_list(page=1, limit=20, customer_type=None, purchase_channels=None,
                      keyword=None, visit_days=None, min_amount=None, max_amount=None,
                      province=None, city=None, district=None, town=None):
    """
    分页查询客户列表（M1，支持客户类型/拿货渠道筛选 + 客户名称/地址关键词搜索
    + 拜访时间筛选（超 X 天未拜访）+ 累计拿货额筛选（金额区间）
    + 省市区镇地址筛选（逐级 LIKE 模糊匹配））

    :param page: 页码
    :param limit: 每页条数（最大 200）
    :param customer_type: 客户类型筛选，选填（多值字段按整词包含匹配，
                          哨兵值 EMPTY_MULTI 表示筛选"无"）
    :param purchase_channels: 拿货渠道筛选，选填（同上）
    :param keyword: 搜索关键词，选填（客户名称/地址模糊匹配，任一命中即返回）
    :param visit_days: 拜访时间筛选 —— 仅返回"超过 visit_days 天未拜访"的客户，
                       选填（None = 不启用；0 = 筛选从未拜访；> 0 = 超 X 天未拜访）
    :param min_amount: 累计拿货额下限（≥），选填（None = 不限）
    :param max_amount: 累计拿货额上限（≤），选填（None = 不限）
    :param province: 省份筛选，选填（地址 LIKE 模糊匹配，None = 不限）
    :param city: 城市筛选，选填（同上）
    :param district: 区县筛选，选填（同上）
    :param town: 镇街筛选，选填（同上）
    :return: {'list': [...], 'total': N, 'page': p, 'limit': l, 'unbound_count': N}
    """
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        limit = min(max(1, int(limit)), 200)
    except (TypeError, ValueError):
        limit = 20

    # 空白视为未筛选，避免 LIKE 匹配空词导致恒空结果
    customer_type = (customer_type or "").strip() or None
    purchase_channels = (purchase_channels or "").strip() or None
    keyword = (keyword or "").strip() or None
    province = (province or "").strip() or None
    city = (city or "").strip() or None
    district = (district or "").strip() or None
    town = (town or "").strip() or None

    # 拜访时间筛选：前端传入字符串 "0"/"10"/"30" → 转 int；空字符串/None = 不启用
    try:
        visit_days = int(visit_days) if visit_days not in (None, "", None) else None
    except (TypeError, ValueError):
        visit_days = None

    # 累计拿货额筛选：前端传入金额字符串 → 转 float；空字符串/None = 不限
    try:
        min_amount = float(min_amount) if min_amount not in (None, "") else None
    except (TypeError, ValueError):
        min_amount = None
    try:
        max_amount = float(max_amount) if max_amount not in (None, "") else None
    except (TypeError, ValueError):
        max_amount = None

    visited_threshold = datetime.now() - timedelta(days=VISIT_VALID_DAYS)

    with orm_session() as session:
        total, rows = visit_amap_customer_dao.page_customers(
            session, page=page, limit=limit,
            customer_type=customer_type, purchase_channels=purchase_channels,
            keyword=keyword, visit_days=visit_days,
            min_amount=min_amount, max_amount=max_amount,
            province=province, city=city, district=district, town=town)
        unbound_count = visit_amap_customer_dao.count_by_status(session, status=0)

        # 负责人列（多对多联 crmapp_users，客户 id → "张三,李四"，逗号分割展示）
        owner_rows = visit_customer_owner_dao.list_by_customer_ids(
            session, [r.id for r in rows])
        owner_names_map = {}
        if owner_rows:
            users = session.query(CrmappUsers).filter(
                CrmappUsers.id.in_({r.user_id for r in owner_rows})).all()
            user_map = {u.id: u.username for u in users}
            for owner in owner_rows:
                name = user_map.get(owner.user_id)
                if name:
                    owner_names_map.setdefault(owner.visit_amap_customer_id, []).append(name)
        owner_names_map = {cid: ",".join(names) for cid, names in owner_names_map.items()}

        # 会话内完成序列化，避免会话关闭后访问过期实例（DetachedInstanceError）
        items = [_serialize(r, visited_threshold, owner_names_map.get(r.id, ""))
                 for r in rows]

    return {
        "list": items,
        "total": total,
        "page": page,
        "limit": limit,
        "unbound_count": unbound_count,
    }


def get_filter_options():
    """
    列表筛选下拉选项（来源：visit_amap_customer 实际数据，随导入动态变化）

    customer_type / purchase_channels 均为 | 分隔多值字段，拆分为单值后去重排序。

    :return: {'customer_types': [...], 'purchase_channels': [...]}
    """
    with orm_session() as session:
        types_raw = visit_amap_customer_dao.get_distinct_customer_types(session)
        channels_raw = visit_amap_customer_dao.get_distinct_purchase_channels(session)
    return {
        "customer_types": sorted({t for raw in types_raw for t in raw.split('|') if t}),
        "purchase_channels": sorted({c for raw in channels_raw for c in raw.split('|') if c}),
    }


def get_region_options():
    """
    省市区镇级联下拉选项（客户列表地址筛选用）

    口径与 get_filter_options 一致：取库中实际地址动态解析生成，只出现有客户的区域；
    省市区三级齐全的地址才进入选项树（直辖市/无省份等无法逐级解析的地址跳过），
    镇街可选（无镇街的区县仍保留区县选项）。

    :return: {'provinces': [{'name': 省, 'cities': [{'name': 市, 'districts': [
                {'name': 区县, 'towns': [镇街...]}...]}...]}...]}，各级名称字典序排序
    """
    with orm_session() as session:
        addresses = visit_amap_customer_dao.get_all_addresses(session)

    # 嵌套聚合：{省: {市: {区县: set(镇街)}}}
    tree = {}
    for addr in addresses:
        province, city, district, town = _parse_region(addr)
        if not province or not city or not district:
            continue
        towns = tree.setdefault(province, {}).setdefault(city, {}).setdefault(district, set())
        if town:
            towns.add(town)

    # 嵌套 dict → 有序列表（名称字典序），前端直接按级联渲染
    provinces = []
    for province_name in sorted(tree):
        cities = []
        for city_name in sorted(tree[province_name]):
            districts = []
            for district_name in sorted(tree[province_name][city_name]):
                districts.append({
                    "name": district_name,
                    "towns": sorted(tree[province_name][city_name][district_name]),
                })
            cities.append({"name": city_name, "districts": districts})
        provinces.append({"name": province_name, "cities": cities})
    return {"provinces": provinces}

