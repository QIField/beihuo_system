# -*- coding:utf-8 -*-
"""
轮次异常隔离测试（三级隔离 + 状态异常落库）

覆盖目标：
  1. 公司级隔离：单个公司处理异常 → 全 0 默认统计，其余公司继续
  2. 落库级隔离：单个订单保存失败 → 其余订单仍落库、统计不丢
  3. 订单级隔离：单个订单处理异常 → 跳过继续处理本轮其余订单
  4. 状态异常条目：PART_QUOTE 无报价 → 按业务失败明细落库（下轮跳过，不再死循环）
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.services import qpl_quote_service as qs
from app.utils.qpl_auto_bill import auto_submit_part_quote as asp


def _result_dict(enquiry_no, success=True):
    return {
        'enquiry_no': enquiry_no,
        'order_category': 'A',
        'success': success,
        'message': 'ok' if success else 'bad',
    }


def _order(enquiry_no):
    """A 类订单：无 WAITING_QUOTE 条目（classify_order → 'A'）"""
    return {
        'supplierEnquiryNo': enquiry_no,
        'carType5': '奥迪A6',
        'supplierEnquiryDemandList': [{
            'supplerDemandId': 'D1',
            'supplierEnquiryItemList': [{
                'enquiryItemId': 'i1',
                'itemOe': 'OE-1',
                'quoteStatus': 'PART_QUOTE',
                'supplierQuoteItemList': [],
            }],
        }],
    }


# ---------------------------------------------------------------------------
# 公司级隔离
# ---------------------------------------------------------------------------

def test_company_isolation(monkeypatch):
    """第一个公司异常 → 全 0 默认统计，第二个公司正常处理"""
    monkeypatch.setattr(qs, 'get_supported_companies', lambda: ['c1', 'c2'])

    def fake_company(company, begin_date=None, end_date=None):
        if company == 'c1':
            raise RuntimeError('c1 处理炸了')
        return {
            'company': company, 'success_count': 1, 'fail_count': 0,
            'total': 1, 'category_a': 1, 'category_b': 0, 'category_c': 0,
        }

    monkeypatch.setattr(qs, 'process_and_save_quotes_for_company', fake_company)

    results = qs.process_and_save_quotes_for_all_companies()

    assert len(results) == 2
    assert results[0]['company'] == 'c1'
    assert results[0]['total'] == 0  # 异常公司返回全 0 默认
    assert results[1]['company'] == 'c2'
    assert results[1]['success_count'] == 1


# ---------------------------------------------------------------------------
# 落库级隔离
# ---------------------------------------------------------------------------

def test_persist_isolation(monkeypatch):
    """第一个订单落库失败 → 第二个订单仍落库，统计两个订单都计数"""
    monkeypatch.setattr(qs, 'submit_all_quotes', lambda *a, **k: [
        _result_dict('EN1', success=True),
        _result_dict('EN2', success=False),
    ])

    persist_calls = []

    def fake_persist(result, company):
        persist_calls.append(result['enquiry_no'])
        if result['enquiry_no'] == 'EN1':
            raise RuntimeError('EN1 落库炸了')

    monkeypatch.setattr(qs, '_persist_order_result', fake_persist)

    summary = qs.process_and_save_quotes_for_company('fsbbr')

    assert persist_calls == ['EN1', 'EN2']  # EN1 失败后 EN2 仍尝试落库
    assert summary['total'] == 2
    assert summary['success_count'] == 1
    assert summary['fail_count'] == 1


# ---------------------------------------------------------------------------
# 订单级隔离
# ---------------------------------------------------------------------------

def test_order_isolation(monkeypatch):
    """第一个订单详情拉取异常 → 跳过该订单，第二个订单正常提交"""
    monkeypatch.setattr(
        asp, 'query_enquiry_list',
        lambda *a, **k: {'data': [_order('EN1'), _order('EN2')]}
    )
    monkeypatch.setattr(asp, '_filter_processed_orders', lambda *a, **k: (set(), {}))

    def fake_detail(enquiry_no, company=None):
        if enquiry_no == 'EN1':
            raise RuntimeError('EN1 详情拉取炸了')
        return {'data': _order(enquiry_no)}

    monkeypatch.setattr(asp, 'get_enquiry_detail', fake_detail)

    def fake_handler(detail_data, company, processed_item_ids=None):
        return {
            'category': 'A',
            'extra_quote_items': {},
            'summary_list': [],
            'failed_items': {},
        }

    monkeypatch.setattr(asp, 'ORDER_HANDLERS', {'A': fake_handler})
    monkeypatch.setattr(asp, 'construct_quote_request', lambda *a, **k: {'req': 1})
    monkeypatch.setattr(asp, 'submit_quote', lambda *a, **k: {'code': 10000, 'message': '提交成功'})

    results = asp.submit_all_quotes('2026-11-15', '2026-11-17', company='fsbbr')

    assert len(results) == 1
    assert results[0]['enquiry_no'] == 'EN2'
    assert results[0]['success'] is True


def test_order_isolation_handler_error(monkeypatch):
    """handler 内部异常 → 该订单跳过，不中断本轮"""
    monkeypatch.setattr(
        asp, 'query_enquiry_list',
        lambda *a, **k: {'data': [_order('EN1'), _order('EN2')]}
    )
    monkeypatch.setattr(asp, '_filter_processed_orders', lambda *a, **k: (set(), {}))
    monkeypatch.setattr(asp, 'get_enquiry_detail',
                        lambda enquiry_no, company=None: {'data': _order(enquiry_no)})

    calls = []

    def fake_handler(detail_data, company, processed_item_ids=None):
        calls.append(detail_data['supplierEnquiryNo'])
        if detail_data['supplierEnquiryNo'] == 'EN1':
            raise RuntimeError('handler 炸了')
        return {'category': 'A', 'extra_quote_items': {}, 'summary_list': [], 'failed_items': {}}

    monkeypatch.setattr(asp, 'ORDER_HANDLERS', {'A': fake_handler})
    monkeypatch.setattr(asp, 'construct_quote_request', lambda *a, **k: {'req': 1})
    monkeypatch.setattr(asp, 'submit_quote', lambda *a, **k: {'code': 10000, 'message': '提交成功'})

    results = asp.submit_all_quotes('2026-11-15', '2026-11-17', company='fsbbr')

    assert calls == ['EN1', 'EN2']  # 两个订单都尝试了
    assert len(results) == 1
    assert results[0]['enquiry_no'] == 'EN2'


# ---------------------------------------------------------------------------
# 状态异常条目落库
# ---------------------------------------------------------------------------

def test_status_abnormal_item_saved_as_failure():
    """PART_QUOTE 条目无报价 → 按业务失败明细落库，下轮按已处理跳过"""
    demand_list = [{
        'supplerDemandId': 'D1',
        'supplierEnquiryItemList': [{
            'enquiryItemId': 'i1',
            'itemOe': 'OE-1',
            'quoteStatus': 'PART_QUOTE',
            'supplierQuoteItemList': [],
        }],
    }]

    details = qs._collect_item_details(
        demand_list, extra_quote_items={}, failed_items={},
        failed_brand_names={}, failed_item_prices={},
        failure_categories={}, retry_counts={},
        enquiry_no='EN1', company='fsbbr'
    )

    assert len(details) == 1
    assert details[0]['_has_quote'] is False
    assert details[0]['_failure_reason'] == '状态异常(PART_QUOTE)'


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
