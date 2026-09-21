# -*- coding:utf-8 -*-
"""
商机计算服务 - 每日全量刷新 niche_opportunity 表

数据流程：
  1. 从 wechat_daily_quote_detail 表聚合 OE 码维度的询价统计（近30天 + 上一个30天 + 近7天）
  2. 从 oe_search_log 表聚合 OE 码维度的搜索统计（近30天 + 上一个30天）
  3. 从 crmapp_beihuo 表获取当前可用库存和在途数量
  4. 对每个 OE 码计算商机评分、商机等级和补货建议
  5. TRUNCATE 清空 niche_opportunity 表后，批量写入新计算结果

本版说明：
  - 直接读取微信询价原始表 wechat_daily_quote_detail，不再经过统一询价中间层
  - 已融合 OE 搜索日志作为独立评分维度
  - 趋势分奖惩对称；缺货强度分引入样本置信度
  - 补货建议采用 7 天/30 天加权预测，备货系数/天数暂为全局常量
  - 不含成交率维度（deal_status 相关数据暂不可用）
"""

import time
import math
from datetime import date, timedelta
from typing import List, Dict

from app.dao.niche_dao.niche_opportunity_dao import (
    fetch_inquiry_stats,
    fetch_search_stats,
    fetch_inventory_map,
    truncate_table,
    batch_insert,
)
from app.utils.logger_config import get_task_logger

logger = get_task_logger('niche')

# =============================================================================
# 配置常量
# =============================================================================

# 商机评分权重（5 维度加权，满分 1.0）
WEIGHTS = {
    'inquiry': 0.30,        # 询价热度
    'search': 0.15,         # OE 搜索热度
    'out_of_stock': 0.25,   # 缺货强度
    'customer': 0.15,       # 客户广度
    'trend': 0.15,          # 需求趋势
}

# 商机等级阈值
LEVEL_THRESHOLDS = [
    ('S', 80),
    ('A', 60),
    ('B', 40),
    ('C', 20),
    ('D', 0),
]

# 补货建议参数
INQUIRY_CONVERSION_RATE = 0.3   # 全局询价转化系数（品类/OE 级数据不足时的 fallback）
STOCK_DAYS = 15                 # 默认备货天数（天），未来可按品类/交期覆盖
REPLENISH_STOCK_RATIO = 0.5     # 触发补货的库存阈值比例：当前库存 < 建议备货量 × 该比例
HIGH_OOS_RATE = 0.5             # 高缺货率阈值
MIN_INQUIRY_FOR_REPLENISH = 3   # 触发补货的最小询价次数

# 缺货强度分置信度参数
OOS_CONFIDENCE_THRESHOLD = 10   # 达到满信所需的询价样本量
OOS_CONFIDENCE_MIN_WEIGHT = 0.3 # 最小置信权重

# 趋势分参数
SEARCH_TO_INQUIRY_ALPHA = 0.3   # 趋势分中搜索次数相对询价次数的折算系数

# 批量插入时的每批记录数
INSERT_BATCH = 2000


# =============================================================================
# 百分位数计算函数
# =============================================================================

def _percentile(values: List[float], pct: float) -> float:
    """
    计算百分位数（线性插值法）

    Args:
        values: 数值列表
        pct: 百分位（0~1）

    Returns:
        对应百分位数值；列表为空返回 0
    """
    if not values:
        return 0.0

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])

    k = (n - 1) * pct
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])

    return float(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f))


# =============================================================================
# 评分与补货计算函数
# =============================================================================

def _calc_inquiry_score(inquiry_count: int, p80_count: float) -> float:
    """
    询价热度分：按询价次数相对 P80 位置打分
    """
    if p80_count <= 0:
        return 0.0
    return min(100.0, round(inquiry_count / p80_count * 100, 2))


def _calc_search_score(search_count: int, p80_count: float) -> float:
    """
    搜索热度分：按 OE 搜索次数相对 P80 位置打分
    """
    if p80_count <= 0:
        return 0.0
    return min(100.0, round(search_count / p80_count * 100, 2))


