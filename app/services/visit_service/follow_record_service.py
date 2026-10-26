# -*- coding:utf-8 -*-
# @Time    : 2026/10/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : follow_record_service.py
# @Software: PyCharm
# 跟进记录服务：M7 跟进时间轴（分页 + 渠道筛选）+ 手动新增/编辑/作废
# 设计文档 doc/客访管理/04-跟进记录模块设计.md；接口层见 app/api/visit/visit_follow_api.py。
# 跟进记录与拜访记录（visit_record）完全独立：唯一写入渠道为后台表单，无自动联动。

from datetime import datetime

from app.dao.visit_dao import visit_amap_customer_dao, visit_follow_record_dao, visit_record_dao
from app.utils.orm.session import orm_session

# 跟进渠道固定枚举（04 设计文档第二节，本期不做字典表）
CHANNELS = ("微信", "电话", "线上平台", "上门", "其他")

# 拜访历史合并展示类型（只读：不可编辑/作废，不落 visit_follow_record 表）
VISIT_CHANNEL = "拜访同步"

# 时间轴单侧拉取上限（手动跟进 / 拜访历史各拉一页后内存合并排序）
TIMELINE_PULL_LIMIT = 200

# channel → 默认时间轴标题（channel_desc），前端可覆盖
CHANNEL_DESC_DEFAULTS = {
    "微信": "微信沟通",
    "电话": "电话沟通",
    "线上平台": "线上平台沟通",
    "上门": "上门拜访",
    "其他": "跟进沟通",
}

# 无效客户状态（visit_amap_customer.status，见 amap_customer_service.STATUS_LABELS）
STATUS_INVALID = 2

TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
)


def _parse_customer_id(customer_id):
    """客户标识清洗：非正整数视为非法"""
    try:
        customer_id = int(str(customer_id).strip())
    except (TypeError, ValueError):
        raise ValueError("客户标识不合法")
    if customer_id <= 0:
        raise ValueError("缺少客户标识")
    return customer_id


def _parse_follow_time(value):
    """
    跟进时间解析：兼容 datetime 与字符串；空值取当前时间

    :raises ValueError: 格式非法 / 晚于当前时间（不允许预约式跟进，仅可补录过去）
    """
    if value is None or not str(value).strip():
        return datetime.now().replace(microsecond=0)
    if isinstance(value, datetime):
        ft = value.replace(microsecond=0)
    else:
        s = str(value).strip()
        ft = None
        for fmt in TIME_FORMATS:
            try:
                ft = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
        if ft is None:
            raise ValueError("跟进时间格式不合法")
    if ft > datetime.now():
        raise ValueError("跟进时间不能晚于当前时间")
    return ft


def _validate_channel(channel):
    """渠道校验：必须在固定枚举内"""
    channel = (channel or "").strip()
    if not channel:
        raise ValueError("跟进渠道不能为空")
    if channel not in CHANNELS:
        raise ValueError("跟进渠道不合法，可选值：微信/电话/线上平台/上门/其他")
    return channel


def _validate_content(content):
    """内容校验：去空白后非空"""
    content = (content or "").strip()
    if not content:
        raise ValueError("跟进内容不能为空")
    return content


def _resolve_desc(channel, channel_desc):
    """时间轴标题：显式传入优先，否则按渠道映射默认值"""
    desc = (channel_desc or "").strip()
    return desc[:100] or CHANNEL_DESC_DEFAULTS.get(channel, "跟进沟通")


def _get_customer_or_raise(session, customer_id):
    """校验客户存在且非无效（status=2 闭店/错误采集，拒绝新增跟进）"""
    row = visit_amap_customer_dao.get_by_id(session, customer_id)
    if not row:
        raise ValueError("客户不存在或已被删除")
    if row.status == STATUS_INVALID:
        raise ValueError("无效客户不允许新增跟进")
    return row


