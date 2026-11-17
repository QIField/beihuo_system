# -*- coding:utf-8 -*-
"""
汽配龙报价失败分类 / 冷却判定 单元测试

覆盖目标：
  1. _classify_failure_reason：priceCheck 归业务错误（不重试）、CRM接口异常/零件信息请求失败归临时错误
  2. _build_failure_metadata：临时错误重试计数递增、达到上限转重试耗尽、业务错误计数为 0
  3. _filter_processed_orders：成功/业务错误/重试耗尽跳过；临时错误冷却期内跳过、冷却到期允许重试；
     DB 异常降级不抛出
"""

import os
import sys
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.utils.qpl_auto_bill.auto_submit_part_quote import (
    FAIL_PRICE_CHECK_FAILED,
    FAIL_CRM_API_ERROR,
    FAIL_OE_DATA_MISSING,
    FAIL_NO_STOCK,
    MAX_RETRY_COUNT,
    COOLDOWN_HOURS,
    FAILURE_CATEGORY_BUSINESS,
    FAILURE_CATEGORY_TEMPORARY,
    FAILURE_CATEGORY_RETRY_EXHAUSTED,
    _classify_failure_reason,
    _build_failure_metadata,
    _filter_processed_orders,
)


# ---------------------------------------------------------------------------
# 失败分类
# ---------------------------------------------------------------------------

def test_price_check_failure_is_business():
    """价格检测失败属于价格问题，归业务错误，不重试"""
    assert _classify_failure_reason(FAIL_PRICE_CHECK_FAILED) == FAILURE_CATEGORY_BUSINESS
    assert _classify_failure_reason(f"{FAIL_PRICE_CHECK_FAILED}: 奔驰 A001: 价格低于门槛") == FAILURE_CATEGORY_BUSINESS


def test_crm_api_error_is_temporary():
    assert _classify_failure_reason(FAIL_CRM_API_ERROR) == FAILURE_CATEGORY_TEMPORARY
    assert _classify_failure_reason(f"{FAIL_CRM_API_ERROR}: status=401") == FAILURE_CATEGORY_TEMPORARY


def test_oe_data_missing_is_temporary():
    assert _classify_failure_reason(FAIL_OE_DATA_MISSING) == FAILURE_CATEGORY_TEMPORARY


def test_business_and_empty_reasons():
    assert _classify_failure_reason(FAIL_NO_STOCK) == FAILURE_CATEGORY_BUSINESS
    assert _classify_failure_reason(None) == FAILURE_CATEGORY_BUSINESS


# ---------------------------------------------------------------------------
# 重试计数
# ---------------------------------------------------------------------------

def test_business_failure_retry_is_zero():
    categories, retries = _build_failure_metadata({'i1': FAIL_NO_STOCK}, 'EN1', {})
    assert categories['i1'] == FAILURE_CATEGORY_BUSINESS
    assert retries['i1'] == 0


def test_temporary_failure_increments_retry():
    categories, retries = _build_failure_metadata({'i1': FAIL_CRM_API_ERROR}, 'EN1', {})
    assert categories['i1'] == FAILURE_CATEGORY_TEMPORARY
    assert retries['i1'] == 1


def test_temporary_failure_exhausts_at_max_retry():
    retry_info = {('EN1', 'i1'): {'retry_count': MAX_RETRY_COUNT - 1, 'fail_type': '临时错误'}}
    categories, retries = _build_failure_metadata({'i1': FAIL_CRM_API_ERROR}, 'EN1', retry_info)
    assert categories['i1'] == FAILURE_CATEGORY_RETRY_EXHAUSTED
    assert retries['i1'] == MAX_RETRY_COUNT


# ---------------------------------------------------------------------------
# 已处理条目加载与冷却判定（DB 打桩）
# ---------------------------------------------------------------------------

class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params):
        self._params = params

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, cursor_class=None):
        return FakeCursor(self._rows)

    def close(self):
        pass


def _row(enquiry_no='EN1', item_id='i1', fail_type='成功', retry=0, minutes_ago=0):
    return {
        'supplier_enquiry_no': enquiry_no,
        'enquiry_item_id': item_id,
        'fail_type': fail_type,
        'retry_count': retry,
        'submit_time': datetime.now() - timedelta(minutes=minutes_ago),
    }


def _load(monkeypatch, rows):
    monkeypatch.setattr(
        'app.utils.database_connection.get_db_connection',
        lambda: FakeConn(rows)
    )
    return _filter_processed_orders({'EN1'}, 'fsbbr', '2026-11-15', '2026-11-17')


def test_success_and_business_items_are_processed(monkeypatch):
    rows = [_row('EN1', 'i1', '成功', 0), _row('EN1', 'i2', '业务错误', 0)]
    processed, retry_info = _load(monkeypatch, rows)
    assert ('EN1', 'i1') in processed
    assert ('EN1', 'i2') in processed
    assert retry_info[('EN1', 'i1')]['fail_type'] == '成功'


def test_temporary_item_in_cooldown_is_skipped(monkeypatch):
    rows = [_row('EN1', 'i1', '临时错误', 1, minutes_ago=30)]
    processed, retry_info = _load(monkeypatch, rows)
    # 冷却期内（COOLDOWN_HOURS 小时内）视为已处理，本轮跳过
    assert ('EN1', 'i1') in processed
    assert retry_info[('EN1', 'i1')]['retry_count'] == 1


def test_temporary_item_after_cooldown_is_retryable(monkeypatch):
    minutes_ago = COOLDOWN_HOURS * 60 + 30
    rows = [_row('EN1', 'i1', '临时错误', 1, minutes_ago=minutes_ago)]
    processed, retry_info = _load(monkeypatch, rows)
    # 冷却到期 → 不算已处理，允许本轮重试
    assert ('EN1', 'i1') not in processed
    assert retry_info[('EN1', 'i1')]['retry_count'] == 1


def test_temporary_item_exhausted_is_processed(monkeypatch):
    minutes_ago = COOLDOWN_HOURS * 60 + 30
    rows = [_row('EN1', 'i1', '临时错误', MAX_RETRY_COUNT, minutes_ago=minutes_ago)]
    processed, _ = _load(monkeypatch, rows)
    assert ('EN1', 'i1') in processed  # 重试耗尽，永久跳过


def test_success_row_wins_over_failure_row(monkeypatch):
    rows = [_row('EN1', 'i1', '临时错误', 1, minutes_ago=1), _row('EN1', 'i1', '成功', 0)]
    processed, retry_info = _load(monkeypatch, rows)
    assert ('EN1', 'i1') in processed
    assert retry_info[('EN1', 'i1')]['fail_type'] == '成功'


def test_db_failure_degrades_gracefully(monkeypatch):
    def broken_conn():
        raise RuntimeError('DB down')

    monkeypatch.setattr('app.utils.database_connection.get_db_connection', broken_conn)
    processed, retry_info = _filter_processed_orders({'EN1'}, 'fsbbr', '2026-11-15', '2026-11-17')
    assert processed == set()
    assert retry_info == {}


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
