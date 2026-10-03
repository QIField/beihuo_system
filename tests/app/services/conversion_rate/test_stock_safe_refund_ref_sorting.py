# -*- coding:utf-8 -*-
# @Time    : 2026/08/05
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : test_stock_safe_refund_ref_sorting.py

"""
安全库存退货关联表 - 排序逻辑单元测试

测试 _find_combination_match 函数和 step2 排序逻辑的各场景：
1. 直接匹配（数量相等）
2. 组合匹配（子集和等于目标值）
3. 无匹配（按数量降序）
4. 边界情况（空列表、单元素、多组合等）

运行方式：
    python -m tests.conversion_rate.test_stock_safe_refund_ref_sorting
"""

import sys
import os
import copy

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.stock_safe_service.stock_safe_refund_ref_service import (
    _find_combination_match,
    _sort_normal_orders,
)


# ==================== _find_combination_match 单元测试 ====================

def test_combination_match_empty_list():
    """空列表应返回空列表"""
    result = _find_combination_match([], 10)
    assert result == [], f"空列表应返回空列表，实际返回 {result}"
    print("[PASS] test_combination_match_empty_list")


def test_combination_match_single_exact():
    """单元素列表且等于目标值"""
    result = _find_combination_match([7], 7)
    assert result == [0], f"应返回 [0]，实际返回 {result}"
    print("[PASS] test_combination_match_single_exact")


def test_combination_match_single_no_match():
    """单元素列表且不等于目标值"""
    result = _find_combination_match([5], 7)
    assert result == [], f"应返回空列表，实际返回 {result}"
    print("[PASS] test_combination_match_single_no_match")


def test_combination_match_two_elements():
    """两元素之和等于目标值"""
    result = _find_combination_match([3, 4], 7)
    assert result == [0, 1], f"应返回 [0, 1]，实际返回 {result}"
    print("[PASS] test_combination_match_two_elements")


def test_combination_match_subset():
    """多元素中部分子集和等于目标值"""
    result = _find_combination_match([5, 3, 4], 7)
    # 算法优先选择靠前的索引组合，3+4=7 对应索引 [1, 2]
    assert result == [1, 2], f"应返回 [1, 2]（3+4=7），实际返回 {result}"
    print("[PASS] test_combination_match_subset")


def test_combination_match_larger_set():
    """多元素中组合匹配"""
    result = _find_combination_match([2, 3, 5, 7, 9], 10)
    # 2+3+5=10，对应索引 [0, 1, 2]
    assert result == [0, 1, 2], f"应返回 [0, 1, 2]（2+3+5=10），实际返回 {result}"
    print("[PASS] test_combination_match_larger_set")


def test_combination_match_no_match():
    """无任何组合能匹配目标值"""
    result = _find_combination_match([2, 4, 6], 7)
    assert result == [], f"应返回空列表，实际返回 {result}"
    print("[PASS] test_combination_match_no_match")


def test_combination_match_sum_less_than_target():
    """所有元素之和小于目标值，应快速剪枝返回空"""
    result = _find_combination_match([1, 2, 3], 10)
    assert result == [], f"应返回空列表（快速剪枝），实际返回 {result}"
    print("[PASS] test_combination_match_sum_less_than_target")


def test_combination_match_duplicate_values():
    """存在重复值"""
    result = _find_combination_match([3, 3, 4], 7)
    # 3+4=7，索引 [0, 2] 或 [1, 2]
    assert result in ([0, 2], [1, 2]), f"应返回 [0, 2] 或 [1, 2]，实际返回 {result}"
    print("[PASS] test_combination_match_duplicate_values")


def test_combination_match_zero_target():
    """目标值为0应返回空列表"""
    result = _find_combination_match([1, 2, 3], 0)
    assert result == [], f"目标值为0应返回空列表，实际返回 {result}"
    print("[PASS] test_combination_match_zero_target")


# ==================== 排序逻辑场景测试 ====================

def _test_sorting_scenario(refund_quantity: int, normal_orders: list, expected_order: list, scenario_name: str):
    """
    调用 _sort_normal_orders 验证排序结果是否符合预期

    Args:
        refund_quantity: 退货数量（负数）
        normal_orders: 常规订单列表，每个元素为 dict，包含 quantity 字段
        expected_order: 期望的 quantity 顺序
        scenario_name: 场景名称
    """
    matched_normal_orders = copy.deepcopy(normal_orders)
    _sort_normal_orders(matched_normal_orders, refund_quantity)

    actual_order = [o["quantity"] for o in matched_normal_orders]
    assert actual_order == expected_order, (
        f"[{scenario_name}] 排序结果不符合预期\n"
        f"  期望: {expected_order}\n"
        f"  实际: {actual_order}"
    )
    print(f"[PASS] {scenario_name}")


def test_sorting_exact_match():
    """场景1: 存在直接匹配 - 退货数量-7，常规订单有7"""
    normal_orders = [{"quantity": 5}, {"quantity": 7}, {"quantity": 3}]
    # 7 直接匹配应排最前，其余按数量降序
    _test_sorting_scenario(-7, normal_orders, [7, 5, 3], "直接匹配优先")


