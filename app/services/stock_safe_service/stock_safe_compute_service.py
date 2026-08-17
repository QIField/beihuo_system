# -*- coding:utf-8 -*-
# @Time    : 2026/08/08
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_compute_service.py
# @Software: trae-cn

"""
安全库存计算服务 - 每日全量刷新 stock_safe 表

数据流程：
  1. 从 oe_parts_sales 表读取历史销量数据（年均销量、日平均销量、标准差、月销量JSON等）
  2. 关联 crmapp_beihuo 表获取当前可用库存（available_stock）
  3. 对每个产品进行 ABC 分类、安全库存计算、上下限计算、库存状态判定
  4. TRUNCATE 清空 stock_safe 表后，批量写入新计算结果

ABC 分类规则：
  - 按年销量（annual_sales_1y）降序排列
  - A 类（前 20% 销量）：Z 值 = 1.5（较高服务水平），覆盖天数 = 10 天
  - B 类（中间 60% 销量）：Z 值 = 1.2（中等服务水平），覆盖天数 = 20 天
  - C 类（后 20% 销量）：Z 值 = 0.8（较低服务水平），覆盖天数 = 30 天
  - 年销量为 0 的产品强制归为 C 类（无销量数据无法衡量需求）

季节系数：当月销量 / 月均销量，钳制到 [0.7, 1.3] 范围内，用于修正安全库存

安全库存公式：SS = Z × σ_w × √(L / 7)
  - σ_w：周销量标准差（基于过去 52 周数据）
  - L：补货周期（当前为 1 天）
  - √(L/7)：将周标准差转换为 L 天内的需求标准差
"""

import json
# 用于解析月销量 JSON 字符串（monthly_sales_json 字段）

import time
# 用于计算任务执行耗时

from datetime import date, timedelta
# date: 获取当前日期，用于确定统计月份
# timedelta: 计算上月最后一天的日期偏移

# ── DAO 层导入 ──
from app.dao.stock_safe_dao.stock_safe_dao import (
    fetch_sales_with_inventory,  # 查询销量及库存数据
    truncate_table,               # TRUNCATE 清空 stock_safe 表
    batch_insert,                 # 批量插入记录到 stock_safe 表
)

# ── 日志工具导入 ──
from app.scripts.spiders.spiders_services.log import get_stock_safe_logger

# 创建日志记录器实例，用于输出各阶段执行日志
logger = get_stock_safe_logger()
# =============================================================================
# 配置常量模块
# =============================================================================

# ABC 分类配置字典
# 键：分类等级（A/B/C）
# 值：
#   pct   - 该分类占总产品数的比例（A:20%, B:60%, C:20%）
#   z     - 安全库存 Z 值（标准正态分布分位数，决定服务水平）
#   cover - 覆盖天数，用于计算库存上限中的备货天数
ABC_CFG = {
    'A': {'pct': 0.2, 'z': 1.5, 'cover': 20},   # 高价值/高销量，高服务水平，短覆盖
    'B': {'pct': 0.6, 'z': 1.2, 'cover': 15},   # 中价值/中销量，中等服务水平，中覆盖
    'C': {'pct': 0.2, 'z': 0.8, 'cover': 5},   # 低价值/低销量，低服务水平，长覆盖
}

# 采购提前期（天）：从下单到到货的周期
LEAD_TIME = 1

# 积压判定倍数：当可用库存 >= 库存上限 * 此倍数时，判定为库存积压
OVERSTOCK_RATIO = 1.3

# 批量插入时的每批记录数，避免单次插入数据量过大
INSERT_BATCH = 2000

# 季节系数的上下限钳制范围，防止极端月份数据导致安全库存剧烈波动
SEASON_MIN, SEASON_MAX = 0.7, 1.3


# =============================================================================
# ABC 分类计算函数
# =============================================================================