def _calc_out_of_stock_score(oos_rate: float, inquiry_count: int) -> float:
    """
    缺货强度分：缺货率 × 100，并按询价样本量做置信度降权

    小样本时（如 1 次询价且缺货）不被过度放大，满信阈值由
    OOS_CONFIDENCE_THRESHOLD 控制。
    """
    base_score = oos_rate * 100
    confidence = min(1.0, inquiry_count / OOS_CONFIDENCE_THRESHOLD)
    weighted_score = base_score * (OOS_CONFIDENCE_MIN_WEIGHT + (1 - OOS_CONFIDENCE_MIN_WEIGHT) * confidence)
    return round(weighted_score, 2)


def _calc_customer_score(customer_count: int, p80_count: float) -> float:
    """
    客户广度分：按询价客户数相对 P80 位置打分
    """
    if p80_count <= 0:
        return 0.0
    return min(100.0, round(customer_count / p80_count * 100, 2))


def _calc_trend_score(
    inquiry_current: int,
    inquiry_prev: int,
    search_current: int,
    search_prev: int,
) -> float:
    """
    需求趋势分：综合搜索与询价的变化，奖惩对称。

    - 综合需求指数 = 询价次数 + α * 搜索次数
    - 环比 -50% → 0 分，持平 → 50 分，+50% → 100 分
    """
    current_index = inquiry_current + SEARCH_TO_INQUIRY_ALPHA * search_current
    prev_index = inquiry_prev + SEARCH_TO_INQUIRY_ALPHA * search_prev

    if prev_index <= 0:
        return 100.0 if current_index > 0 else 0.0

    rate = (current_index - prev_index) / prev_index
    return max(0.0, min(100.0, round(50 + rate * 100, 2)))


def _calc_opportunity_level(score: float) -> str:
    """
    根据综合商机评分划分商机等级
    """
    for level, threshold in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return 'D'


def _get_conversion_rate(_oe_code: str, _brand_name: str) -> float:
    """
    获取询价转化系数。

    当前阶段无品类/OE 级历史成交数据，直接返回全局常量。
    未来可接入销售历史后，按品类/OE 动态校准。
    """
    return INQUIRY_CONVERSION_RATE


def _get_stock_days(_oe_code: str, _brand_name: str) -> int:
    """
    获取建议备货天数。

    当前阶段返回全局常量。未来可接入供应商交期、安全库存结果后按品类覆盖。
    """
    return STOCK_DAYS


def _calc_replenish_suggestion(
    oe_code: str,
    brand_name: str,
    inquiry_count_7d: int,
    inquiry_count_30d: int,
    oos_rate: float,
    opportunity_score: float,
    available_stock: int,
    transit_quantity: int,
) -> Dict[str, float]:
    """
    计算建议备货量和建议补货数量（改进版）

    需求预测：
        加权日均需求 = 0.6 * (近7天日均) + 0.4 * (近30天日均)
        建议备货量 = 加权日均需求 × 转化系数 × 备货天数

    触发条件（需同时满足）：
        1. 商机评分 >= 50 或 缺货率 >= 50%
        2. 可用库存 + 在途 < 建议备货量 × 0.5
        3. 近30天询价次数 >= 3

    Returns:
        {'suggested_stock_qty': float, 'replenish_suggestion': int}
    """
    conversion_rate = _get_conversion_rate(oe_code, brand_name)
    stock_days = _get_stock_days(oe_code, brand_name)

    forecast_daily_demand = (
        0.6 * (inquiry_count_7d / 7.0)
        + 0.4 * (inquiry_count_30d / 30.0)
    )
    suggested_stock_qty = round(forecast_daily_demand * conversion_rate * stock_days, 2)

    has_opportunity = opportunity_score >= 50 or oos_rate >= HIGH_OOS_RATE
    stock_insufficient = (available_stock + transit_quantity) < suggested_stock_qty * REPLENISH_STOCK_RATIO
    enough_inquiry = inquiry_count_30d >= MIN_INQUIRY_FOR_REPLENISH

    if has_opportunity and stock_insufficient and enough_inquiry:
        replenish = max(0, int(math.ceil(suggested_stock_qty - available_stock - transit_quantity)))
    else:
        replenish = 0

    return {
        'suggested_stock_qty': suggested_stock_qty,
        'replenish_suggestion': replenish,
    }


# =============================================================================
# 单行记录构建函数
# =============================================================================