def test_sorting_combination_match():
    """场景2: 存在组合匹配 - 退货数量-7，常规订单5、3、4（3+4=7）"""
    normal_orders = [{"quantity": 5}, {"quantity": 3}, {"quantity": 4}]
    # 组合匹配的 3,4 排前面（按数量降序：4, 3），剩余 5 排最后
    _test_sorting_scenario(-7, normal_orders, [4, 3, 5], "组合匹配（3+4=7）")


def test_sorting_combination_match_complex():
    """场景3: 复杂组合匹配 - 退货数量-10，常规订单2、3、5、7、9（2+3+5=10）"""
    normal_orders = [{"quantity": 2}, {"quantity": 3}, {"quantity": 5}, {"quantity": 7}, {"quantity": 9}]
    # 组合匹配的 2,3,5 排前面（按数量降序：5, 3, 2），剩余 9,7 按数量降序
    _test_sorting_scenario(-10, normal_orders, [5, 3, 2, 9, 7], "复杂组合匹配（2+3+5=10）")


def test_sorting_no_match():
    """场景4: 无任何匹配 - 退货数量-7，常规订单2、4、6（无组合能等于7）"""
    normal_orders = [{"quantity": 2}, {"quantity": 4}, {"quantity": 6}]
    # 无匹配，按数量降序（大→小）
    _test_sorting_scenario(-7, normal_orders, [6, 4, 2], "无匹配按降序")


def test_sorting_single_element_match():
    """场景5: 单元素且匹配"""
    normal_orders = [{"quantity": 7}]
    _test_sorting_scenario(-7, normal_orders, [7], "单元素匹配")


def test_sorting_single_element_no_match():
    """场景6: 单元素且不匹配"""
    normal_orders = [{"quantity": 5}]
    _test_sorting_scenario(-7, normal_orders, [5], "单元素不匹配")


def test_sorting_combination_match_duplicates():
    """场景7: 重复值组合匹配 - 退货数量-7，常规订单3、3、4（3+4=7）"""
    normal_orders = [{"quantity": 3}, {"quantity": 3}, {"quantity": 4}]
    # 组合匹配的 3,4 排前面（按数量降序：4, 3），剩余 3 排最后（按数量降序）
    _test_sorting_scenario(-7, normal_orders, [4, 3, 3], "重复值组合匹配")


def test_sorting_multiple_combinations():
    """场景8: 多种组合可能 - 退货数量-7，常规订单1、2、4、3、5"""
    normal_orders = [{"quantity": 1}, {"quantity": 2}, {"quantity": 4}, {"quantity": 3}, {"quantity": 5}]
    # 1+2+4=7（索引0,1,2），组合匹配的排前面（按数量降序：4, 2, 1），剩余 5,3 按数量降序
    _test_sorting_scenario(-7, normal_orders, [4, 2, 1, 5, 3], "多种组合可能（1+2+4=7）")


def test_sorting_exact_match_multiple():
    """场景9: 多个直接匹配 - 退货数量-7，常规订单7、7、3"""
    normal_orders = [{"quantity": 7}, {"quantity": 7}, {"quantity": 3}]
    # 直接匹配优先，其余按数量降序
    _test_sorting_scenario(-7, normal_orders, [7, 7, 3], "多个直接匹配")


def test_sorting_combination_match_all_used():
    """场景10: 所有订单组成组合 - 退货数量-10，常规订单1、2、3、4"""
    normal_orders = [{"quantity": 1}, {"quantity": 2}, {"quantity": 3}, {"quantity": 4}]
    # 1+2+3+4=10，所有订单组成组合，按数量降序
    _test_sorting_scenario(-10, normal_orders, [4, 3, 2, 1], "所有订单组成组合")


# ==================== 主测试函数 ====================

def run_all_tests():
    print("=" * 70)
    print("安全库存退货关联表 - 排序逻辑单元测试")
    print("=" * 70)

    print("\n--- _find_combination_match 单元测试 ---")
    test_combination_match_empty_list()
    test_combination_match_single_exact()
    test_combination_match_single_no_match()
    test_combination_match_two_elements()
    test_combination_match_subset()
    test_combination_match_larger_set()
    test_combination_match_no_match()
    test_combination_match_sum_less_than_target()
    test_combination_match_duplicate_values()
    test_combination_match_zero_target()

    print("\n--- 排序逻辑场景测试 ---")
    test_sorting_exact_match()
    test_sorting_combination_match()
    test_sorting_combination_match_complex()
    test_sorting_no_match()
    test_sorting_single_element_match()
    test_sorting_single_element_no_match()
    test_sorting_combination_match_duplicates()
    test_sorting_multiple_combinations()
    test_sorting_exact_match_multiple()
    test_sorting_combination_match_all_used()

    print("\n" + "=" * 70)
    print("全部测试通过！")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)