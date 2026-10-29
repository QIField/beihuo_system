# -*- coding: utf-8 -*-
"""oe_diff_scan_service 扫描判定单测：evaluate_oe / compute_scan_results 为纯函数，不依赖数据库"""
from app.services.oe_diff_scan_service.scan_service import evaluate_oe, compute_scan_results


def _row(pid, oe, replace_number, brand='原厂'):
    return {'product_id': pid, 'oe': oe, 'brand': brand, 'replace_number': replace_number}


def test_multi_rows_same_numbers_is_consistent():
    rows = [_row(1, 'A123', 'B456,C789'), _row(2, 'B456', 'C789,B456', '马勒')]
    result = evaluate_oe('A123', rows)
    assert result['status'] == '一致'
    assert result['matched_count'] == 2


def test_order_difference_is_not_a_diff():
    """A123,B456 与 B456,A123 视为相同（只比较号码集合，不比较顺序）"""
    rows = [_row(1, 'A123', 'B456,A123'), _row(2, 'B456', 'A123,B456', '博世')]
    assert evaluate_oe('A123', rows)['status'] == '一致'


def test_missing_number_is_diff():
    rows = [_row(1, 'A123', 'B456,C789'), _row(2, 'B456', 'A123,B456', '马勒')]
    result = evaluate_oe('A123', rows)
    # 并集 {A123,B456,C789}，两行各有缺失
    assert result['status'] == '有差异'
    assert result['matched_count'] == 2


def test_extra_number_is_diff():
    rows = [_row(1, 'A123', 'B456'), _row(2, 'B456', 'A123,C789', '马勒')]
    assert evaluate_oe('A123', rows)['status'] == '有差异'


def test_single_row_is_single():
    result = evaluate_oe('A123', [_row(1, 'A123', 'B456,C789')])
    assert result['status'] == '单行'
    assert result['matched_count'] == 1


def test_empty_rows_is_unmatched():
    assert evaluate_oe('A123', [])['status'] == '未匹配'


def test_chinese_comma_split():
    """中英文逗号混用不影响号码集合比较"""
    rows = [_row(1, 'A123', 'B456，C789'), _row(2, 'B456', 'C789,B456', '马勒')]
    assert evaluate_oe('A123', rows)['status'] == '一致'


def test_compute_scan_results_matches_two_ways():
    """主oe匹配 ∪ 替换号包含匹配，且按行去重"""
    rows = [
        _row(1, 'A123', 'B456,C789'),
        _row(2, 'B456', 'A123', '马勒'),
        _row(3, 'C789', 'A123', '博世'),
        _row(4, 'D001', 'X999', '其他'),
    ]
    results = {r['oe']: r for r in compute_scan_results(rows, ['A123', 'D001', 'E999'])}
    assert results['A123']['matched_count'] == 3
    assert results['A123']['status'] == '有差异'
    assert results['D001']['status'] == '单行'
    assert results['E999']['status'] == '未匹配'