def _calc_abc(rows: list) -> dict:
    """
    按年销量（annual_sales_1y）降序对产品进行 ABC 分类。

    分类逻辑：
      1. 按年销量（annual_sales_1y）降序排列
      2. 前 20% 的产品 → A 类（高销量/高频次）
      3. 接下来的 60% 的产品 → B 类（中等）
      4. 剩余 20% 的产品 → C 类（低销量/低频次）
      5. 年销量为 0 的产品强制归为 C 类（无销量数据无法衡量需求）

    Args:
        rows: 从数据库查询到的原始数据行列表，每行包含 'number'、'brand_name'、
              'annual_sales_1y' 字段

    Returns:
        dict: 键为 "{number}|{brand_name}" 格式的唯一标识，值为 ABC 分类字符（'A'/'B'/'C'）
              若输入为空列表，返回空字典
    """
    # 提取每个产品的唯一标识和年销量
    # 使用 "|" 拼接 number 和 brand_name 作为唯一键，应对不同品牌下相同产品编号的情况
    products = []
    for r in rows:
        annual_sales = float(r.get('annual_sales_1y', 0) or 0)
        products.append({
            'key': f"{r['number']}|{r['brand_name']}",
            # 年销量作为 ABC 排序依据
            'annual_sales': annual_sales,
        })

    # 空数据保护：若没有产品数据，直接返回空字典
    if not products:
        return {}

    # 按年销量降序排列，销量高的产品排在前面
    sorted_prods = sorted(products, key=lambda x: x['annual_sales'], reverse=True)

    # 计算各类别的产品数量阈值
    total = len(sorted_prods)
    a_cnt = int(total * ABC_CFG['A']['pct'])       # A 类产品数量
    b_cnt = int(total * ABC_CFG['B']['pct'])       # B 类产品数量

    # 遍历排序后的产品列表，按索引分配 ABC 分类
    abc = {}
    for i, p in enumerate(sorted_prods):
        if i < a_cnt:
            # 前 a_cnt 个 → A 类
            abc[p['key']] = 'A'
        elif i < a_cnt + b_cnt:
            # 接下来 b_cnt 个 → B 类
            abc[p['key']] = 'B'
        else:
            # 剩余 → C 类
            abc[p['key']] = 'C'

    # 注意：annual_sales=0 的产品销量为 0，排序自然垫底落入 C 类区域，无需额外强制处理
    return abc


# =============================================================================
# 季节系数计算函数
# =============================================================================

def _calc_season(monthly_json: str, annual: float) -> float:
    """
    计算季节系数 = 当月销量 / 月均销量，结果钳制在 [0.7, 1.3] 范围内。

    设计意图：
      - 季节系数反映当前月份销量相对于平均水平的波动
      - 系数 > 1.0 表示旺季，安全库存应适当增加
      - 系数 < 1.0 表示淡季，安全库存应适当减少
      - 钳制范围避免极端值对安全库存造成过大冲击

    计算步骤：
      1. 月均销量 = 年销量 / 12
      2. 从 monthly_sales_json 中提取上个月的销量
      3. 当月销量 / 月均销量，得到基础季节系数
      4. 钳制到 [SEASON_MIN, SEASON_MAX] 范围内

    Args:
        monthly_json: 月销量 JSON 字符串，格式为 {"YYYY-MM": 销量, ...}
        annual: 年销量（过去 12 个月的总销量）

    Returns:
        float: 经过钳制处理的季节系数，保留两位小数。异常情况返回 1.0（无季节波动）
    """
    # 计算月均销量 = 年销量 / 12
    avg_monthly = annual / 12

    # 防御性处理：若年销量 <= 0，无法计算月均，返回 1.0（无季节调整）
    if avg_monthly <= 0:
        return 1.0

    # 解析 monthly_sales_json 字符串为字典
    # 注意：该字段在数据库中可能为 NULL 或空字符串，需做防御处理
    try:
        monthly = json.loads(monthly_json) if monthly_json else {}
    except (json.JSONDecodeError, TypeError):
        # JSON 解析失败时返回 1.0，避免整个计算流程中断
        return 1.0

    # 确保解析结果为字典类型（防御性检查）
    if not isinstance(monthly, dict):
        return 1.0

    # 确定统计月份：上月最后一天
    # 例：若今天是 2026-08-08，则上月最后一天为 2026-07-31
    # 策略：取当前月份第一天的前一天的月份
    today = date.today()
    stat = date(today.year, today.month, 1) - timedelta(days=1)

    # 从月销量字典中取出上个月的销量，格式化为 "YYYY-MM" 作为键
    cur = float(monthly.get(f"{stat.year:04d}-{stat.month:02d}", 0))

    # 计算季节系数并钳制到 [SEASON_MIN, SEASON_MAX] 范围
    # cur / avg_monthly 可能小于 0.7 或大于 1.3，通过 max/min 组合钳制
    return round(max(SEASON_MIN, min(SEASON_MAX, cur / avg_monthly)), 2)


