# -*- coding:utf-8 -*-
"""
汽配龙自动报价重构 · 阶段三单元测试

覆盖目标：
  1. quote_builder.normalize_quote_item：新格式调整（QUOTED/AUTO_QUOTE/空 quoteExtraInfoVo/移除废弃字段），
     已有报价项（带 supplierQuoteItemId）原样透传
  2. quote_builder.build_submit_request：PAGE_QUOTE 顶层格式、已有报价保留、新报价追加
  3. pipeline 状态过滤与落库分流：
     - 本地终态/冷却中明细跳过
     - 提交成功 → quoted + attempt 成功
     - 匹配失败 → failed_biz（确定性不重试）
     - 提交失败 → failed_temp（冷却重试）
     - 宝马订单跳过不落终态
  4. enquiry_api.get_enquiry_detail_all：PAGE 分页合并
"""

import os
import sys
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from app.services.qpl_auto_quote import quote_builder as qb
from app.services.qpl_auto_quote import pipeline as pl
from app.services.qpl_auto_quote import matcher as mt
from app.services.qpl_auto_quote.constants import QUOTE_TYPE_PAGE_QUOTE


# ---------------------------------------------------------------------------
# quote_builder
# ---------------------------------------------------------------------------

def _new_built_quote_item():
    """模拟旧匹配链 construct_crm_quote_item 的产出"""
    return {
        "brandId": 7885, "brandName": "菲尔/FREY", "deliveryAging": 1,
        "itemQuality": 2, "itemSellPrice": 80, "partsNo": "",
        "supplierQuoteItemId": None, "pid": "QCJ-FREY-X|1",
        "quoteTaxType": "INCLUSIVE",
        "quoteExtraInfoVo": {"originTire": None},
        "priceCheckSnapshot": {"checkResult": "SUCCESS"},
        "quoteStatus": "WAITING_QUOTE",
        "pidSrcList": ["A"], "checkPriceSrc": None, "productList": [],
    }


def test_normalize_quote_item_new_format():
    item = qb.normalize_quote_item(_new_built_quote_item())

    assert item['quoteStatus'] == 'QUOTED'
    assert item['quoteMethod'] == 'AUTO_QUOTE'
    assert item['quoteExtraInfoVo'] == {}
    for removed in ('pidSrcList', 'checkPriceSrc', 'productList'):
        assert removed not in item
    assert item['brandName'] == '菲尔/FREY'      # 业务字段保留
    assert item['priceCheckSnapshot'] is not None


def test_normalize_quote_item_existing_quote_passthrough():
    """已有报价项（服务端分配 ID）整项透传，quoteExtraInfoVo 不清空"""
    existing = {
        "brandName": "曼克马利", "supplierQuoteItemId": 8082024013,
        "quoteExtraInfoVo": {"supplierProductSrc": "ERP_SUPPLIER", "source": "ERP"},
        "quoteStatus": "QUOTED",
    }
    item = qb.normalize_quote_item(existing)

    assert item == existing  # 原样透传
    assert item['quoteExtraInfoVo'] == {"supplierProductSrc": "ERP_SUPPLIER", "source": "ERP"}


def _make_detail(items):
    """构造 detail_data：items = [(item_id, quote_status, existing_quotes)]"""
    item_list = []
    for item_id, status, quotes in items:
        item_list.append({
            "enquiryItemId": item_id, "quoteStatus": status,
            "itemOe": f"OE{item_id}", "itemName": f"件{item_id}",
            "supplierQuoteItemList": quotes,
        })
    return {
        "supplierEnquiryNo": "SIQR001", "supplierEnquiryDemandList": [
            {"supplerDemandId": 9001, "supplierEnquiryItemList": item_list}
        ],
    }