def _build_record(
    row: dict,
    stat_date: str,
    inventory_map: dict,
    search_map: dict,
    p80_inquiry: float,
    p80_customer: float,
    p80_search: float,
) -> dict:
    """
    对单行询价统计数据计算商机评分与补货建议，构建待插入数据库的字典。

    参数说明：
      - inventory_map 的 key 需为小写 OE 码，value 包含 available_stock、
        transit_quantity、brand_name。
      - search_map 的 key 需为小写 OE 码，value 包含 search_count_30d、
        search_count_prev_30d。
    """
    oe_code = row['oe_code']
    inquiry_count_30d = int(row.get('inquiry_count_30d', 0) or 0)
    inquiry_count_prev_30d = int(row.get('inquiry_count_prev_30d', 0) or 0)
    inquiry_count_7d = int(row.get('inquiry_count_7d', 0) or 0)
    out_of_stock_count_30d = int(row.get('out_of_stock_count_30d', 0) or 0)
    out_of_stock_rate_30d = float(row.get('out_of_stock_rate_30d', 0) or 0.0)
    customer_count_30d = int(row.get('customer_count_30d', 0) or 0)

    # OE 搜索日志数据（按 oe_code 大小写不敏感匹配）
    search_stat = search_map.get(oe_code.lower().strip(), {})
    search_count_30d = int(search_stat.get('search_count_30d', 0) or 0)
    search_count_prev_30d = int(search_stat.get('search_count_prev_30d', 0) or 0)

    # 各维度评分
    inquiry_score = _calc_inquiry_score(inquiry_count_30d, p80_inquiry)
    search_score = _calc_search_score(search_count_30d, p80_search)
    out_of_stock_score = _calc_out_of_stock_score(out_of_stock_rate_30d, inquiry_count_30d)
    customer_score = _calc_customer_score(customer_count_30d, p80_customer)
    trend_score = _calc_trend_score(
        inquiry_count_30d,
        inquiry_count_prev_30d,
        search_count_30d,
        search_count_prev_30d,
    )

    # 综合商机评分
    opportunity_score = round(
        WEIGHTS['inquiry'] * inquiry_score
        + WEIGHTS['search'] * search_score
        + WEIGHTS['out_of_stock'] * out_of_stock_score
        + WEIGHTS['customer'] * customer_score
        + WEIGHTS['trend'] * trend_score,
        2,
    )

    opportunity_level = _calc_opportunity_level(opportunity_score)

    # 库存数据与品牌名称（统一使用小写 OE 查找）
    inv = inventory_map.get(oe_code.lower().strip(), {'available_stock': 0, 'transit_quantity': 0, 'brand_name': ''})
    available_stock = int(inv.get('available_stock', 0) or 0)
    transit_quantity = int(inv.get('transit_quantity', 0) or 0)
    brand_name = inv.get('brand_name') or ''

    # 补货建议
    replenish = _calc_replenish_suggestion(
        oe_code=oe_code,
        brand_name=brand_name,
        inquiry_count_7d=inquiry_count_7d,
        inquiry_count_30d=inquiry_count_30d,
        oos_rate=out_of_stock_rate_30d,
        opportunity_score=opportunity_score,
        available_stock=available_stock,
        transit_quantity=transit_quantity,
    )

    return {
        'oe_code': oe_code,
        'part_name': row.get('part_name') or '',
        'brand_name': brand_name,
        'inquiry_count_30d': inquiry_count_30d,
        'inquiry_count_prev_30d': inquiry_count_prev_30d,
        'inquiry_count_7d': inquiry_count_7d,
        'inquiry_trend_rate': round(
            ((inquiry_count_30d - inquiry_count_prev_30d) / inquiry_count_prev_30d)
            if inquiry_count_prev_30d > 0 else (1.0 if inquiry_count_30d > 0 else 0.0),
            4,
        ),
        'out_of_stock_count_30d': out_of_stock_count_30d,
        'out_of_stock_rate_30d': out_of_stock_rate_30d,
        'customer_count_30d': customer_count_30d,
        'inquiry_score': inquiry_score,
        'search_score': search_score,
        'out_of_stock_score': out_of_stock_score,
        'customer_score': customer_score,
        'trend_score': trend_score,
        'opportunity_score': opportunity_score,
        'opportunity_level': opportunity_level,
        'available_stock': available_stock,
        'transit_quantity': transit_quantity,
        'suggested_stock_qty': replenish['suggested_stock_qty'],
        'replenish_suggestion': replenish['replenish_suggestion'],
        'search_count_30d': search_count_30d,
        'search_count_prev_30d': search_count_prev_30d,
        'stat_date': stat_date,
    }