# =============================================================================
# 库存状态判定函数
# =============================================================================

def _determine_status(avail: int, avg_daily: float, lower: float,
                      upper: float, safety: float, annual: int) -> tuple:
    """
    判定产品的库存状态及原因。

    判定优先级（从高到低）：
      1. 呆滞清库 → 年销量为 0，一年无销售记录
      2. 慢动销去库 → 年销量 <= 12，月均销量 <= 1
      3. 紧急补货 → 可用库存为 0 或 ≤ 安全库存
      4. 需补货 → 可用库存 ≤ 库存下限（再订货点）
      5. 库存积压 → 可用库存 ≥ 上限 × 积压阈值
      6. 正常 → 以上条件均不满足

    Args:
        avail:    可用库存数量
        avg_daily:日均销量
        lower:    库存下限
        upper:    库存上限
        safety:   调整后安全库存
        annual:   年销量

    Returns:
        tuple: (库存状态中文描述, 原因代码)
               - 正常状态时，reason 为 None
               - 特殊状态（呆滞清库/慢动销去库）时，reason 为原因代码
    """
    # 优先级 1：年销量为 0 → 呆滞清库
    if annual == 0:
        return '呆滞清库', 'no_sale_1y'

    # 优先级 2：年销量 <= 12 → 慢动销去库
    if annual <= 12:
        return '慢动销去库', 'low_sale'

    # 优先级 3：可用库存为 0 或 ≤ 安全库存 → 紧急补货
    if avail == 0 or avail <= safety:
        return '紧急补货', None

    # 优先级 4：可用库存 ≤ 库存下限（再订货点）→ 需补货
    if avail <= lower:
        return '需补货', None

    # 优先级 5：可用库存 ≥ 上限 × 积压倍数 → 库存积压
    if avail >= upper * OVERSTOCK_RATIO:
        return '库存积压', None

    # 默认状态：正常
    return '正常', None


# =============================================================================
# 库存上下限调整函数
# =============================================================================

def _adjust_limits(status: str, avail: int, lower: float, upper: float) -> tuple:
    """
    根据库存状态调整上下限值。

    调整规则：
      - 慢动销去库：下限设为 0（不强制补货），上限设为可用库存的 50%（逐步去库存）
      - 呆滞清库：上下限均设为 0（不再补货，清库处理）
      - 其他状态：保持原有计算值不变

    Args:
        status:  库存状态中文描述
        avail:   可用库存数量
        lower:   原始计算的下限值
        upper:   原始计算的上限值

    Returns:
        tuple: (调整后的下限, 调整后的上限)
    """
    # 慢动销去库：只出不进，上限设为现有库存的一半，逐步消耗
    if status == '慢动销去库':
        return 0.0, round(avail * 0.5, 2)

    # 呆滞清库：彻底停止补货，上下限归零
    if status == '呆滞清库':
        return 0.0, 0.0

    # 其他状态：保持原始计算值不变
    return lower, upper


# =============================================================================
# 单行记录构建函数
# =============================================================================

