# -*- coding:utf-8 -*-
# @Time    : 2026/08/06
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : build_oe_parts_sales_service.py
# @Software: trae-cn

"""
OE零件销量表（oe_parts_sales）构建 - 服务层

每日全量刷新主入口 run_sync() 流程：
1. DAO 数据库聚合：UNION ALL + GROUP BY + SUM CASE，输出 SKU 维度年/月/周销量
2. pandas 向量化派生：日均/月均销量、周标准差 σ_w、月度/周度 JSON
3. TRUNCATE 清空 + 批量写入

调度建议（LightweightTaskManager，每日 03:00）：
    from app.core.task_manager import task_manager
    task_manager.schedule(run_sync, 'cron', 'oe_parts_sales_daily_refresh',
                          hour=3, minute=0, replace_existing=True)
"""

import json
import time
from datetime import date, datetime, timedelta

import pandas as pd
import numpy as np

from app.dao.stock_safe_dao.build_oe_parts_sales import (
    fetch_aggregated_sales,
    truncate_table,
    batch_insert,
)
from app.scripts.spiders.spiders_services.log import get_stock_safe_logger

logger = get_stock_safe_logger()

# 每批插入行数，控制 executemany 分批大小
INSERT_BATCH_SIZE = 2000

# 12 个月度列名（与 DAO 聚合输出 month_1~month_12 对应）
MONTH_COLUMNS = [f"month_{i}" for i in range(1, 13)]

# 52 个周度列名（与 DAO 聚合输出 week_1~week_52 对应）
WEEK_COLUMNS = [f"week_{i}" for i in range(1, 53)]


def _last_12_months(stat_date: date) -> list:
    """
    生成12个完整自然月键列表（含 stat_date 所在月份，从旧到新）。

    算法：从 stat_date 的 (year, month) 开始倒推 12 个月，跨年时年份减 1，
    最后 reverse 得到从旧到新排列。

    Args:
        stat_date: 统计日期（上月最后一天）

    Returns:
        长度为12的字符串列表，格式 "YYYY-MM"，从旧到新排列
    """
    # 初始化空列表，用于收集 12 个月份键
    months = []
    # 从统计日期的年份和月份开始向前倒推
    year, month = stat_date.year, stat_date.month
    # 循环 12 次，每次收集前一个月
    for _ in range(12):
        # 将当前 (year, month) 格式化为 "YYYY-MM" 字符串并追加到列表
        months.append(f"{year:04d}-{month:02d}")
        # 月份减 1，向前倒推一个月
        month -= 1
        # 如果月份减到 0，说明跨上一年：月份重置为 12，年份减 1
        if month == 0:
            month, year = 12, year - 1
    # 当前列表是从新到旧（如 2026-08, 2026-07, ...），reverse 后变为从旧到新
    months.reverse()  # 从旧到新排列
    return months


def _last_52_weeks(stat_date_ts: int) -> list:
    """
    生成52个周范围，从 stat_date_ts 向前推52周（每周7天）。

    周范围按从旧到新排列，与 DAO 输出的 week_1~week_52 一一对应。
    每个元素为 (start_ts, end_ts, label)，label 为周起始日期 "YYYY-MM-DD"。

    示例（stat_date_ts=2026-07-31 23:59:59）：
        week_1  (最旧): [2025-08-02 00:00:00, 2025-08-08 23:59:59]
        week_52 (最新): [2026-07-25 00:00:00, 2026-07-31 23:59:59]

    Args:
        stat_date_ts: 统计日期结束的秒级时间戳

    Returns:
        长度为52的列表，按从旧到新排列，每个元素为 (start_ts, end_ts, label)
    """
    DAY_SECONDS = 86400
    ranges = []
    for i in range(52):
        # i=0 -> week_1 (最旧), i=51 -> week_52 (最新)
        week_end = stat_date_ts - (51 - i) * 7 * DAY_SECONDS
        week_start = week_end - 6 * DAY_SECONDS
        # label: 周起始日期字符串，用于 weekly_sales_json 键名
        label = datetime.fromtimestamp(week_start).strftime("%Y-%m-%d")
        ranges.append((week_start, week_end, label))
    return ranges


