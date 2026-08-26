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

from sqlalchemy import or_, case, asc, desc, func, select
from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger
from app.models.orm_models.stock_safe_models.stock_safe import StockSafe
from app.models.orm_models.stock_safe_models.stock_safe_useless_data import StockSafeUselessData

logger = get_task_logger('stock_safe')


def get_stock_safe_list(
    keyword: str = '',
    stock_status: str = '',
    sales_status: str = '',
    abc_classification: str = '',
    data_type: str = 'useful',
    page: int = 1,
    limit: int = 50,
    sort_field: str = '',
    sort_order: str = 'asc',
) -> dict:
    """
    分页查询安全库存列表（服务端排序 + 分页）

    支持关键词搜索（number / brand_name / pdname / frey_no）、
    库存状态筛选、销售状态筛选、ABC 分类筛选，以及任意字段排序。

    数据范围筛选（data_type，默认 'useful'）：
        all:     全部数据（不做废弃过滤）
        useful:  有用数据（排除 stock_safe_useless_data 表中存在的 frey_no）
        useless: 废弃数据（仅返回 stock_safe_useless_data 表中存在的 frey_no）

    Args:
        keyword: 搜索关键词（匹配 OE号/品牌/产品名称/条码）
        stock_status: 库存状态编码（1=呆滞清库/2=慢动销去库/3=紧急补货/4=需补货/5=库存正常）
        sales_status: 销售状态（无销售/销量极低/销量低/销量正常）
        abc_classification: ABC 分类筛选（A/B/C）
        data_type: 数据范围：all / useful / useless，默认 useful
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
    # 数据范围参数校验（非法值回退到默认 useful）
    if data_type not in ('all', 'useful', 'useless'):
        data_type = 'useful'

    with orm_session() as session:
        # 构建基础查询
        query = session.query(StockSafe)

        # ---- 数据范围筛选（按 frey_no 匹配 stock_safe_useless_data 表） ----
        # 废弃数据仅按 frey_no 记录在废弃表中，stock_safe 原数据保留未删除，
        # 此处通过 frey_no 的 IN / NOT IN 来区分 有用 / 废弃 / 全部。
        if data_type != 'all':
            useless_freys = select(StockSafeUselessData.frey_no)
            if data_type == 'useless':
                # 仅返回已废弃的记录
                query = query.filter(StockSafe.frey_no.in_(useless_freys))
            else:  # useful：排除已废弃记录
                query = query.filter(~StockSafe.frey_no.in_(useless_freys))

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

        # ---- 库存状态筛选（直接匹配 stock_status 字段） ----
        if stock_status:
            query = query.filter(StockSafe.stock_status == stock_status)

        # ---- 销售状态筛选（直接匹配 sales_status 字段） ----
        if sales_status:
            query = query.filter(StockSafe.sales_status == sales_status)

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
    统计各库存维度的产品数量（用于前端卡片展示）

    销售状态和库存状态分别存储在独立的 sales_status 和 stock_status 字段中，
    本函数分别按字段分组统计。

    Returns:
        dict: { '呆滞清库': 10, '慢动销去库': 5, '库存积压': 3, '紧急补货': 8, '需补货': 20,
                '需补货|可卖天数较少': 6, '库存正常': 100, '无销售': 5, '销量极低': 10, '销量低': 3, '销量正常': 50 }
    """
    # 所有可能的标签列表
    sales_labels = ['无销售', '销量极低', '销量低', '销量正常']
    stock_labels = ['呆滞清库', '慢动销去库', '库存积压', '需补货', '需补货|可卖天数较少', '紧急补货', '库存正常']

    with orm_session() as session:
        # 按销售状态分组统计
        sales_rows = (
            session.query(StockSafe.sales_status, func.count(StockSafe.id).label('cnt'))
            .group_by(StockSafe.sales_status)
            .all()
        )
        # 按库存状态分组统计
        stock_rows = (
            session.query(StockSafe.stock_status, func.count(StockSafe.id).label('cnt'))
            .group_by(StockSafe.stock_status)
            .all()
        )

    # 初始化结果字典
    result = {}
    for label in sales_labels:
        result[label] = 0
    for label in stock_labels:
        result[label] = 0

    # 销售维度统计（数据库值直接是中文标签）
    for row in sales_rows:
        label = row.sales_status or ''
        if label in result:
            result[label] += row.cnt

    # 库存维度统计（数据库值直接是中文标签）
    for row in stock_rows:
        label = row.stock_status or ''
        if label in result:
            result[label] += row.cnt

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