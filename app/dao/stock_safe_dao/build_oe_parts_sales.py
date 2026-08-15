# -*- coding:utf-8 -*-
# @Time    : 2026/08/06
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : build_oe_parts_sales.py
# @Software: trae-cn

"""
OE零件销量表（oe_parts_sales）构建 - 数据访问层（DAO）

职责（对应 doc/安全库存文档整理/10_销量表生成流程.md）：
1. 聚合抽取：将 sales_order_history 无退货常规订单（order_type_id=1，且
   orders_items_id 不在 stock_safe_refund_ref 的退货关联中）与
   stock_safe_refund_ref type=21/22 部分退货净额（最新 match_count）UNION ALL 后，
   在数据库端按 (number, brand_name) GROUP BY 聚合，直接输出年/月维度销量。
   DB 端聚合只返回聚合结果（SKU 维度，远小于明细行数），降低内存与网络消耗。
2. 全量写入支持：TRUNCATE 清空 + 批量插入（executemany），保证写入完整性。

字段说明（与 sales_order_history 同名同义，无字段映射层）：
- number: OE号 | pdname: 产品名称 | frey_no: 条码 | brand_name: 品牌名
- 净销量取值：第一部分 quantity，第二部分 processed_quantity
- 时间维度统一取常规订单 create_date（秒级时间戳）
"""


from sqlalchemy import text, bindparam
from app.utils.orm.session import orm_session
from datetime import datetime, timedelta

# 参与退货排除的 type 集合：常规订单一旦存在这些类型关联即被排除
# （完全退货 11/12/13、部分退货 21/22/23、退货超出 31/32/33）
REFUND_EXCLUDE_TYPES = (11, 12, 13, 21, 22, 23, 31, 32, 33)
# 部分退货净额类型：常规订单有剩余（processed_quantity > 0）
REFUND_RESIDUAL_TYPES = (21, 22)


def fetch_aggregated_sales(stat_date_ts: int, stat_year: int,
                           one_year_ago_ts: int, months: list,
                           weekly_ranges: list) -> list:
    """
    数据库聚合查询：按 (number, brand_name) 聚合净销量，输出年/月/周维度统计

    将原 sales_order_history 无退货常规订单（order_type_id=1）与
    stock_safe_refund_ref type=21/22 退货净额 UNION ALL 后 GROUP BY 聚合，
    在数据库端完成年/月/周销量 SUM(CASE WHEN)，只返回聚合结果（SKU 维度），
    显著降低传输行数与 Python 内存消耗。

    新增周维度统计（方案一：真实周标准差）：
    - 52 周销量列（week_1~week_52），按自定义周范围（7天/周）聚合
    - 用于服务层计算真实周销量标准差 σ_w，替代原月度标准差

    数据质量过滤（原服务层 _merge_row 逻辑下推至 SQL）：
    - OE号/品牌名非空、净销量 > 0
    - create_date BETWEEN one_year_ago_ts AND stat_date_ts（近一年时间窗口 + 过滤未来日期与非法超大时间戳）
    - FROM_UNIXTIME 对非法时间戳返回 NULL，CASE 自动归 0（等价原"跳过非法时间戳"）

    Args:
        stat_date_ts: 统计日期当天结束的秒级时间戳（过滤未来数据上界）
        stat_year: 统计日期的年份（用于今年/去年 SUM 判定）
        one_year_ago_ts: 近一年窗口起点的秒级时间戳（当天 0 点）
        months: 近12个月键列表 ['YYYY-MM', ...]（12个，从旧到新，对应 month_1~month_12）
        weekly_ranges: 52周时间范围列表 [(start_ts, end_ts), ...]（从旧到新）

    Returns:
        聚合记录字典列表，每条包含：
            number, brand_name, pdname, frey_no,
            annual_sales_1y, sales_this_year, sales_last_year,
            month_1 ~ month_12（按 months 顺序的各月净销量）
            week_1 ~ week_52（当提供 weekly_ranges 时，按周范围聚合的各周净销量）
    """
    # 动态拼装 12 个月度列的 SUM(CASE WHEN ...) 表达式
    month_exprs = ",\n            ".join(
        f"SUM(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(t.create_date), '%Y-%m') = :m{i} "
        f"THEN t.net_qty ELSE 0 END) AS month_{i}"
        for i in range(1, 13)
    )

    # 如果提供了 weekly_ranges，动态拼装 52 个周度列的 SUM(CASE WHEN ...) 表达式
    week_exprs = ""
    if weekly_ranges:
        week_exprs = ",\n            " + ",\n            ".join(
            f"SUM(CASE WHEN t.create_date BETWEEN :ws{i} AND :we{i} "
            f"THEN t.net_qty ELSE 0 END) AS week_{i}"
            for i in range(1, 53)
        )

    sql = text(f"""
        SELECT
            t.number,
            t.brand_name,
            MAX(t.pdname) AS pdname,
            MAX(t.frey_no) AS frey_no,
            SUM(CASE WHEN t.create_date BETWEEN :one_year_ago_ts AND :stat_date_ts
                     THEN t.net_qty ELSE 0 END) AS annual_sales_1y,
            SUM(CASE WHEN YEAR(FROM_UNIXTIME(t.create_date)) = :stat_year
                     THEN t.net_qty ELSE 0 END) AS sales_this_year,
            SUM(CASE WHEN YEAR(FROM_UNIXTIME(t.create_date)) = :stat_year - 1
                     THEN t.net_qty ELSE 0 END) AS sales_last_year,
            {month_exprs}
            {week_exprs}
        FROM (
            -- 第一部分：无退货常规订单（order_type_id=1，净销量取 quantity）
            SELECT s.number, s.brand_name, s.pdname, s.frey_no,
                   s.quantity AS net_qty, s.create_date
            FROM sales_order_history s
            WHERE s.order_type_id = 1
              AND s.number IS NOT NULL AND s.number != ''
              AND s.brand_name IS NOT NULL AND s.brand_name != ''
              AND s.quantity > 0
              AND s.create_date BETWEEN :one_year_ago_ts AND :stat_date_ts
              AND NOT EXISTS (
                  SELECT 1 FROM stock_safe_refund_ref r
                  WHERE r.normal_order_items_id = s.orders_items_id
                    AND r.type IN :exclude_types
              )
            UNION ALL
            -- 第二部分：部分退货净额（type=21/22 最新 match_count，净销量取 processed_quantity）
            SELECT r.number, r.brand_name, r.pdname, r.frey_no,
                   r.processed_quantity AS net_qty, h.create_date
            FROM stock_safe_refund_ref r
            JOIN sales_order_history h ON h.orders_items_id = r.normal_order_items_id
            WHERE r.type IN :residual_types
              AND r.processed_quantity > 0
              AND r.number IS NOT NULL AND r.number != ''
              AND r.brand_name IS NOT NULL AND r.brand_name != ''
              AND h.create_date BETWEEN :one_year_ago_ts AND :stat_date_ts
              AND r.match_count = (
                  SELECT MAX(match_count)
                  FROM stock_safe_refund_ref r2
                  WHERE r2.normal_order_items_id = r.normal_order_items_id
              )
        ) t
        GROUP BY t.number, t.brand_name
    """).bindparams(
        bindparam("exclude_types", expanding=True),
        bindparam("residual_types", expanding=True),
    )

    # 组装查询参数：时间窗口 + 年份 + 退货类型 + 12 个月键
    params = {
        "stat_date_ts": stat_date_ts,
        "stat_year": stat_year,
        "one_year_ago_ts": one_year_ago_ts,
        "exclude_types": REFUND_EXCLUDE_TYPES,
        "residual_types": REFUND_RESIDUAL_TYPES,
    }
    for i, m in enumerate(months, 1):
        params[f"m{i}"] = m
    # 如果提供了 weekly_ranges，添加52周时间戳参数
    if weekly_ranges:
        for i, (ws, we) in enumerate(weekly_ranges, 1):
            params[f"ws{i}"] = ws
            params[f"we{i}"] = we

    with orm_session() as session:
        result = session.execute(sql, params).mappings().all()
        return [dict(row) for row in result]