def _serialize(row):
    """ORM 对象 → 时间轴行 dict（须在会话内调用，避免 DetachedInstanceError）"""
    return {
        "id": row.id,
        "is_visit": False,
        "amap_customer_id": row.amap_customer_id,
        "channel": row.channel,
        "channel_desc": row.channel_desc,
        "content": row.content,
        "follow_time": row.follow_time.strftime("%Y-%m-%d %H:%M:%S") if row.follow_time else None,
        "creator_id": row.creator_id,
        "creator_name": row.creator_name,
    }


def _visit_to_item(row):
    """
    拜访记录 → 时间轴条目（类型=拜访同步，只读）

    拜访历史不落 visit_follow_record 表（两表保持独立），仅在时间轴查询时
    合并展示：不可编辑/作废，前端提供"查看完整拜访详情"跳转拜访历史 Tab。
    """
    return {
        "id": row.id,
        "is_visit": True,
        "amap_customer_id": row.amap_customer_id,
        "channel": VISIT_CHANNEL,
        "channel_desc": "上门拜访",
        "content": row.content,
        "follow_time": row.visit_time.strftime("%Y-%m-%d %H:%M:%S") if row.visit_time else None,
        "creator_id": None,
        "creator_name": row.recorder,
    }


def get_follow_list(customer_id, page=1, limit=20, channel=None):
    """
    分页查询跟进时间轴（M7：手动跟进 + 拜访历史合并，按时间倒序）

    拜访历史以"拜访同步"类型并入时间轴（只读、不可编辑/作废），
    两表保持独立、不做落库合并；内存合并后按 follow_time 倒序切片分页。

    :param customer_id: visit_amap_customer 物理主键 id（URL 避免透传含逗号的 POI 编码）
    :param page: 页码
    :param limit: 每页条数（最大 200）
    :param channel: 跟进渠道筛选，选填（含"拜访同步"）
    :return: {'list': [...], 'total': N, 'page': p, 'limit': l, 'channels': [...]}
    """
    customer_id = _parse_customer_id(customer_id)
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        limit = min(max(1, int(limit)), TIMELINE_PULL_LIMIT)
    except (TypeError, ValueError):
        limit = 20

    # 空白视为未筛选
    channel = (channel or "").strip() or None
    if channel and channel != VISIT_CHANNEL and channel not in CHANNELS:
        raise ValueError("跟进渠道不合法，可选值：微信/电话/线上平台/上门/其他/拜访同步")

    with orm_session() as session:
        customer = _get_customer_or_raise(session, customer_id)
        poi = customer.amap_poi_id
        items = []
        # 手动跟进（筛选"拜访同步"时跳过）
        if channel != VISIT_CHANNEL:
            _, follow_rows = visit_follow_record_dao.page_follows(
                session, page=1, limit=TIMELINE_PULL_LIMIT,
                amap_customer_id=poi, channel=channel)
            items.extend(_serialize(r) for r in follow_rows)
        # 拜访历史合并（仅未筛选或筛选"拜访同步"时拉取）
        if channel in (None, VISIT_CHANNEL):
            _, visit_rows = visit_record_dao.page_records(
                session, page=1, limit=TIMELINE_PULL_LIMIT, amap_customer_id=poi)
            items.extend(_visit_to_item(r) for r in visit_rows)

    # 统一按时间倒序（同为 "%Y-%m-%d %H:%M:%S" 格式，字符串排序即可）
    items.sort(key=lambda x: x["follow_time"] or "", reverse=True)
    start = (page - 1) * limit

    return {
        "list": items[start:start + limit],
        "total": len(items),
        "page": page,
        "limit": limit,
        "channels": list(CHANNELS),  # 手动表单渠道枚举（"拜访同步"仅供筛选，不可手选）
    }


