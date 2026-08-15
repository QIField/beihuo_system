# -*- coding:utf-8 -*-
# @Time    : 2026/08/08
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_dao.py
# @Software: trae-cn

"""
安全库存表（stock_safe）数据访问层（DAO）

职责：
1. 读取 oe_parts_sales 销量统计结果，作为安全库存计算的基础输入
2. 从 crmapp_beihuo 表获取可用库存，使用 (number, brand_name, frey_no) 三字段匹配
3. 批量写入安全库存计算结果到 stock_safe 表
4. 每日全量刷新：TRUNCATE 清空 + 批量插入

数据流：
    oe_parts_sales (销量数据)  ──→  stock_safe 计算
    crmapp_beihuo (库存数据)   ──→  available_stock（三字段匹配）
"""

from sqlalchemy import text
from app.utils.orm.session import orm_session


def fetch_sales_with_inventory(company: str = 'fsbbr') -> list:
    """
    从 oe_parts_sales 和 crmapp_beihuo 读取并集数据，获取销量及可用库存

    使用 UNION 实现 FULL OUTER JOIN 效果，同时保留以下两种情况：
    1. oe_parts_sales 中存在但 crmapp_beihuo 中无匹配的产品（available_stock 为 0）
    2. crmapp_beihuo 中有库存但 oe_parts_sales 中无销售记录的产品（销量字段为 0/NULL）

    三字段匹配关系：
    - oe_parts_sales.number = crmapp_beihuo.oe
    - oe_parts_sales.brand_name = crmapp_beihuo.品牌
    - oe_parts_sales.frey_no = crmapp_beihuo.物料条码

    crmapp_beihuo 按 company 过滤，保证数据的组织隔离性。

    Args:
        company: 组织代码，默认 'fsbbr'

    Returns:
        记录字典列表，每条包含：
        - number, brand_name, frey_no, pdname（产品标识）
        - avg_daily_sales_1y, sales_std_dev_1y, annual_sales_1y（销量统计）
        - monthly_sales_json（月度销量JSON，用于季节系数计算）
        - cost_price（成本价，来自crmapp_beihuo.成本价，无匹配则为0）
        - available_stock（可用库存，来自crmapp_beihuo，无匹配则为0）
    """
    sql = text("""
        -- 第一部分：oe_parts_sales 的全部记录（LEFT JOIN 保留左表全部行）
        SELECT
            s.number,
            s.brand_name,
            s.frey_no,
            s.pdname,
            s.avg_daily_sales_1y,
            s.sales_std_dev_1y,
            s.annual_sales_1y,
            s.monthly_sales_json,
            COALESCE(b.成本价, 0) AS cost_price,
            COALESCE(b.库存数量, 0) AS available_stock
        FROM oe_parts_sales s
        LEFT JOIN crmapp_beihuo b
            ON s.number = b.oe COLLATE utf8mb4_unicode_ci
            AND s.brand_name = b.品牌 COLLATE utf8mb4_unicode_ci
            AND s.frey_no = b.物料条码 COLLATE utf8mb4_unicode_ci
            AND b.company = :company

        UNION

        -- 第二部分：crmapp_beihuo 中有库存但 oe_parts_sales 中无销售记录的产品
        SELECT
            b.oe COLLATE utf8mb4_unicode_ci AS number,
            b.品牌 COLLATE utf8mb4_unicode_ci AS brand_name,
            b.物料条码 COLLATE utf8mb4_unicode_ci AS frey_no,
            b.物料名称 COLLATE utf8mb4_unicode_ci AS pdname,
            0 AS avg_daily_sales_1y,
            0 AS sales_std_dev_1y,
            0 AS annual_sales_1y,
            NULL AS monthly_sales_json,
            COALESCE(b.成本价, 0) AS cost_price,
            COALESCE(b.库存数量, 0) AS available_stock
        FROM crmapp_beihuo b
        LEFT JOIN oe_parts_sales s
            ON s.number = b.oe COLLATE utf8mb4_unicode_ci
            AND s.brand_name = b.品牌 COLLATE utf8mb4_unicode_ci
            AND s.frey_no = b.物料条码 COLLATE utf8mb4_unicode_ci
        WHERE s.number IS NULL
          AND b.company = :company
    """)

    with orm_session() as session:
        result = session.execute(sql, {"company": company}).mappings().all()
        return [dict(row) for row in result]


def batch_insert(rows: list, batch_size: int = 2000) -> int:
    """
    批量插入安全库存计算结果到 stock_safe 表（executemany）

    采用 INSERT IGNORE 策略，避免因唯一键冲突导致整批失败。
    由于每日全量刷新（先 TRUNCATE 后写入），正常情况下不会发生冲突。
    created_at / updated_at 走数据库默认值，不显式写入。

    Args:
        rows: 待插入记录字典列表，每个元素需包含：
            number, brand_name, frey_no, pdname,
            abc_classification, avg_daily_sales,
            base_safety_stock, season_coefficient, safety_stock,
            stock_lower_limit, stock_upper_limit,
            available_stock, sellable_days,
            stock_status
        batch_size: 每批插入行数，默认 2000

    Returns:
        实际插入的总行数
    """
    if not rows:
        return 0

    sql = text("""
        INSERT IGNORE INTO stock_safe (
            number,
            brand_name,
            frey_no,
            pdname,
            abc_classification,
            avg_daily_sales,
            base_safety_stock,
            season_coefficient,
            safety_stock,
            stock_lower_limit,
            stock_upper_limit,
            available_stock,
            sellable_days,
            stock_status
        )
        VALUES (
            :number,
            :brand_name,
            :frey_no,
            :pdname,
            :abc_classification,
            :avg_daily_sales,
            :base_safety_stock,
            :season_coefficient,
            :safety_stock,
            :stock_lower_limit,
            :stock_upper_limit,
            :available_stock,
            :sellable_days,
            :stock_status
        )
    """)

    total = 0
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        with orm_session() as session:
            result = session.execute(sql, chunk)
            total += result.rowcount  # pyright: ignore[reportAttributeAccessIssue]
    return total


def truncate_table() -> None:
    """
    清空 stock_safe 表（TRUNCATE TABLE，重置自增ID）

    注意：TRUNCATE 是 DDL 语句，MySQL 中隐式提交、无法事务回滚，
    调用前需确保数据已持久化。
    """
    with orm_session() as session:
        session.execute(text("TRUNCATE TABLE stock_safe"))


