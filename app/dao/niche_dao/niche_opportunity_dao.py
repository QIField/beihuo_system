# -*- coding:utf-8 -*-
"""
商机表（niche_opportunity）数据访问层

职责：
1. 从 wechat_daily_quote_detail 表聚合 OE 码维度的询价统计
2. 从 crmapp_beihuo 表获取当前可用库存和在途数量
3. 批量写入商机计算结果到 niche_opportunity 表
4. 每日全量刷新：TRUNCATE 清空 + 批量插入
"""

from sqlalchemy import text
from sqlalchemy import func
from app.utils.orm.session import orm_session


def fetch_inquiry_stats(stat_date: str, company: str = 'fsbbr') -> list:
    """
    从 wechat_daily_quote_detail 表聚合 OE 码维度的询价统计

    统计口径：
    - 近30天：stat_date 往前推 30 天（含 stat_date 当天）
    - 上一个30天：再往前推 30 天，用于计算趋势
    - 只统计有 oe_code 的记录

    Args:
        stat_date: 统计日期字符串，格式 YYYY-MM-DD
        company: 公司代码（预留，当前不用于过滤）

    Returns:
        记录字典列表，每条包含：
        - oe_code, part_name（取最近一条询价记录）
        - inquiry_count_30d, inquiry_count_prev_30d, inquiry_count_7d
        - out_of_stock_count_30d, out_of_stock_rate_30d
        - customer_count_30d
        （brand_name 由 crmapp_beihuo 库存查询提供）
    """
    sql = text("""
        SELECT
            s.oe_code,
            COALESCE(l.part_name, '') AS part_name,
            COALESCE(s.inquiry_count_30d, 0) AS inquiry_count_30d,
            COALESCE(p.inquiry_count_prev_30d, 0) AS inquiry_count_prev_30d,
            COALESCE(s7.inquiry_count_7d, 0) AS inquiry_count_7d,
            COALESCE(s.out_of_stock_count_30d, 0) AS out_of_stock_count_30d,
            ROUND(COALESCE(s.out_of_stock_count_30d, 0) / NULLIF(s.inquiry_count_30d, 0), 4) AS out_of_stock_rate_30d,
            COALESCE(s.customer_count_30d, 0) AS customer_count_30d
        FROM (
            SELECT
                oe_code,
                COUNT(*) AS inquiry_count_30d,
                SUM(CASE WHEN is_out_of_stock = 1 THEN 1 ELSE 0 END) AS out_of_stock_count_30d,
                COUNT(DISTINCT NULLIF(inquiry_customer, '')) AS customer_count_30d
            FROM (
                SELECT
                    id,
                    oe_code,
                    part_name,
                    inquiry_customer,
                    is_out_of_stock,
                    CASE
                        WHEN create_date LIKE '% %' THEN STR_TO_DATE(create_date, '%Y-%m-%d %H:%i:%s')
                        ELSE STR_TO_DATE(create_date, '%Y-%m-%d')
                    END AS create_dt
                FROM wechat_daily_quote_detail
                WHERE oe_code IS NOT NULL
                  AND oe_code != ''
                  AND oe_code != '0'
            ) t
            WHERE create_dt >= DATE_SUB(:stat_date, INTERVAL 29 DAY)
              AND create_dt < DATE_ADD(:stat_date, INTERVAL 1 DAY)
            GROUP BY oe_code
        ) s
        LEFT JOIN (
            SELECT
                oe_code,
                COUNT(*) AS inquiry_count_prev_30d
            FROM (
                SELECT
                    id,
                    oe_code,
                    is_out_of_stock,
                    CASE
                        WHEN create_date LIKE '% %' THEN STR_TO_DATE(create_date, '%Y-%m-%d %H:%i:%s')
                        ELSE STR_TO_DATE(create_date, '%Y-%m-%d')
                    END AS create_dt
                FROM wechat_daily_quote_detail
                WHERE oe_code IS NOT NULL
                  AND oe_code != ''
                  AND oe_code != '0'
            ) t
            WHERE create_dt >= DATE_SUB(:stat_date, INTERVAL 59 DAY)
              AND create_dt < DATE_SUB(:stat_date, INTERVAL 29 DAY)
            GROUP BY oe_code
        ) p ON s.oe_code = p.oe_code
        LEFT JOIN (
            SELECT
                oe_code,
                COUNT(*) AS inquiry_count_7d
            FROM (
                SELECT
                    id,
                    oe_code,
                    CASE
                        WHEN create_date LIKE '% %' THEN STR_TO_DATE(create_date, '%Y-%m-%d %H:%i:%s')
                        ELSE STR_TO_DATE(create_date, '%Y-%m-%d')
                    END AS create_dt
                FROM wechat_daily_quote_detail
                WHERE oe_code IS NOT NULL
                  AND oe_code != ''
                  AND oe_code != '0'
            ) t
            WHERE create_dt >= DATE_SUB(:stat_date, INTERVAL 6 DAY)
              AND create_dt < DATE_ADD(:stat_date, INTERVAL 1 DAY)
            GROUP BY oe_code
        ) s7 ON s.oe_code = s7.oe_code
        LEFT JOIN (
            SELECT
                oe_code,
                part_name
            FROM (
                SELECT
                    oe_code,
                    part_name,
                    @rn := IF(@prev_oe = oe_code, @rn + 1, 1) AS rn,
                    @prev_oe := oe_code
                FROM (
                    SELECT
                        id,
                        oe_code,
                        part_name,
                        CASE
                            WHEN create_date LIKE '% %' THEN STR_TO_DATE(create_date, '%Y-%m-%d %H:%i:%s')
                            ELSE STR_TO_DATE(create_date, '%Y-%m-%d')
                        END AS create_dt
                    FROM wechat_daily_quote_detail
                    WHERE oe_code IS NOT NULL
                      AND oe_code != ''
                      AND oe_code != '0'
                ) t
                CROSS JOIN (SELECT @rn := 0, @prev_oe := '') AS vars
                ORDER BY oe_code, create_dt DESC, id DESC
            ) ranked
            WHERE rn = 1
        ) l ON s.oe_code = l.oe_code
        ORDER BY s.inquiry_count_30d DESC
    """)

    with orm_session() as session:
        result = session.execute(sql, {"stat_date": stat_date, "company": company}).mappings().all()
        return [dict(row) for row in result]


