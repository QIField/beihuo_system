# -*- coding:utf-8 -*-
"""
比价导入结果快照序列化单元测试

只测试纯逻辑（serialize_results），不依赖数据库：
1. 月份明细（lowest_price + 当月全部记录，价格升序）
2. overall_lowest / overall_highest 极值
3. all_records 跨月聚合且按日期倒序
4. 空结果、无采购记录行的兜底结构

运行方式：
    python tests/app/services/compare_service/test_compare_result_snapshot_service.py
"""

import json
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..', '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.models.purchase_history_compare_models import (
    OECompareResult,
    MonthSummary,
    PurchaseRecord,
)
from app.services.compare_service.compare_result_snapshot_service import (
    CompareResultSnapshotService,
)


def _build_result():
    records_may = [
        PurchaseRecord(year=2024, month=5, supplier='供应商B', price=110.0),
        PurchaseRecord(year=2024, month=5, supplier='供应商A', price=120.0),
    ]
    records_mar = [
        PurchaseRecord(year=2024, month=3, supplier='供应商C', price=100.0),
    ]
    return OECompareResult(
        oe='A123',
        search_oe='A123',
        brand='博世',
        month_summaries={
            5: MonthSummary(month=5, lowest_price=110.0, all_records=records_may),
            3: MonthSummary(month=3, lowest_price=100.0, all_records=records_mar),
        },
        overall_lowest=('2024-03', '供应商C', 100.0),
        overall_highest=('2024-05', '供应商A', 120.0),
        product_name='测试件',
        stock_quantity=5,
        tag='A类',
        sales_today=1,
        price=99.5,
    )


def test_serialize_structure_and_extremes():
    result = _build_result()
    result.group_index = 1
    data = json.loads(CompareResultSnapshotService.serialize_results([result]))

    assert len(data) == 1
    row = data[0]
    assert row['oe'] == 'A123'
    assert row['group_index'] == 1
    assert row['overall_lowest'] == ['2024-03', '供应商C', 100.0]
    assert row['overall_highest'] == ['2024-05', '供应商A', 120.0]
    assert row['product_name'] == '测试件'
    assert row['stock_quantity'] == 5
    assert row['price'] == 99.5


def test_serialize_month_records_preserved():
    result = _build_result()
    row = json.loads(CompareResultSnapshotService.serialize_results([result]))[0]

    may = row['months']['5']
    assert may['lowest_price'] == 110.0
    # MonthSummary 已按价格升序，序列化后顺序保持
    assert [r['price'] for r in may['records']] == [110.0, 120.0]
    assert may['records'][0] == {'date': '2024-05', 'supplier': '供应商B', 'price': 110.0}

    mar = row['months']['3']
    assert len(mar['records']) == 1


def test_all_records_aggregated_desc():
    result = _build_result()
    row = json.loads(CompareResultSnapshotService.serialize_results([result]))[0]

    assert [r['date'] for r in row['all_records']] == ['2024-05', '2024-05', '2024-03']
    assert len(row['all_records']) == 3


def test_empty_results_and_no_records_row():
    assert json.loads(CompareResultSnapshotService.serialize_results([])) == []

    empty_row_result = OECompareResult(
        oe='X',
        search_oe='X',
        brand='品牌',
        month_summaries={},
        overall_lowest=('', '', 0.0),
        overall_highest=('', '', 0.0),
    )
    row = json.loads(CompareResultSnapshotService.serialize_results([empty_row_result]))[0]
    assert row['overall_lowest'] is None
    assert row['overall_highest'] is None
    assert row['months'] == {}
    assert row['all_records'] == []
    # 无 product_name、无 frey_no、无月份记录 → 名称列展示未匹配
    assert row['product_name'] == '未匹配到数据'


def test_product_name_falls_back_empty_when_has_month_records():
    result = OECompareResult(
        oe='Y',
        search_oe='Y',
        brand='品牌',
        month_summaries={
            1: MonthSummary(month=1, lowest_price=10.0, all_records=[
                PurchaseRecord(year=2024, month=1, supplier='S', price=10.0),
            ]),
        },
        overall_lowest=('2024-01', 'S', 10.0),
        overall_highest=('2024-01', 'S', 10.0),
    )
    row = json.loads(CompareResultSnapshotService.serialize_results([result]))[0]
    # 有采购记录但无 product_name 时，名称列留空，不显示未匹配
    assert row['product_name'] == ''


def main():
    test_serialize_structure_and_extremes()
    test_serialize_month_records_preserved()
    test_all_records_aggregated_desc()
    test_empty_results_and_no_records_row()
    test_product_name_falls_back_empty_when_has_month_records()
    print('全部快照序列化测试通过（5/5）')


if __name__ == '__main__':
    main()