def test_build_submit_request_page_quote_format():
    detail = _make_detail([(1, 'PART_QUOTE', [{"brandName": "宝马", "supplierQuoteItemId": 1}])])
    detail.update({'pickUpWay': 2, 'pickUpWayStr': '物流配送', 'deliveryAddress': '广东 佛山'})
    extra = {1: [_new_built_quote_item()]}

    request = qb.build_submit_request(detail, extra)

    assert request['quoteType'] == QUOTE_TYPE_PAGE_QUOTE
    assert request['channel'] == 'S_STATION'
    assert request['supplierEnquiryNo'] == 'SIQR001'
    # 实测接口校验"配送方式为空"，顶层配送三字段必须保留
    assert request['pickUpWay'] == 2
    assert request['pickUpWayStr'] == '物流配送'
    assert request['deliveryAddress'] == '广东 佛山'

    item = request['demandList'][0]['enquiryItemList'][0]
    assert item['supplierEnquiryItemId'] == 1
    assert len(item['quoteItemList']) == 2          # 已有报价 + 新报价
    assert item['quoteItemList'][0]['supplierQuoteItemId'] == 1   # 已有项在前
    assert item['quoteItemList'][1]['quoteMethod'] == 'AUTO_QUOTE'  # 新项在后


def test_build_submit_request_waiting_without_quote_keeps_empty_list():
    detail = _make_detail([(2, 'WAITING_QUOTE', [])])

    request = qb.build_submit_request(detail, {})

    item = request['demandList'][0]['enquiryItemList'][0]
    assert item['quoteItemList'] == []
    assert item['quoteStatus'] == 'WAITING_QUOTE'


# ---------------------------------------------------------------------------
# pipeline：状态过滤 + 落库分流
# ---------------------------------------------------------------------------

class Recorder:
    """记录 persistence 调用"""
    def __init__(self):
        self.calls = []

    def __contains__(self, name):
        return name in [c[0] for c in self.calls]


def _patch_pipeline(monkeypatch, local_statuses=None, match_result=None, submit_resp=None):
    """mock pipeline 的 persistence / api / matcher 依赖，返回调用记录 dict"""
    calls = {'record_attempt': [], 'mark_quoted': [], 'mark_failed': [],
             'upsert_order': 0, 'upsert_items': 0, 'progress': 0}

    monkeypatch.setattr(pl, 'get_enquiry_detail_all', lambda no, c: _make_detail([
        (101, 'WAITING_QUOTE', []), (102, 'QUOTED', [{"brandName": "宝马"}]),
    ]))
    monkeypatch.setattr(pl, 'upsert_order', lambda c, o: calls.__setitem__('upsert_order', calls['upsert_order'] + 1))
    monkeypatch.setattr(pl, 'upsert_items', lambda c, no, items: calls.__setitem__('upsert_items', calls['upsert_items'] + 1))
    monkeypatch.setattr(pl, 'mark_item_quoted', lambda *a, **k: calls['mark_quoted'].append((a, k)))
    monkeypatch.setattr(pl, 'mark_item_failed',
                        lambda company, item_id, fail_stage, fail_reason, is_temp, **k:
                        calls['mark_failed'].append({'item_id': item_id, 'is_temp': is_temp,
                                                     'stage': fail_stage, 'reason': fail_reason}))
    monkeypatch.setattr(pl, 'record_attempt',
                        lambda company, no, item_id, round_id, action, result, **k:
                        calls['record_attempt'].append({'item_id': item_id, 'action': action,
                                                        'result': result, **k}))
    monkeypatch.setattr(pl, 'update_order_progress', lambda c, no: calls.__setitem__('progress', calls['progress'] + 1))
    monkeypatch.setattr(pl, 'fetch_item_statuses', lambda c, ids: local_statuses or {})
    monkeypatch.setattr(pl, 'match_order_by_brand', lambda d, c, skip_item_ids=None: match_result)
    monkeypatch.setattr(pl, 'submit_enquiry_page', lambda dl, no, c: submit_resp)
    return calls


_QUOTED_MATCH = {
    'extra_quote_items': {101: [_new_built_quote_item()]},
    'failed_items': {103: 'CRM未匹配'},
    'failed_brand_names': {}, 'quote_item_ids': {101}, 'category': 'A',
}


