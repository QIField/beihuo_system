# -*- coding:utf-8 -*-
# @Time    : 2026/08/08
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : test_stock_safe_compute.py

"""
安全库存计算服务 - 纯函数单元测试

测试范围（无需数据库）：
1. _determine_status：6 种核心状态 + 边界值
2. _build_record：安全库存公式计算、上下限、状态字段
3. _calc_season：季节系数计算与钳制
4. _calc_abc：ABC 分类逻辑
5. _adjust_limits：上下限调整策略

运行方式：
    python -m tests.conversion_rate.test_stock_safe_compute
"""

import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.stock_safe_service.stock_safe_compute_service import (
    _determine_status,
    _build_record,
    _calc_season,
    _calc_abc,
    _adjust_limits,
    LEAD_TIME,
    OVERSTOCK_RATIO,
    ABC_CFG,
)


# =============================================================================
# 辅助函数
# =============================================================================

def _assert_status(result, expected_status, expected_reason):
    """断言 _determine_status 返回的二元组"""
    status, reason = result
    assert status == expected_status, f"status: expected {expected_status}, got {status}"
    assert reason == expected_reason, f"reason: expected {expected_reason}, got {reason}"


# =============================================================================
# 测试：_determine_status
# =============================================================================

def test_status_dead_stock():
    """年销量为 0 → 呆滞清库"""
    result = _determine_status(avail=100, avg_daily=10, lower=50, upper=200, safety=20, annual=0)
    _assert_status(result, '呆滞清库', 'no_sale_1y')


def test_status_slow_moving():
    """年销量 ≤ 12 → 慢动销去库"""
    result = _determine_status(avail=100, avg_daily=10, lower=50, upper=200, safety=20, annual=12)
    _assert_status(result, '慢动销去库', 'low_sale')


def test_status_urgent_replenish_stockout():
    """可用库存为 0 → 紧急补货"""
    result = _determine_status(avail=0, avg_daily=100, lower=200, upper=500, safety=50, annual=1000)
    _assert_status(result, '紧急补货', None)


def test_status_urgent_replenish_safety_exhausted():
    """可用库存 ≤ 安全库存 → 紧急补货"""
    result = _determine_status(avail=30, avg_daily=100, lower=200, upper=500, safety=50, annual=1000)
    _assert_status(result, '紧急补货', None)


def test_status_replenish():
    """可用库存 ≤ 库存下限 → 需补货"""
    # avail=60, avg_daily=10 → sellable=6, ROP=lower=200, 60 <= 200 → 需补货
    result = _determine_status(avail=60, avg_daily=10, lower=200, upper=500, safety=50, annual=1000)
    _assert_status(result, '需补货', None)


def test_status_overstock():
    """可用库存 ≥ 上限 × 积压阈值 → 库存积压"""
    upper = 500
    result = _determine_status(avail=int(upper * OVERSTOCK_RATIO), avg_daily=10,
                               lower=50, upper=upper, safety=20, annual=1000)
    _assert_status(result, '库存积压', None)


def test_status_normal():
    """所有条件均不满足 → 正常"""
    result = _determine_status(avail=300, avg_daily=10, lower=50, upper=500, safety=20, annual=1000)
    _assert_status(result, '正常', None)


def test_status_priority_order():
    """验证优先级：呆滞清库 > 慢动销去库 > 紧急补货 > 需补货 > 积压 > 正常"""
    # 同时满足多个条件，应返回优先级最高的
    # annual=0（呆滞）且 avail=0（紧急补货）→ 应返回呆滞
    result = _determine_status(avail=0, avg_daily=10, lower=50, upper=200, safety=20, annual=0)
    _assert_status(result, '呆滞清库', 'no_sale_1y')

    # annual=12（慢动销）且 avail=0（紧急补货）→ 应返回慢动销
    result = _determine_status(avail=0, avg_daily=10, lower=50, upper=200, safety=20, annual=12)
    _assert_status(result, '慢动销去库', 'low_sale')

    # avail=10, safety=50（紧急补货）且 avail=10 <= lower=200（需补货）→ 应返回紧急补货
    result = _determine_status(avail=10, avg_daily=10, lower=200, upper=500, safety=50, annual=1000)
    _assert_status(result, '紧急补货', None)


# =============================================================================
# 测试：_calc_season
# =============================================================================