def batch_insert(rows: list, batch_size: int = 2000) -> int:
    """
    批量插入销量统计记录到 oe_parts_sales（executemany）

    Args:
        rows: 待插入记录字典列表，每个元素需包含：
            number, brand_name, pdname, frey_no,
            avg_daily_sales_1y, avg_monthly_sales_1y, annual_sales_1y,
            sales_this_year, sales_last_year, sales_std_dev_1y,
            monthly_sales_json（JSON字符串）, weekly_sales_json（JSON字符串）, stat_date
        batch_size: 每批插入行数，默认 2000

    Returns:
        实际插入的总行数
    """
    # 空列表直接返回0，避免空 executemany
    if not rows:
        return 0

    # 构建批量INSERT SQL（参数由服务层预构造，直接 executemany）
    # 注意：created_at / updated_at 走数据库默认值，不写入
    sql = text("""
        INSERT INTO oe_parts_sales (
            number,
            brand_name,
            pdname,
            frey_no,
            avg_daily_sales_1y,
            avg_monthly_sales_1y,
            annual_sales_1y,
            sales_this_year,
            sales_last_year,
            sales_std_dev_1y,
            monthly_sales_json,
            weekly_sales_json,
            stat_date
        )
        VALUES (
            :number,
            :brand_name,
            :pdname,
            :frey_no,
            :avg_daily_sales_1y,
            :avg_monthly_sales_1y,
            :annual_sales_1y,
            :sales_this_year,
            :sales_last_year,
            :sales_std_dev_1y,
            :monthly_sales_json,
            :weekly_sales_json,
            :stat_date
        )
    """)

    total = 0
    # 分片批量插入，控制单条 SQL 长度
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        with orm_session() as session:
            result = session.execute(sql, chunk)
            total += result.rowcount  # pyright: ignore[reportAttributeAccessIssue]
    return total





def truncate_table() -> None:
    """
    清空 oe_parts_sales 表（TRUNCATE TABLE，重置自增ID）

    注意：TRUNCATE 是 DDL 语句，MySQL 中隐式提交、无法事务回滚，
    调用前需确保数据已持久化。
    """
    with orm_session() as session:
        session.execute(text("TRUNCATE TABLE oe_parts_sales"))