def test_pipeline_submit_success_marks_quoted_and_biz_failed(monkeypatch):
    calls = _patch_pipeline(monkeypatch, match_result=_QUOTED_MATCH,
                            submit_resp={'code': 10000, 'data': True})

    submitted = pl.process_order('fsbbr', 'SIQR001', 'r1')

    assert submitted is True
    # 101 报价成功落 quoted；103 匹配失败落 failed_biz（确定性，不重试）
    assert any(k[1] == 101 for k, kw in calls['mark_quoted'])
    failed_103 = [f for f in calls['mark_failed'] if f['item_id'] == 103]
    assert failed_103 and failed_103[0]['is_temp'] is False
    # 102（详情中已 QUOTED）同步为已有报价
    assert any(k[1] == 102 and kw.get('quote_source') == '已有报价'
               for k, kw in calls['mark_quoted'])


def test_pipeline_submit_fail_marks_temp(monkeypatch):
    calls = _patch_pipeline(monkeypatch, match_result=_QUOTED_MATCH,
                            submit_resp={'code': 500, 'message': '系统繁忙'})

    submitted = pl.process_order('fsbbr', 'SIQR001', 'r1')

    assert submitted is False
    failed = {f['item_id']: f for f in calls['mark_failed']}
    assert failed[101]['is_temp'] is True                     # 临时失败走冷却
    assert '提交失败' in failed[101]['reason']
    # attempt 含 submit 失败流水 + 快照
    submit_attempts = [a for a in calls['record_attempt'] if a['action'] == 'submit']
    assert submit_attempts and submit_attempts[0]['result'] == '失败'


def test_pipeline_part_quote_item_enters_target(monkeypatch):
    """PART_QUOTE 明细（部分报价，仍有未报完需求）必须进入处理范围，不能静默跳过"""
    match_called = []
    calls = {}
    monkeypatch.setattr(pl, 'get_enquiry_detail_all', lambda no, c: _make_detail(
        [(101, 'PART_QUOTE', [{"supplierQuoteItemId": "sq1", "brandName": "菲尔"}])]))
    monkeypatch.setattr(pl, 'upsert_order', lambda c, o: None)
    monkeypatch.setattr(pl, 'upsert_items', lambda c, no, items: None)
    monkeypatch.setattr(pl, 'mark_item_quoted', lambda *a, **k: calls.setdefault('q', []).append(a))
    monkeypatch.setattr(pl, 'mark_item_failed', lambda *a, **k: calls.setdefault('f', []).append(a))
    monkeypatch.setattr(pl, 'record_attempt', lambda *a, **k: None)
    monkeypatch.setattr(pl, 'update_order_progress', lambda c, no: None)
    monkeypatch.setattr(pl, 'fetch_item_statuses', lambda c, ids: {})
    monkeypatch.setattr(pl, 'match_order_by_brand',
                        lambda d, c, skip_item_ids=None: match_called.append(1) or
                        {'extra_quote_items': {}, 'failed_items': {}, 'failed_brand_names': {},
                         'quote_item_ids': set(), 'category': 'A'})
    monkeypatch.setattr(pl, 'submit_enquiry_page', lambda dl, no, c: {'code': 10000})

    submitted = pl.process_order('fsbbr', 'SIQR001', 'r1')

    assert submitted is True
    assert match_called                     # 未在 P2 提前 return，进入了匹配
    assert not calls.get('f')               # PART_QUOTE 明细未被误落失败


def test_pipeline_skips_terminal_and_cooling_items(monkeypatch):
    local = {
        101: {'status': 'failed_biz', 'next_retry_time': None},
        102: {'status': 'quoted', 'next_retry_time': None},
    }
    calls = _patch_pipeline(monkeypatch, local_statuses=local,
                            match_result={'extra_quote_items': {}, 'failed_items': {},
                                          'failed_brand_names': {}, 'quote_item_ids': set(),
                                          'category': 'A'},
                            submit_resp={'code': 10000})

    pl.process_order('fsbbr', 'SIQR001', 'r1')

    # 101 本地终态 → 无任何失败落库；mark_quoted 仅剩 102 的已有报价同步
    assert calls['mark_failed'] == []
    quoted_ids = {k[1] for k, kw in calls['mark_quoted']}
    assert quoted_ids == {102}