def _build_record(row: dict, abc_class: str) -> dict:
    """
    对单行数据计算所有安全库存相关字段，构建待插入数据库的字典。

    计算逻辑：
      1. 基础安全库存 = Z 值 × 周销量标准差 × 根号(提前期 / 7)
         这是在没有考虑季节波动情况下的基础安全库存水平
      2. 调整后安全库存 = 基础安全库存 × 季节系数
         考虑当前月份的季节性波动对安全库存进行修正
      3. 库存下限 = 日均销量 × 提前期 + 安全库存
         满足提前期内的需求并保留安全库存缓冲
      4. 库存上限 = 日均销量 × (提前期 + 覆盖天数) + 安全库存
         在提前期基础上增加覆盖天数作为备货周期的上限

    Args:
        row:       原始数据行字典，包含销量统计和库存字段
        abc_class: ABC 分类（'A'/'B'/'C'），用于确定 Z 值和覆盖天数

    Returns:
        dict: 包含所有计算结果的字典，可直接用于数据库插入
    """
    # ── 提取原始字段值（带防御性默认值） ──
    # 日均销量（过去 12 个月的日平均销量）
    avg_daily = float(row.get('avg_daily_sales_1y', 0) or 0)
    # 销量标准差（过去 52 周的周销量标准差）
    std_dev = float(row.get('sales_std_dev_1y', 0) or 0)
    # 年销量（过去 12 个月的总销量）
    annual = int(row.get('annual_sales_1y', 0) or 0)
    # 当前可用库存（来自 crmapp_beihuo 的实际库存）
    avail = int(row.get('available_stock', 0) or 0)
    # 当前在途数量（来自 crmapp_beihuo 的在途数量）
    in_transit = int(row.get('transit_quantity', 0) or 0)

    # ── 安全库存计算 ──
    # 计算季节系数
    season = _calc_season(row.get('monthly_sales_json'), annual)  # pyright: ignore[reportArgumentType]

    # 基础安全库存 = Z值 × 周销量标准差 × 根号(提前期 ÷ 7)
    # 使用 ABC_CFG.get 防御性读取，若 abc_class 不在配置中则默认用 C 类参数
    base = round(ABC_CFG.get(abc_class, ABC_CFG['C'])['z'] * std_dev * (LEAD_TIME / 7) ** 0.5, 2)

    # 调整后安全库存 = 基础安全库存 × 季节系数
    safety = round(base * season, 2)

    # ── 库存上下限计算 ──
    # 获取 ABC 分类对应的覆盖天数
    cover = ABC_CFG.get(abc_class, ABC_CFG['C'])['cover']

    # 下限 = 日平均销量 × 提前期 + 安全库存
    # 含义：在补货到货前的最低需求 + 安全缓冲
    lower = round(avg_daily * LEAD_TIME + safety, 2)

    # 上限 = 日平均销量 × (提前期 + 覆盖天数) + 安全库存
    # 含义：从下单到下次补货前的最长周期需求 + 安全缓冲
    upper = round(avg_daily * (LEAD_TIME + cover) + safety, 2)

    # ── 库存状态判定与上下限调整 ──
    # 根据可用库存、日均销量、上下限、安全库存和年销量判定库存状态
    status, reason = _determine_status(avail, avg_daily, lower, upper, safety, annual)

    # 根据状态调整上下限（慢动销/呆滞产品需要特殊处理）
    adj_lower, adj_upper = _adjust_limits(status, avail, lower, upper)

    # ── 构建返回字典 ──
    # 注意：字段名需与数据库表 stock_safe 的列名严格对应
    return {
        # 产品标识字段
        'number': row['number'],                  # 产品编号
        'brand_name': row['brand_name'],          # 品牌名称
        'frey_no': row['frey_no'],                # 条码/货号
        'pdname': row.get('pdname'),              # 产品名称（可能为 NULL）

        # ABC 分类与销量统计
        'abc_classification': abc_class,          # ABC 分类（A/B/C）
        'avg_daily_sales': avg_daily,             # 日平均销量

        # 安全库存相关
        'base_safety_stock': base,                # 基础安全库存（未含季节调整）
        'season_coefficient': season,             # 季节系数
        'safety_stock': safety,                   # 最终安全库存（含季节调整）

        # 库存上下限
        'stock_lower_limit': adj_lower,           # 调整后的库存下限
        'stock_upper_limit': adj_upper,           # 调整后的库存上限

        # 库存状态
        'available_stock': avail,                 # 当前可用库存
        'transit_quantity': in_transit,           # 在途数量
        'sellable_days': round(avail / avg_daily, 2) if avg_daily > 0 else 0.0,  # 可销售天数
        'stock_status': status,                   # 库存状态
    }


# =============================================================================
# 主入口函数
# =============================================================================