def fetch_search_stats(stat_date: str) -> dict:
    """
    从 oe_search_log 表聚合 OE 码维度的搜索统计（近 30 天 + 上一个 30 天）

    统计口径：
    - 近 30 天窗口：stat_date 往前推 30 天（含 stat_date 当天）
    - 上一个 30 天窗口：stat_date 往前 59 天 ~ 30 天
    - 只统计有 oe_number 的记录
    - oe_number 与 wechat_daily_quote_detail.oe_code 做大小写不敏感、去空格匹配

    Args:
        stat_date: 统计日期字符串，格式 YYYY-MM-DD

    Returns:
        dict: {
            normalized_oe_code.lower().strip(): {
                'oe_code': 原始 oe_number,
                'search_count_30d': int,
                'search_count_prev_30d': int,
            },
            ...
        }
    """
    sql = text("""
        SELECT
            TRIM(oe_number) AS oe_code,
            SUM(CASE WHEN search_date >= DATE_SUB(:stat_date, INTERVAL 29 DAY)
                      AND search_date <= :stat_date THEN 1 ELSE 0 END) AS search_count_30d,
            SUM(CASE WHEN search_date >= DATE_SUB(:stat_date, INTERVAL 59 DAY)
                      AND search_date < DATE_SUB(:stat_date, INTERVAL 29 DAY) THEN 1 ELSE 0 END) AS search_count_prev_30d
        FROM oe_search_log
        WHERE search_date >= DATE_SUB(:stat_date, INTERVAL 59 DAY)
          AND search_date <= :stat_date
          AND oe_number IS NOT NULL
          AND TRIM(oe_number) != ''
        GROUP BY TRIM(oe_number)
    """)

    with orm_session() as session:
        result = session.execute(sql, {"stat_date": stat_date}).mappings().all()
        search_map = {}
        for row in result:
            key = row['oe_code'].lower().strip()
            search_map[key] = {
                'oe_code': row['oe_code'],
                'search_count_30d': int(row.get('search_count_30d', 0) or 0),
                'search_count_prev_30d': int(row.get('search_count_prev_30d', 0) or 0),
            }
        return search_map