def test_pipeline_unknown_brand_skipped_without_terminal(monkeypatch):
    """车辆品牌无法识别：明细保持 pending，只留跳过流水，不触发提交"""
    monkeypatch.setattr(pl, 'get_enquiry_detail_all', lambda no, c: _make_detail([
        (201, 'WAITING_QUOTE', []),
    ]))
    monkeypatch.setattr(pl, 'upsert_order', lambda c, o: None)
    monkeypatch.setattr(pl, 'upsert_items', lambda c, no, items: None)
    monkeypatch.setattr(pl, 'update_order_progress', lambda c, no: None)
    monkeypatch.setattr(pl, 'fetch_item_statuses', lambda c, ids: {})
    monkeypatch.setattr(pl, 'match_order_by_brand', lambda d, c, skip_item_ids=None: None)
    monkeypatch.setattr(pl, 'submit_enquiry_page',
                        lambda dl, no, c: (_ for _ in ()).throw(AssertionError('跳过不应触发提交')))
    calls = {'failed': [], 'attempts': []}
    monkeypatch.setattr(pl, 'mark_item_failed',
                        lambda company, i, fail_stage, fail_reason, is_temp, **k:
                        calls['failed'].append(i))
    monkeypatch.setattr(pl, 'record_attempt',
                        lambda company, no, i, r, action, result, **k:
                        calls['attempts'].append({'item_id': i, 'action': action, 'result': result}))

    submitted = pl.process_order('fsbbr', 'SIQR001', 'r1')

    assert submitted is False
    assert calls['failed'] == []                        # 跳过不落终态
    assert calls['attempts'][0]['result'] == '跳过'      # attempt 留跳过流水
    assert calls['attempts'][0]['action'] == 'match'


def test_pipeline_bmw_ensures_oes_before_match(monkeypatch):
    """宝马订单：匹配前必须先调用 OE 补齐，且跳过项不参与补 OE"""
    calls = {'ensure': []}
    detail = _make_detail([(301, 'WAITING_QUOTE', [])])
    detail['carBrand'] = '宝马'
    monkeypatch.setattr(pl, 'get_enquiry_detail_all', lambda no, c: detail)
    monkeypatch.setattr(pl, 'upsert_order', lambda c, o: None)
    monkeypatch.setattr(pl, 'upsert_items', lambda c, no, items: None)
    monkeypatch.setattr(pl, 'update_order_progress', lambda c, no: None)
    monkeypatch.setattr(pl, 'fetch_item_statuses', lambda c, ids: {})
    monkeypatch.setattr(pl, 'ensure_bmw_oes_for_order',
                        lambda d, c, skip_item_ids=None: calls['ensure'].append(dict(skip=skip_item_ids)))
    monkeypatch.setattr(pl, 'match_order_by_brand',
                        lambda d, c, skip_item_ids=None: {'extra_quote_items': {}, 'failed_items': {},
                                                          'failed_brand_names': {},
                                                          'quote_item_ids': set(), 'category': 'C'})
    monkeypatch.setattr(pl, 'submit_enquiry_page', lambda dl, no, c: {'code': 10000})
    monkeypatch.setattr(pl, 'mark_item_failed', lambda *a, **k: None)
    monkeypatch.setattr(pl, 'record_attempt', lambda *a, **k: None)
    monkeypatch.setattr(pl, 'mark_item_quoted', lambda *a, **k: None)

    pl.process_order('fsbbr', 'SIQR001', 'r1')

    assert calls['ensure'] == [{'skip': set()}]         # OE 补齐先于匹配执行