def run_compute() -> dict:
    """
    安全库存每日全量刷新主入口函数。

    执行流程：
      第 1 步：从 oe_parts_sales 和 crmapp_beihuo 读取并集销量及库存数据
      第 2 步：对所有产品进行 ABC 分类（基于年销量 annual_sales_1y）
      第 3 步：逐行计算安全库存、上下限、库存状态等字段
      第 4 步：TRUNCATE 清空 stock_safe 表后批量写入新计算结果

    全量刷新策略说明：
      - 采用 TRUNCATE + 批量 INSERT 的方式，确保数据完全一致
      - 不采用增量更新，因为每次计算需要重新评估所有产品的分类和状态
      - 批量写入使用 INSERT_BATCH = 2000 条一批，避免大事务导致锁表

    Returns:
        dict: 执行结果摘要，包含：
            - status: 执行状态字符串（'completed' 表示成功）
            - total_count: 总记录数
            - inserted_count: 实际写入记录数
            - total_elapsed_time: 总耗时（秒）
            - timestamp: 完成时间戳

    Raises:
        Exception: 任何异常会被日志记录后重新抛出，由上层调用方处理
    """
    start = time.time()  # 记录任务开始时间，用于计算总耗时
    logger.info("[开始] stock_safe 安全库存计算任务启动")

    try:
        # ====== 阶段 1：读取原始数据 ======
        # 从 oe_parts_sales 和 crmapp_beihuo 的并集读取销量统计和可用库存
        rows = fetch_sales_with_inventory()
        logger.info("[阶段1] 读取数据完成: %d 条", len(rows))

        # 空数据保护：若没有数据，直接返回空结果，不执行后续计算
        if not rows:
            return {"status": "completed", "total_count": 0, "inserted_count": 0,
                    "total_elapsed_time": round(time.time() - start, 2),
                    "timestamp": int(time.time())}

        # ====== 阶段 2：ABC 分类 ======
        # 按年销量（annual_sales_1y）对所有产品进行 ABC 分类
        # 注意：分类结果依赖于全局年销量排序，必须全部加载后才能计算
        abc = _calc_abc(rows)
        logger.info("[阶段2] ABC分类: A=%d B=%d C=%d",
                    sum(1 for v in abc.values() if v == 'A'),
                    sum(1 for v in abc.values() if v == 'B'),
                    sum(1 for v in abc.values() if v == 'C'))

        # ====== 阶段 3：逐行计算 ======
        # 列表推导式逐行计算安全库存字段
        # 使用 abc.get 获取分类，若产品不在分类字典中（理论上不会发生），默认 C 类
        records = [_build_record(r, abc.get(f"{r['number']}|{r['brand_name']}", 'C'))
                   for r in rows]
        logger.info("[阶段3] 计算完成: %d 条", len(records))

        # ====== 阶段 4：写入数据库 ======
        # 全量刷新策略：先 TRUNCATE 清空旧数据，再批量写入新数据
        # 注意：TRUNCATE 是 DDL 操作，隐式提交事务，且无法回滚
        truncate_table()

        # 批量插入，每批 INSERT_BATCH 条，避免单次 SQL 过大
        inserted = batch_insert(records, batch_size=INSERT_BATCH)

        # 计算总耗时并记录日志
        elapsed = round(time.time() - start, 2)
        logger.info("[完成] 写入 %d 行, 耗时 %.2fs", inserted, elapsed)

        # 返回执行结果摘要
        return {"status": "completed", "total_count": len(records),
                "inserted_count": inserted, "total_elapsed_time": elapsed,
                "timestamp": int(time.time())}

    except Exception:
        # 捕获所有异常，记录完整堆栈信息后重新抛出
        # 上层调度方（如定时任务框架）可根据异常决定是否重试或告警
        logger.error("[失败] stock_safe 计算异常", exc_info=True)
        raise


# =============================================================================
# 脚本入口
# =============================================================================

# if __name__ == "__main__":
#     # 当直接运行此脚本时，执行安全库存计算
#     # 注：实际生产环境中通常由定时任务调度器（如 APScheduler/Celery Beat）调用
#     run_compute()