def test_season_normal():
    """正常季节系数计算"""
    monthly_json = '{"2026-07": 120, "2026-06": 100, "2026-05": 80}'
    # 年销量 1200，月均 100，当月 120 → 1.2
    result = _calc_season(monthly_json, 1200)
    assert result == 1.2, f"expected 1.2, got {result}"


def test_season_clamp_min():
    """季节系数低于下限 0.7 时钳制"""
    monthly_json = '{"2026-07": 30, "2026-06": 100}'
    # 年销量 1200，月均 100，当月 30 → 0.3 → 钳制为 0.7
    result = _calc_season(monthly_json, 1200)
    assert result == 0.7, f"expected 0.7, got {result}"


def test_season_clamp_max():
    """季节系数高于上限 1.3 时钳制"""
    monthly_json = '{"2026-07": 200, "2026-06": 100}'
    # 年销量 1200，月均 100，当月 200 → 2.0 → 钳制为 1.3
    result = _calc_season(monthly_json, 1200)
    assert result == 1.3, f"expected 1.3, got {result}"


def test_season_zero_annual():
    """年销量为 0 时返回 1.0"""
    result = _calc_season('{"2026-07": 100}', 0)
    assert result == 1.0, f"expected 1.0, got {result}"


def test_season_invalid_json():
    """JSON 解析失败时返回 1.0"""
    result = _calc_season('not valid json', 1200)
    assert result == 1.0, f"expected 1.0, got {result}"


# =============================================================================
# 测试：_calc_abc
# =============================================================================

def test_abc_simple():
    """基本 ABC 分类"""
    rows = [
        {'number': 'P001', 'brand_name': 'B', 'annual_sales_1y': 1000},
        {'number': 'P002', 'brand_name': 'B', 'annual_sales_1y': 500},
        {'number': 'P003', 'brand_name': 'B', 'annual_sales_1y': 100},
        {'number': 'P004', 'brand_name': 'B', 'annual_sales_1y': 50},
        {'number': 'P005', 'brand_name': 'B', 'annual_sales_1y': 10},
    ]
    abc = _calc_abc(rows)
    assert abc['P001|B'] == 'A', f"P001 expected A, got {abc['P001|B']}"
    assert abc['P002|B'] == 'B', f"P002 expected B, got {abc['P002|B']}"
    assert abc['P003|B'] == 'B', f"P003 expected B, got {abc['P003|B']}"
    assert abc['P004|B'] == 'B', f"P004 expected B, got {abc['P004|B']}"
    assert abc['P005|B'] == 'C', f"P005 expected C, got {abc['P005|B']}"


def test_abc_zero_sales():
    """零销量产品强制归为 C 类"""
    rows = [
        {'number': 'P001', 'brand_name': 'B', 'annual_sales_1y': 1000},
        {'number': 'P002', 'brand_name': 'B', 'annual_sales_1y': 0},
    ]
    abc = _calc_abc(rows)
    assert abc['P002|B'] == 'C', f"P002 expected C, got {abc['P002|B']}"


def test_abc_empty():
    """空数据列表返回空字典"""
    assert _calc_abc([]) == {}


# =============================================================================
# 测试：_adjust_limits
# =============================================================================

def test_adjust_slow_moving():
    """慢动销：下限=0，上限=可用库存×50%"""
    lower, upper = _adjust_limits('慢动销去库', avail=100, lower=50, upper=200)
    assert lower == 0.0, f"expected 0.0, got {lower}"
    assert upper == 50.0, f"expected 50.0, got {upper}"


def test_adjust_dead_stock():
    """呆滞：上下限均为 0"""
    lower, upper = _adjust_limits('呆滞清库', avail=100, lower=50, upper=200)
    assert lower == 0.0, f"expected 0.0, got {lower}"
    assert upper == 0.0, f"expected 0.0, got {upper}"


def test_adjust_replenish():
    """正常补货：保持原值不变"""
    lower, upper = _adjust_limits('正常', avail=100, lower=50, upper=200)
    assert lower == 50, f"expected 50, got {lower}"
    assert upper == 200, f"expected 200, got {upper}"


# =============================================================================
# 测试：_build_record（安全库存公式计算）
# =============================================================================