def test_pipeline_fills_pickup_info(monkeypatch):
    """有 shopUid 时调取货方式接口并合入详情；接口异常不阻断流水线"""
    detail = _make_detail([(401, 'WAITING_QUOTE', [])])
    detail['shopUid'] = 'SHOP1'
    captured = {}

    def fake_pickup(shop_uid, enquiry_no, tuhu_supplier_id, company):
        captured.update(shop_uid=shop_uid, company=company)
        return {'code': 10000, 'data': {'supplierPropertyPickUpWayInfo': {
                    'defaultPickUpWay': {'pickUpWay': 2, 'pickUpWayStr': '物流配送'}},
                    'shopProvinceName': '广东', 'shopCityName': '佛山'}}

    import app.utils.qpl_auto_bill.enquiry_api as old_api
    monkeypatch.setattr(old_api, 'get_pickup_way_and_distance', fake_pickup)
    monkeypatch.setattr(pl, 'get_enquiry_detail_all', lambda no, c: detail)
    monkeypatch.setattr(pl, 'upsert_order', lambda c, o: None)
    monkeypatch.setattr(pl, 'upsert_items', lambda c, no, items: None)
    monkeypatch.setattr(pl, 'update_order_progress', lambda c, no: None)
    monkeypatch.setattr(pl, 'fetch_item_statuses', lambda c, ids: {})
    monkeypatch.setattr(pl, 'match_order_by_brand',
                        lambda d, c, skip_item_ids=None: {'extra_quote_items': {}, 'failed_items': {},
                                                          'failed_brand_names': {},
                                                          'quote_item_ids': set(), 'category': 'A'})
    monkeypatch.setattr(pl, 'submit_enquiry_page', lambda dl, no, c: {'code': 10000})
    monkeypatch.setattr(pl, 'mark_item_failed', lambda *a, **k: None)
    monkeypatch.setattr(pl, 'record_attempt', lambda *a, **k: None)
    monkeypatch.setattr(pl, 'mark_item_quoted', lambda *a, **k: None)

    pl.process_order('fsbbr', 'SIQR001', 'r1')

    assert captured['shop_uid'] == 'SHOP1'
    assert detail['pickUpWay'] == 2                     # 配送方式已合入提交体来源
    assert detail['deliveryAddress'] == '广东 佛山'


def test_pipeline_pickup_api_exception_not_fatal(monkeypatch):
    """取货方式接口异常：不阻断流水线，明细照常处理"""
    detail = _make_detail([(402, 'WAITING_QUOTE', [])])
    detail['shopUid'] = 'SHOP2'

    import app.utils.qpl_auto_bill.enquiry_api as old_api
    monkeypatch.setattr(old_api, 'get_pickup_way_and_distance',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('api down')))
    monkeypatch.setattr(pl, 'get_enquiry_detail_all', lambda no, c: detail)
    monkeypatch.setattr(pl, 'upsert_order', lambda c, o: None)
    monkeypatch.setattr(pl, 'upsert_items', lambda c, no, items: None)
    monkeypatch.setattr(pl, 'update_order_progress', lambda c, no: None)
    monkeypatch.setattr(pl, 'fetch_item_statuses', lambda c, ids: {})
    monkeypatch.setattr(pl, 'match_order_by_brand',
                        lambda d, c, skip_item_ids=None: {'extra_quote_items': {402: [_new_built_quote_item()]},
                                                          'failed_items': {}, 'failed_brand_names': {},
                                                          'quote_item_ids': {402}, 'category': 'A'})
    monkeypatch.setattr(pl, 'submit_enquiry_page', lambda dl, no, c: {'code': 10000})
    monkeypatch.setattr(pl, 'record_attempt', lambda *a, **k: None)
    marked = []
    monkeypatch.setattr(pl, 'mark_item_quoted',
                        lambda company, item_id, **k: marked.append(item_id))

    pl.process_order('fsbbr', 'SIQR001', 'r1')

    assert 402 in marked                                # 异常不影响报价主流程


# ---------------------------------------------------------------------------
# matcher
# ---------------------------------------------------------------------------