def fetch_inventory_map(oe_codes: list, company: str = 'fsbbr') -> dict:
    """
    批量查询 crmapp_beihuo 表的库存和在途数量

    由于 wechat_daily_quote_detail 只有 oe_code，而 crmapp_beihuo 的 OE 列可能一条记录对应多个条码，
    这里对每个 oe_code 聚合 SUM(库存数量) 和 SUM(在途数量)。

    Args:
        oe_codes: OE 码列表
        company: 公司代码，默认 'fsbbr'

    Returns:
        dict: {oe_code: {'available_stock': int, 'transit_quantity': int, 'brand_name': str}}
    """
    if not oe_codes:
        return {}

    sql = text("""
        SELECT
            oe COLLATE utf8mb4_unicode_ci AS oe_code,
            COALESCE(MAX(`品牌`), '') AS brand_name,
            COALESCE(SUM(`库存数量`), 0) AS available_stock,
            COALESCE(SUM(`在途数量`), 0) AS transit_quantity
        FROM crmapp_beihuo
        WHERE oe IN :oe_codes
          AND company = :company
          AND oe IS NOT NULL AND oe != ''
        GROUP BY oe COLLATE utf8mb4_unicode_ci
    """)

    with orm_session() as session:
        result = session.execute(sql, {"oe_codes": tuple(oe_codes), "company": company}).mappings().all()
        return {
            row['oe_code']: {
                'brand_name': row['brand_name'] or '',
                'available_stock': row['available_stock'],
                'transit_quantity': row['transit_quantity'],
            }
            for row in result
        }


def batch_insert(rows: list, batch_size: int = 2000) -> int:
    """
    批量插入商机计算结果到 niche_opportunity 表

    采用 INSERT IGNORE 策略，避免因唯一键冲突导致整批失败。
    由于每日全量刷新（先 TRUNCATE 后写入），正常情况下不会发生冲突。

    Args:
        rows: 待插入记录字典列表
        batch_size: 每批插入行数，默认 2000

    Returns:
        实际插入的总行数
    """
    if not rows:
        return 0

    sql = text("""
        INSERT IGNORE INTO niche_opportunity (
            oe_code,
            part_name,
            brand_name,
            inquiry_count_30d,
            inquiry_count_prev_30d,
            inquiry_count_7d,
            inquiry_trend_rate,
            out_of_stock_count_30d,
            out_of_stock_rate_30d,
            customer_count_30d,
            inquiry_score,
            search_score,
            out_of_stock_score,
            customer_score,
            trend_score,
            opportunity_score,
            opportunity_level,
            available_stock,
            transit_quantity,
            suggested_stock_qty,
            replenish_suggestion,
            search_count_30d,
            search_count_prev_30d,
            stat_date
        )
        VALUES (
            :oe_code,
            :part_name,
            :brand_name,
            :inquiry_count_30d,
            :inquiry_count_prev_30d,
            :inquiry_count_7d,
            :inquiry_trend_rate,
            :out_of_stock_count_30d,
            :out_of_stock_rate_30d,
            :customer_count_30d,
            :inquiry_score,
            :search_score,
            :out_of_stock_score,
            :customer_score,
            :trend_score,
            :opportunity_score,
            :opportunity_level,
            :available_stock,
            :transit_quantity,
            :suggested_stock_qty,
            :replenish_suggestion,
            :search_count_30d,
            :search_count_prev_30d,
            :stat_date
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
    清空 niche_opportunity 表（TRUNCATE TABLE，重置自增ID）

    注意：TRUNCATE 是 DDL 语句，MySQL 中隐式提交、无法事务回滚，
    调用前需确保数据已持久化。
    """
    with orm_session() as session:
        session.execute(text("TRUNCATE TABLE niche_opportunity"))