def _derive_fields(rows: list, stat_date: date, months: list,
                   actual_days: int, weekly_labels: list) -> list:
    """
    基于 DAO 聚合结果，用 pandas 向量化派生统计字段。

    派生字段：
    - avg_daily_sales_1y: annual_sales_1y / 实际天数
    - avg_monthly_sales_1y: annual_sales_1y / 12
    - sales_std_dev_1y: 近52周周销量总体标准差 σ_w（ddof=0）
    - monthly_sales_json: {"YYYY-MM": 数量}
    - weekly_sales_json: {"YYYY-MM-DD": 数量}

    使用 pandas 向量化替代逐行循环，由 C 扩展完成批量运算。

    Args:
        rows: DAO 聚合记录列表
        stat_date: 统计日期
        months: 12个完整自然月键列表
        actual_days: 12个完整自然月的实际天数
        weekly_labels: 52个周起始日期标签列表

    Returns:
        待插入 oe_parts_sales 的记录列表
    """
    if not rows:
        return []

    # 将 DAO 返回的记录列表转为 pandas DataFrame，每行是一个 SKU（number, brand_name 组合）
    # DataFrame 列名与 DAO 返回的字典键一致，可直接按列名访问
    df = pd.DataFrame(rows)

    # 从 DataFrame 中提取 12 个月度净销量列，转换为 numpy 二维数组（N行×12列）
    # dtype=float 确保数值类型适合标准差计算，避免整数除法问题
    month_matrix = df[MONTH_COLUMNS].to_numpy(dtype=float)
    annual = df["annual_sales_1y"].to_numpy(dtype=float)

    # 日均/月均销量
    df["avg_daily_sales_1y"] = np.round(annual / actual_days, 2)
    df["avg_monthly_sales_1y"] = np.round(annual / 12, 2)

    # 周标准差 σ_w（方案一：真实周标准差，用于 SS = Z × σ_w × √(L/7)）
    week_matrix = df[WEEK_COLUMNS].to_numpy(dtype=float)
    df["sales_std_dev_1y"] = np.round(np.std(week_matrix, axis=1, ddof=0), 2)

    # 周度 JSON
    df["weekly_sales_json"] = [
        json.dumps({lbl: int(v) for lbl, v in zip(weekly_labels, vals)}, ensure_ascii=False)
        for vals in week_matrix
    ]

    # 月度 JSON（保留用于季节系数计算）
    df["monthly_sales_json"] = [
        json.dumps({m: int(v) for m, v in zip(months, vals)}, ensure_ascii=False)
        for vals in month_matrix
    ]

    df["stat_date"] = stat_date.strftime("%Y-%m-%d")

    # 删除中间计算列，只保留待插入字段
    columns_to_drop = list(MONTH_COLUMNS) + list(WEEK_COLUMNS)
    return df.drop(columns=columns_to_drop).to_dict("records")


def run_sync() -> dict:
    """
    销量表（oe_parts_sales）每日全量刷新主入口。

    执行流程：
    1. 阶段1：DAO 聚合查询，DB 端完成 UNION ALL + GROUP BY + SUM CASE
    2. 阶段2：pandas 向量化派生统计字段
    3. 阶段3：TRUNCATE 清空 + 批量写入

    Returns:
        同步结果字典：{status, aggregate_count, inserted_count, total_elapsed_time, timestamp}
    """
    start_time = time.time()
    logger.info("[开始] oe_parts_sales 每日刷新任务启动")

    # 参数计算：完整自然月对齐方案，统计日期 = 上月最后一天
    today = date.today()
    stat_date = date(today.year, today.month, 1) - timedelta(days=1)
    stat_date_ts = int(datetime.combine(stat_date, datetime.max.time()).timestamp())

    # 12个月前的第一天 0 点
    year, month = stat_date.year, stat_date.month + 1 - 12
    if month <= 0:
        month += 12
        year -= 1
    one_year_start = date(year, month, 1)
    one_year_ago_ts = int(datetime.combine(one_year_start, datetime.min.time()).timestamp())
    actual_days = (stat_date - one_year_start).days + 1
    months = _last_12_months(stat_date)

    # 52周范围计算
    weekly_tuples = _last_52_weeks(stat_date_ts)
    weekly_ranges = [(ws, we) for ws, we, _ in weekly_tuples]
    weekly_labels = [label for _, _, label in weekly_tuples]

    try:
        # 阶段1：DAO 数据库聚合
        rows = fetch_aggregated_sales(stat_date_ts, stat_date.year, one_year_ago_ts,
                                      months, weekly_ranges=weekly_ranges)
        logger.info("[阶段1] DB 聚合完成: %d 个 (number, brand_name) 组合", len(rows))

        # 阶段2：pandas 向量化派生
        records = _derive_fields(rows, stat_date, months, actual_days, weekly_labels=weekly_labels)
        logger.info("[阶段2] 派生完成: %d 条记录", len(records))

        # 阶段3：TRUNCATE + 批量写入
        truncate_table()
        inserted = batch_insert(records, batch_size=INSERT_BATCH_SIZE)
        logger.info("[阶段3] 批量写入完成: %d 行", inserted)

        elapsed = round(time.time() - start_time, 2)
        logger.info("[完成] 刷新完成: 写入 %d 行, 耗时 %.2fs", inserted, elapsed)
        return {"status": "completed", "aggregate_count": len(rows),
                "inserted_count": inserted,
                "total_elapsed_time": elapsed, "timestamp": int(time.time())}

    except Exception as e:
        logger.error("[失败] oe_parts_sales 刷新异常: %s", e, exc_info=True)
        raise


# if __name__ == "__main__":
#     run_sync()