def test_matcher_routes_by_car_brand(monkeypatch):
    captured = {}

    def fake_handler(detail, company, processed_item_ids=None):
        captured['processed'] = processed_item_ids
        return {'extra_quote_items': {1: []}, 'failed_items': {}, 'failed_brand_names': {},
                'crm_quote_item_ids': {1}, 'bc_quote_item_ids': set(),
                'category': 'A', 'flow_trace_list': []}

    monkeypatch.setattr(mt, 'handle_category_a', fake_handler)
    result = mt.match_order_by_brand({'carBrand': '丰田'}, 'fsbbr', skip_item_ids={9})

    assert result['category'] == 'A'
    assert result['quote_item_ids'] == {1}
    assert captured['processed'] == {9}   # skip 集合传入旧处理器


def test_matcher_bmw_routes_to_category_c(monkeypatch):
    captured = {}

    def fake_c_handler(detail, company, processed_item_ids=None):
        captured['company'] = company
        return {'extra_quote_items': {5: []}, 'failed_items': {}, 'failed_brand_names': {},
                'crm_quote_item_ids': set(), 'bc_quote_item_ids': {5},
                'category': 'C', 'flow_trace_list': []}

    monkeypatch.setattr(mt, 'handle_category_c', fake_c_handler)
    result = mt.match_order_by_brand({'carBrand': '宝马'}, 'fsbbr', skip_item_ids={7})

    assert result['category'] == 'C'
    assert result['quote_item_ids'] == {5}
    assert captured['company'] == 'fsbbr'


def test_matcher_extract_summary():
    summary = mt.extract_quote_summary({'brandName': '菲尔/FREY', 'itemSellPrice': 80,
                                        'deliveryAging': 1, 'partsNo': '', 'itemQuality': 2})
    assert summary == {'matched_brand': '菲尔/FREY', 'item_sell_price': 80,
                       'delivery_aging': 1, 'parts_no': '', 'item_quality': 2}


# ---------------------------------------------------------------------------
# enquiry_api：PAGE 分页合并
# ---------------------------------------------------------------------------

def test_get_enquiry_detail_all_merges_pages(monkeypatch):
    from app.services.qpl_auto_quote import enquiry_api as ea

    pages = [
        {'code': 10000, 'data': {'supplierEnquiryNo': 'SIQR001', 'tid': '103365',
                                 'supplierEnquiryDemandList': [
                                     {'supplerDemandId': 1, 'supplierEnquiryItemList': [{'enquiryItemId': i} for i in range(20)]}]}},
        {'code': 10000, 'data': {'supplierEnquiryNo': 'SIQR001',
                                 'supplierEnquiryDemandList': [
                                     {'supplerDemandId': 1, 'supplierEnquiryItemList': [{'enquiryItemId': 100}]}]}},
        {'code': 10000, 'data': {'supplierEnquiryNo': 'SIQR001',
                                 'supplierEnquiryDemandList': [
                                     {'supplerDemandId': 1, 'supplierEnquiryItemList': []}]}},
    ]
    monkeypatch.setattr(ea, 'get_enquiry_detail_page', lambda no, pno, ps, c: pages[pno - 1])

    detail = ea.get_enquiry_detail_all('SIQR001', 'fsbbr', page_size=20)

    assert detail['tid'] == '103365'
    assert len(detail['supplierEnquiryDemandList']) == 1
    item_ids = [i['enquiryItemId'] for i in detail['supplierEnquiryDemandList'][0]['supplierEnquiryItemList']]
    assert len(item_ids) == 21                      # 第1页20条 + 第2页1条合并
    assert item_ids[0] == 0 and item_ids[-1] == 100


def test_get_enquiry_detail_all_returns_none_on_first_page_fail(monkeypatch):
    from app.services.qpl_auto_quote import enquiry_api as ea
    monkeypatch.setattr(ea, 'get_enquiry_detail_page', lambda *a: {'code': 500})

    assert ea.get_enquiry_detail_all('SIQR001', 'fsbbr') is None
