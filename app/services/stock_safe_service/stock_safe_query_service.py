# -*- coding:utf-8 -*-
# @Time    : 2026/08/13
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_query_service.py
# @Software: trae-cn

"""
安全库存查询服务

提供 stock_safe 表的查询接口，供前端页面展示使用。
数据由每日定时任务（stock_safe_compute_service）全量刷新，
本服务仅负责读取，不涉及任何写入操作。

查询使用 SQLAlchemy ORM 语法，与 stock_safe ORM 模型字段一一对应。
"""

from sqlalchemy import or_, case, asc, desc
from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger
from app.models.orm_models.stock_safe_models.stock_safe import StockSafe

logger = get_task_logger('stock_safe')


def get_stock_safe_list(
    keyword: str = '',
    stock_status: str = '',
    abc_classification: str = '',
    page: int = 1,
    limit: int = 50,
    sort_field: str = '',
    sort_order: str = 'asc',
) -> dict:
    """
    分页查询安全库存列表（服务端排序 + 分页）

    支持关键词搜索（number / brand_name / pdname / frey_no）、
    库存状态筛选、ABC 分类筛选，以及任意字段排序。

    Args:
        keyword: 搜索关键词（匹配 OE号/品牌/产品名称/条码）
        stock_status: 库存状态筛选
        abc_classification: ABC 分类筛选（A/B/C）
        page: 页码，从 1 开始
        limit: 每页条数，默认 50，最大 500
        sort_field: 排序字段名（对应 StockSafe 模型属性名，如 'available_stock'）
        sort_order: 排序方向，'asc' 升序 / 'desc' 降序

    Returns:
        dict: { 'list': [...], 'total': 100, 'page': 1, 'limit': 50 }
    """
    # 参数校验与范围限制
    page = max(1, page)
    limit = max(1, min(limit, 500))
    offset = (page - 1) * limit

    with orm_session() as session:
        # 构建基础查询
        query = session.query(StockSafe)

        # ---- 关键词搜索（多字段 LIKE 匹配） ----
        if keyword:
            kw = f'%{keyword}%'
            query = query.filter(
                or_(
                    StockSafe.number.like(kw),
                    StockSafe.brand_name.like(kw),
                    StockSafe.pdname.like(kw),
                    StockSafe.frey_no.like(kw),
                )
            )

        # ---- 库存状态筛选 ----
        if stock_status:
            query = query.filter(StockSafe.stock_status == stock_status)

        # ---- ABC 分类筛选 ----
        if abc_classification:
            query = query.filter(StockSafe.abc_classification == abc_classification)

        # ---- 总数统计（在分页和排序前执行） ----
        total = query.count()

        # ---- 排序 ----
        # 优先使用前端指定的排序字段
        if sort_field:
            # 通过 getattr 安全获取模型属性，避免 SQL 注入
            sort_col = getattr(StockSafe, sort_field, None)
            if sort_col is not None:
                if sort_order == 'desc':
                    query = query.order_by(sort_col.desc())
                else:
                    query = query.order_by(sort_col.asc())
        else:
            # 默认排序：ABC 分类（A→B→C）+ 可用库存升序
            query = query.order_by(
                case(
                    (StockSafe.abc_classification == 'A', 1),
                    (StockSafe.abc_classification == 'B', 2),
                    (StockSafe.abc_classification == 'C', 3),
                    else_=4,
                ),
                StockSafe.available_stock.asc(),
            )

        # ---- 分页查询 ----
        rows = query.offset(offset).limit(limit).all()

        # ---- 转换为字典列表 ----
        result_list = [row.to_dict() for row in rows]

    return {
        'list': result_list,
        'total': total,
        'page': page,
        'limit': limit,
    }


def get_status_count() -> dict:
    """
    统计各库存状态的产品数量（用于前端卡片展示）

    Returns:
        dict: { '呆滞清库': 10, '慢动销去库': 5, '紧急补货': 8, '需补货': 20, '库存积压': 3, '正常': 100 }
    """
    with orm_session() as session:
        from sqlalchemy import func
        rows = (
            session.query(StockSafe.stock_status, func.count(StockSafe.id).label('cnt'))
            .group_by(StockSafe.stock_status)
            .all()
        )

    result = {}
    for row in rows:
        status = row.stock_status or '未知'
        result[status] = row.cnt
    return result


def get_abc_count() -> dict:
    """
    统计各 ABC 分类的产品数量

    Returns:
        dict: {'A': 100, 'B': 300, 'C': 100}
    """
    with orm_session() as session:
        from sqlalchemy import func
        rows = (
            session.query(StockSafe.abc_classification, func.count(StockSafe.id).label('cnt'))
            .group_by(StockSafe.abc_classification)
            .all()
        )

    result = {}
    for row in rows:
        cls = row.abc_classification or '未知'
        result[cls] = row.cnt
    return result