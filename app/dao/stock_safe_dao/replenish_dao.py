# -*- coding:utf-8 -*-
# @Time    : 2026/09/09
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : replenish_dao.py
# @Software: trae-cn

"""
安全库存补货清单数据访问层（DAO）

职责：
    从 stock_safe 表查询满足补货条件（固定筛选）的记录，供补货 Excel 导出服务使用。

筛选规则（固定）：
    - 销售状态：销量低、销量正常
    - 库存状态：建议补货、可根据情况补货、需补货、紧急补货

说明：
    - 不过滤废弃数据（stock_safe_useless_data），即不含数据范围筛选。
    - 本 DAO 不自行开启事务/会话，由业务层通过 orm_session() 传入，保证整条
      业务链路在同一个事务内执行，维持原子性与一致性。
"""

from sqlalchemy import case

# 补货清单固定的筛选条件（与业务规则保持一致，集中定义便于维护）
SALES_STATUS_LIST = ['销量低', '销量正常']
STOCK_STATUS_LIST = ['建议补货', '可根据情况补货', '需补货', '紧急补货']


def fetch_replenish_data(session) -> list:
    """
    查询需要补货的安全库存记录并转为字典列表

    使用业务层传入的 session 查询（不在本 DAO 开启事务），会话由调用方管理，
    以保持整条业务链路的原子性。

    排序：库存状态按 紧急补货 > 需补货 > 建议补货 > 可根据情况补货 的紧急程度，
    再按可用库存升序。

    Args:
        session: 由业务层开启的数据库会话（orm_session 上下文内的 session）

    Returns:
        list[dict]: 符合补货条件的记录列表（每项为 StockSafe.to_dict()）
    """
    from app.models.orm_models.stock_safe_models.stock_safe import StockSafe

    query = (
        session.query(StockSafe)
        .filter(
            StockSafe.sales_status.in_(SALES_STATUS_LIST),
            StockSafe.stock_status.in_(STOCK_STATUS_LIST),
        )
        .order_by(
            case(
                (StockSafe.stock_status == '紧急补货', 1),
                (StockSafe.stock_status == '需补货', 2),
                (StockSafe.stock_status == '建议补货', 3),
                (StockSafe.stock_status == '可根据情况补货', 4),
                else_=5,
            ),
            StockSafe.available_stock.asc(),
        )
    )
    rows = query.all()
    return [row.to_dict() for row in rows]