def add_follow(customer_id, channel, content, follow_time=None, channel_desc="",
               creator_id=None, creator_name=""):
    """
    新增跟进记录（唯一写入渠道：后台表单，source 概念已随设计修订移除）

    :param customer_id: visit_amap_customer 物理主键 id
    :param channel: 跟进渠道（固定枚举）
    :param content: 跟进内容，非空
    :param follow_time: 跟进时间，缺省当前时间，允许补录过去时间
    :param channel_desc: 时间轴标题，空则按渠道映射默认值
    :param creator_id: 记录人ID（session user_id，可为空）
    :param creator_name: 记录人（session username，非空）
    :return: 新增记录 dict
    """
    customer_id = _parse_customer_id(customer_id)
    channel = _validate_channel(channel)
    content = _validate_content(content)
    follow_time = _parse_follow_time(follow_time)
    channel_desc = _resolve_desc(channel, channel_desc)
    creator_name = (creator_name or "").strip() or "未知"

    with orm_session() as session:
        customer = _get_customer_or_raise(session, customer_id)
        row = visit_follow_record_dao.insert_follow(session, {
            "amap_customer_id": customer.amap_poi_id,
            "channel": channel,
            "channel_desc": channel_desc,
            "content": content,
            "follow_time": follow_time,
            "creator_id": creator_id,
            "creator_name": creator_name,
            "status": 1,
        })
        item = _serialize(row)

    return item


def update_follow(follow_id, channel=None, content=None, follow_time=None, channel_desc=None):
    """
    编辑跟进记录（部分更新：仅更新传入的字段）

    标题规则：channel_desc 显式传入非空优先；否则渠道变更时按新渠道重映射默认值。

    :param follow_id: 跟进记录主键 id
    :param channel: 跟进渠道，选填
    :param content: 跟进内容，选填
    :param follow_time: 跟进时间，选填
    :param channel_desc: 时间轴标题，选填
    :return: 更新后记录 dict
    """
    try:
        follow_id = int(str(follow_id).strip())
    except (TypeError, ValueError):
        raise ValueError("跟进记录标识不合法")
    if follow_id <= 0:
        raise ValueError("缺少跟进记录标识")

    fields = {}
    if channel is not None:
        fields["channel"] = _validate_channel(channel)
    if content is not None:
        fields["content"] = _validate_content(content)
    if follow_time is not None and str(follow_time).strip():
        fields["follow_time"] = _parse_follow_time(follow_time)

    with orm_session() as session:
        row = visit_follow_record_dao.get_by_id(session, follow_id)
        if not row or row.status != 1:
            raise ValueError("跟进记录不存在或已作废")
        if fields.get("channel") and not (channel_desc or "").strip():
            # 渠道变更且未显式指定标题 → 按新渠道重映射默认值
            fields["channel_desc"] = CHANNEL_DESC_DEFAULTS.get(fields["channel"], "跟进沟通")
        elif (channel_desc or "").strip():
            # 显式传入非空标题 → 覆盖；空白且渠道未变 → 保留原标题
            fields["channel_desc"] = _resolve_desc(
                fields.get("channel", row.channel), channel_desc)

        if fields:
            visit_follow_record_dao.update_fields(session, follow_id, fields)
        # 会话内重查序列化，避免更新后实例状态不一致
        row = visit_follow_record_dao.get_by_id(session, follow_id)
        item = _serialize(row)

    return item


def void_follow(follow_id):
    """
    作废跟进记录（status=0 软删，时间轴排除；本期不提供恢复）

    :param follow_id: 跟进记录主键 id
    :return: 作废记录 id
    """
    try:
        follow_id = int(str(follow_id).strip())
    except (TypeError, ValueError):
        raise ValueError("跟进记录标识不合法")
    if follow_id <= 0:
        raise ValueError("缺少跟进记录标识")

    with orm_session() as session:
        row = visit_follow_record_dao.get_by_id(session, follow_id)
        if not row or row.status != 1:
            raise ValueError("跟进记录不存在或已作废")
        visit_follow_record_dao.update_fields(session, follow_id, {"status": 0})

    return follow_id