# =============================================================================
# 主入口函数
# =============================================================================

def run_compute(stat_date: str = None) -> dict:  # pyright: ignore[reportArgumentType]
    """
    商机每日全量刷新主入口函数。

    执行流程：
      第 1 步：从 wechat_daily_quote_detail 聚合近30天/上一个30天/近7天询价数据
      第 2 步：从 oe_search_log 聚合 OE 搜索日志统计
      第 3 步：批量查询 crmapp_beihuo 库存数据
      第 4 步：计算 P80 分位数（询价/客户/搜索）
      第 5 步：计算商机评分、商机等级、补货建议
      第 6 步：TRUNCATE 清空 niche_opportunity 表后批量写入新计算结果

    Args:
        stat_date: 统计日期字符串，格式 YYYY-MM-DD；为空则取昨天

    Returns:
        dict: 执行结果摘要
    """
    if stat_date is None:
        stat_date = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')

    start = time.time()
    logger.info("[开始] niche_opportunity 商机计算任务启动，统计日期: %s", stat_date)

    try:
        # ====== 阶段 1：读取询价统计 ======
        # 直接读取 wechat_daily_quote_detail，按 OE 码维度聚合近 60 天数据
        rows = fetch_inquiry_stats(stat_date)
        logger.info("[阶段1] 询价聚合完成: %d 个 oe_code", len(rows))

        if not rows:
            return {
                "status": "completed",
                "total_count": 0,
                "inserted_count": 0,
                "total_elapsed_time": round(time.time() - start, 2),
                "timestamp": int(time.time()),
            }

        # ====== 阶段 2：读取 OE 搜索日志统计 ======
        search_map = fetch_search_stats(stat_date)
        logger.info("[阶段2] OE 搜索日志聚合完成: %d 个 oe_code", len(search_map))

        # ====== 阶段 3：读取库存数据 ======
        oe_codes = [r['oe_code'] for r in rows]
        inventory_map = fetch_inventory_map(oe_codes)
        # 库存 OE 与询价 OE 可能存在大小写差异，统一转小写做 lookup key
        inventory_map_lower = {
            k.lower().strip(): v for k, v in inventory_map.items()
        }
        logger.info("[阶段3] 库存查询完成: %d 个 oe_code 有库存数据", len(inventory_map))

        # ====== 阶段 4：计算 P80 分位数 ======
        inquiry_counts = [float(r.get('inquiry_count_30d', 0) or 0) for r in rows]
        customer_counts = [float(r.get('customer_count_30d', 0) or 0) for r in rows]
        search_counts = [
            float(search_map.get(r['oe_code'].lower().strip(), {}).get('search_count_30d', 0) or 0)
            for r in rows
        ]
        p80_inquiry = _percentile(inquiry_counts, 0.8)
        p80_customer = _percentile(customer_counts, 0.8)
        p80_search = _percentile(search_counts, 0.8)
        logger.info(
            "[阶段4] P80 分位数: inquiry=%.2f, customer=%.2f, search=%.2f",
            p80_inquiry, p80_customer, p80_search,
        )

        # ====== 阶段 5：逐行计算 ======
        records = [
            _build_record(r, stat_date, inventory_map_lower, search_map, p80_inquiry, p80_customer, p80_search)
            for r in rows
        ]
        logger.info("[阶段5] 商机计算完成: %d 条", len(records))

        # ====== 阶段 6：写入数据库 ======
        truncate_table()
        inserted = batch_insert(records, batch_size=INSERT_BATCH)

        elapsed = round(time.time() - start, 2)
        logger.info("[完成] 写入 %d 行, 耗时 %.2fs", inserted, elapsed)

        return {
            "status": "completed",
            "total_count": len(records),
            "inserted_count": inserted,
            "total_elapsed_time": elapsed,
            "timestamp": int(time.time()),
        }

    except Exception:
        logger.error("[失败] niche_opportunity 计算异常", exc_info=True)
        raise

# if __name__ == "__main__":
#     run_compute()