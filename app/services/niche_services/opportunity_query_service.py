# -*- coding:utf-8 -*-
"""
商机查询服务

提供 niche_opportunity 表的查询接口，供前端页面展示使用。
数据由每日定时任务（opportunity_compute_service）全量刷新，
本服务仅负责读取，不涉及任何写入操作。
"""

from sqlalchemy import or_, case, func
from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger
from app.models.orm_models.niche.niche_opportunity import NicheOpportunity

logger = get_task_logger('niche')


LEVEL_ORDER = case(
    (NicheOpportunity.opportunity_level == 'S', 1),
    (NicheOpportunity.opportunity_level == 'A', 2),
    (NicheOpportunity.opportunity_level == 'B', 3),
    (NicheOpportunity.opportunity_level == 'C', 4),
    (NicheOpportunity.opportunity_level == 'D', 5),
    else_=6,
)


def get_niche_opportunity_list(
    keyword: str = '',
    opportunity_level: str = '',
    min_score: float = 0,
    min_oos_rate: float = 0,
    has_replenish: int = 0,
    page: int = 1,
    limit: int = 50,
    sort_field: str = '',
    sort_order: str = 'desc',
) -> dict:
    """
    分页查询商机列表（服务端排序 + 分页）

    支持关键词搜索（oe_code / brand_name / part_name）、
    商机等级筛选、最低商机评分筛选、最低缺货率筛选、是否有补货建议筛选，以及任意字段排序。

    Args:
        keyword: 搜索关键词（匹配 OE码/品牌/配件名称）
        opportunity_level: 商机等级（S/A/B/C/D）
        min_score: 最低商机评分
        min_oos_rate: 最低缺货率（0~1）
        has_replenish: 是否有补货建议（1=是，0=全部）
        page: 页码，从 1 开始
        limit: 每页条数，默认 50，最大 500
        sort_field: 排序字段名（对应 NicheOpportunity 模型属性名，如 'opportunity_score'）
        sort_order: 排序方向，'asc' 升序 / 'desc' 降序

    Returns:
        dict: { 'list': [...], 'total': 100, 'page': 1, 'limit': 50 }
    """
    page = max(1, page)
    limit = max(1, min(limit, 500))
    offset = (page - 1) * limit

    with orm_session() as session:
        query = session.query(NicheOpportunity)

        # 关键词搜索
        if keyword:
            kw = f'%{keyword}%'
            query = query.filter(
                or_(
                    NicheOpportunity.oe_code.like(kw),
                    NicheOpportunity.brand_name.like(kw),
                    NicheOpportunity.part_name.like(kw),
                )
            )

        # 商机等级筛选
        if opportunity_level:
            query = query.filter(NicheOpportunity.opportunity_level == opportunity_level)

        # 最低商机评分
        if min_score > 0:
            query = query.filter(NicheOpportunity.opportunity_score >= min_score)

        # 最低缺货率
        if min_oos_rate > 0:
            query = query.filter(NicheOpportunity.out_of_stock_rate_30d >= min_oos_rate)

        # 是否有补货建议
        if has_replenish == 1:
            query = query.filter(NicheOpportunity.replenish_suggestion > 0)

        # 总数统计
        total = query.count()

        # 排序
        if sort_field:
            sort_col = getattr(NicheOpportunity, sort_field, None)
            if sort_col is not None:
                if sort_order == 'desc':
                    query = query.order_by(sort_col.desc())
                else:
                    query = query.order_by(sort_col.asc())
        else:
            # 默认排序：商机等级（S→A→B→C→D）+ 商机评分降序
            query = query.order_by(LEVEL_ORDER, NicheOpportunity.opportunity_score.desc())

        # 分页
        rows = query.offset(offset).limit(limit).all()
        result_list = [row.to_dict() for row in rows]

    return {
        'list': result_list,
        'total': total,
        'page': page,
        'limit': limit,
    }


def get_level_count() -> dict:
    """
    统计各商机等级的产品数量（用于前端卡片展示）

    Returns:
        dict: {'S': 10, 'A': 20, 'B': 30, 'C': 40, 'D': 50}
    """
    labels = ['S', 'A', 'B', 'C', 'D']

    with orm_session() as session:
        rows = (
            session.query(NicheOpportunity.opportunity_level, func.count(NicheOpportunity.id).label('cnt'))
            .group_by(NicheOpportunity.opportunity_level)
            .all()
        )

    result = {label: 0 for label in labels}
    for row in rows:
        label = row.opportunity_level or ''
        if label in result:
            result[label] += row.cnt

    return result


def get_top_opportunities(top_n: int = 10) -> list:
    """
    获取商机评分最高的 Top N 记录

    Args:
        top_n: 返回记录数，默认 10

    Returns:
        list[dict]: 商机记录字典列表
    """
    with orm_session() as session:
        rows = (
            session.query(NicheOpportunity)
            .order_by(LEVEL_ORDER, NicheOpportunity.opportunity_score.desc())
            .limit(top_n)
            .all()
        )
        return [row.to_dict() for row in rows]


def get_replenish_count() -> int:
    """
    获取有补货建议的记录数量

    Returns:
        int: 补货建议记录数
    """
    with orm_session() as session:
        return (
            session.query(NicheOpportunity)
            .filter(NicheOpportunity.replenish_suggestion > 0)
            .count()
        )