def test_build_record_normal():
    """正常数据：验证安全库存公式 SS = Z × σ_w × √(L/7)"""
    row = {
        'number': 'P001',
        'brand_name': 'B',
        'frey_no': '123456',
        'pdname': 'Test Product',
        'avg_daily_sales_1y': 50,
        'sales_std_dev_1y': 100,  # 周销量标准差 σ_w = 100
        'annual_sales_1y': 18000,
        'available_stock': 300,
        'monthly_sales_json': '{"2026-07": 1500, "2026-06": 1500, "2026-05": 1500, "2026-04": 1500, "2026-03": 1500, "2026-02": 1500, "2026-01": 1500, "2025-12": 1500, "2025-11": 1500, "2025-10": 1500, "2025-09": 1500, "2025-08": 1500}',
    }
    record = _build_record(row, 'A')

    # 验证：A 类 Z=1.5, σ_w=100, L=1
    # 基础安全库存 = 1.5 × 100 × √(1/7) = 1.5 × 100 × 0.378 = 56.7
    expected_base = round(ABC_CFG['A']['z'] * 100 * (LEAD_TIME / 7) ** 0.5, 2)
    assert record['base_safety_stock'] == expected_base, \
        f"base_safety_stock: expected {expected_base}, got {record['base_safety_stock']}"

    # 季节系数：月均=1500，当月=1500 → 1.0
    assert record['season_coefficient'] == 1.0

    # 调整后安全库存 = 56.7 × 1.0 = 56.7
    assert record['safety_stock'] == expected_base

    # 下限 = 50 × 1 + 56.7 = 106.7
    expected_lower = round(50 * LEAD_TIME + expected_base, 2)
    assert record['stock_lower_limit'] == expected_lower, \
        f"lower: expected {expected_lower}, got {record['stock_lower_limit']}"

    # 上限 = 50 × (1 + 10) + 56.7 = 606.7
    expected_upper = round(50 * (LEAD_TIME + ABC_CFG['A']['cover']) + expected_base, 2)
    assert record['stock_upper_limit'] == expected_upper, \
        f"upper: expected {expected_upper}, got {record['stock_upper_limit']}"

    # 库存状态：avail=300, lower=106.7, upper=606.7, sellable=6
    # 300 > 106.7（不触发需补货）, 300 < 606.7×1.3=788.7（不触发积压）→ 正常
    assert record['stock_status'] == '正常', f"status: expected 正常, got {record['stock_status']}"


def test_build_record_zero_sales():
    """零销量数据：呆滞清库状态"""
    row = {
        'number': 'P002', 'brand_name': 'B', 'frey_no': '789012', 'pdname': None,
        'avg_daily_sales_1y': 0, 'sales_std_dev_1y': 0,
        'annual_sales_1y': 0, 'available_stock': 50,
        'monthly_sales_json': None,
    }
    record = _build_record(row, 'C')
    assert record['stock_status'] == '呆滞清库'


def test_build_record_safety_formula():
    """验证公式变更：σ_w=100, L=1 时, SS = Z × 100 × √(1/7) ≈ Z × 37.8"""
    row = {
        'number': 'P003', 'brand_name': 'B', 'frey_no': '345678', 'pdname': None,
        'avg_daily_sales_1y': 10, 'sales_std_dev_1y': 100,
        'annual_sales_1y': 3600, 'available_stock': 200,
        'monthly_sales_json': '{"2026-07": 300, "2026-06": 300, "2026-05": 300, "2026-04": 300, "2026-03": 300, "2026-02": 300, "2026-01": 300, "2025-12": 300, "2025-11": 300, "2025-10": 300, "2025-09": 300, "2025-08": 300}',
    }

    for abc_class, z in [('A', 1.5), ('B', 1.2), ('C', 0.8)]:
        record = _build_record(row, abc_class)
        expected_base = round(z * 100 * (1 / 7) ** 0.5, 2)
        assert record['base_safety_stock'] == expected_base, \
            f"{abc_class}: expected {expected_base}, got {record['base_safety_stock']}"


# =============================================================================
# 测试入口
# =============================================================================

def test_all():
    """运行所有测试"""
    test_status_dead_stock()
    test_status_slow_moving()
    test_status_urgent_replenish_stockout()
    test_status_urgent_replenish_safety_exhausted()
    test_status_replenish()
    test_status_overstock()
    test_status_normal()
    test_status_priority_order()

    test_season_normal()
    test_season_clamp_min()
    test_season_clamp_max()
    test_season_zero_annual()
    test_season_invalid_json()

    test_abc_simple()
    test_abc_zero_sales()
    test_abc_empty()

    test_adjust_slow_moving()
    test_adjust_dead_stock()
    test_adjust_replenish()

    test_build_record_normal()
    test_build_record_zero_sales()
    test_build_record_safety_formula()

    print("✅ 所有测试通过")


if __name__ == "__main__":
    test_all()