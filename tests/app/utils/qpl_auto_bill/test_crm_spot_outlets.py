# -*- coding:utf-8 -*-
"""
process_crm_spot_quote 出口全覆盖测试

覆盖目标（修复前 6 处静默 continue 不落库导致死循环重跑）：
  1. 无适配品牌 / 无候选产品 → 业务失败落库（FAIL_ADAPT_LIST_EMPTY / FAIL_NO_CANDIDATE）
  2. CRM 响应 None / HTTP 非 200 / JSON 解析失败 / 业务 status 非 200 → 临时错误落库（FAIL_CRM_API_ERROR）
  3. CRM 无现货 → 业务失败落库（FAIL_NO_STOCK）
  4. 成功路径 → crm_quote_items 非空
  5. 单条目异常不中断整轮（记录临时错误后 continue）
  6. processed_item_ids 命中跳过、非报价状态跳过
  7. PART_QUOTE 已报价条目失败同样落库
  8. 奔驰无原厂产品落库退出
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.utils.qpl_auto_bill import auto_submit_part_quote as asp


# ---------------------------------------------------------------------------
# 测试数据构造
# ---------------------------------------------------------------------------

def _detail(item_ids=('i1',), oe='OE-1', status='WAITING_QUOTE', car_type5='宝马520'):
    """构造询价单详情：单个 demand 下多个 item"""
    items = []
    for idx, item_id in enumerate(item_ids):
        items.append({
            'enquiryItemId': item_id,
            'itemOe': f'{oe}-{idx}' if len(item_ids) > 1 else oe,
            'itemName': '机油滤芯',
            'quoteStatus': status,
            'saleCategoryPathId': '/5/123',
            'supplierQuoteItemList': [],
        })
    return {
        'supplierEnquiryNo': 'EN1',
        'tid': 'T1',
        'carBrand': '宝马',
        'carType5': car_type5,
        'supplierEnquiryDemandList': [{'supplierEnquiryItemList': items}],
    }


def _adapt(brand_name='博世滤清', brand_type='副厂', products=None):
    """构造适配列表响应"""
    if products is None:
        products = [{'pid': 'P1', 'partNo': 'PN-001'}]
    return {'data': {'brandList': [{
        'brandName': brand_name,
        'brandTypeDesc': brand_type,
        'productList': products,
    }]}}


def _crm_ok(products=None):
    """构造 CRM 成功响应"""
    if products is None:
        products = [{
            'brand_name': '博世滤清', 'brand_code': 'PN-001', 'frey_no': '',
            'number': 'OE-1', 'qpl_price': '12.5',
        }]
    return {'status': 200, 'data': {'data': [{'child': products}]}}


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, json_error=None):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._json_data


class FakeSpider:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get_product_product_list(self, numberlist=None, is_stock=None):
        self.calls.append(numberlist)
        if self.error is not None:
            raise self.error
        return self.response


def _patch_happy_chain(monkeypatch, adapt=None, response=None, spider=None):
    """打桩公共依赖：适配列表 + CRM spider + 品牌映射 + priceCheck"""
    monkeypatch.setattr(asp, 'CRM_SPIDER_AVAILABLE', True)
    monkeypatch.setattr(asp, 'get_adapt_product_brand',
                        lambda *a, **k: adapt if adapt is not None else _adapt())
    monkeypatch.setattr(asp, 'get_crm_brand_names', lambda name, desc: [name])
    monkeypatch.setattr(asp, '_run_price_check', lambda *a, **k: ({'snap': True}, None))
    monkeypatch.setattr(asp, 'construct_crm_quote_item', lambda *a, **k: {'quote': 'item'})
    spider = spider or FakeSpider(response=response if response is not None
                                  else FakeResponse(json_data=_crm_ok()))
    monkeypatch.setattr(asp, '_get_crm_spider', lambda company='fsbbr': spider)
    return spider


# ---------------------------------------------------------------------------
# 业务失败出口（不重试）
# ---------------------------------------------------------------------------

def test_no_adapt_brands_records_business_failure(monkeypatch):
    """无适配品牌 → FAIL_ADAPT_LIST_EMPTY 落库，且不调用 CRM 接口"""
    spider = _patch_happy_chain(monkeypatch, adapt={'data': {'brandList': []}})

    _, _, failed, _, _, traces = asp.process_crm_spot_quote(_detail(), 'fsbbr')

    assert failed['i1'][0] == asp.FAIL_ADAPT_LIST_EMPTY
    assert spider.calls == []  # 未触达 CRM 接口
    assert traces[0]['flow_status'] == '失败'


def test_no_candidates_records_business_failure(monkeypatch):
    """适配品牌无产品列表 → FAIL_NO_CANDIDATE 落库"""
    _patch_happy_chain(monkeypatch, adapt=_adapt(products=[]))

    _, _, failed, _, _, _ = asp.process_crm_spot_quote(_detail(), 'fsbbr')

    assert failed['i1'][0] == asp.FAIL_NO_CANDIDATE


def test_all_pids_already_quoted_records_failure(monkeypatch):
    """候选 pid 全部已在询价详情中 → FAIL_NO_CANDIDATE"""
    _patch_happy_chain(monkeypatch, adapt=_adapt(products=[{'pid': 'P1', 'partNo': 'PN-001'}]))
    detail = _detail()
    detail['supplierEnquiryDemandList'][0]['supplierEnquiryItemList'][0][
        'supplierQuoteItemList'] = [{'pid': 'P1'}]

    _, _, failed, _, _, _ = asp.process_crm_spot_quote(detail, 'fsbbr')

    assert failed['i1'][0] == asp.FAIL_NO_CANDIDATE


def test_no_crm_products_records_no_stock(monkeypatch):
    """CRM 返回无现货产品 → FAIL_NO_STOCK 落库"""
    _patch_happy_chain(monkeypatch, response=FakeResponse(
        json_data={'status': 200, 'data': {'data': []}}))

    _, _, failed, _, _, _ = asp.process_crm_spot_quote(_detail(), 'fsbbr')

    assert failed['i1'][0] == asp.FAIL_NO_STOCK


# ---------------------------------------------------------------------------
# 临时错误出口（冷却后可重试）
# ---------------------------------------------------------------------------

def test_crm_response_none_records_temporary(monkeypatch):
    """CRM 返回 None（超时）→ FAIL_CRM_API_ERROR 临时错误落库"""
    _patch_happy_chain(monkeypatch, spider=FakeSpider(response=None))

    _, _, failed, _, _, _ = asp.process_crm_spot_quote(_detail(), 'fsbbr')

    assert failed['i1'][0] == asp.FAIL_CRM_API_ERROR


def test_crm_http_error_records_temporary(monkeypatch):
    """HTTP 非 200 → FAIL_CRM_API_ERROR 临时错误落库"""
    _patch_happy_chain(monkeypatch, response=FakeResponse(status_code=500, json_data={}))

    _, _, failed, _, _, _ = asp.process_crm_spot_quote(_detail(), 'fsbbr')

    assert failed['i1'][0] == asp.FAIL_CRM_API_ERROR


def test_crm_bad_json_records_temporary(monkeypatch):
    """JSON 解析失败 → FAIL_CRM_API_ERROR 临时错误落库"""
    _patch_happy_chain(monkeypatch, response=FakeResponse(json_error=ValueError('bad json')))

    _, _, failed, _, _, _ = asp.process_crm_spot_quote(_detail(), 'fsbbr')

    assert failed['i1'][0] == asp.FAIL_CRM_API_ERROR


def test_crm_business_status_error_records_temporary(monkeypatch):
    """业务 status 非 200（如 cookie 失效 401）→ FAIL_CRM_API_ERROR"""
    _patch_happy_chain(monkeypatch, response=FakeResponse(json_data={'status': 401}))

    _, _, failed, _, _, _ = asp.process_crm_spot_quote(_detail(), 'fsbbr')

    assert failed['i1'][0] == asp.FAIL_CRM_API_ERROR


def test_item_exception_isolated_and_retryable(monkeypatch):
    """单条目内部异常不抛出中断整轮：记录临时错误后 continue"""
    # CRM 返回完整产品数据，保证走到品牌匹配循环
    _patch_happy_chain(monkeypatch)

    def broken_brand_map(name, desc):
        raise RuntimeError('映射配置炸了')

    monkeypatch.setattr(asp, 'get_crm_brand_names', broken_brand_map)

    # 不应抛出异常
    _, _, failed, _, _, _ = asp.process_crm_spot_quote(_detail(), 'fsbbr')
    assert failed['i1'][0] == asp.FAIL_CRM_API_ERROR


# ---------------------------------------------------------------------------
# 成功路径
# ---------------------------------------------------------------------------

def test_success_path_produces_quote_items(monkeypatch):
    """品牌+partNo+价格全部命中且 priceCheck 通过 → 产出报价项"""
    _patch_happy_chain(monkeypatch)

    quote_items, original_ids, failed, _, _, traces = \
        asp.process_crm_spot_quote(_detail(), 'fsbbr')

    assert 'i1' in quote_items
    assert quote_items['i1'] == [{'quote': 'item'}]
    assert failed == {}
    assert traces[0]['flow_status'] == '成功'


def test_success_price_rounded_up(monkeypatch):
    """qpl_price 12.5 → 向上取整 13 传给 priceCheck（快照断言）"""
    captured = {}

    def fake_price_check(product, product_info, tid, car_brand,
                         enquiry_no, enquiry_item_id, company):
        captured['price'] = product_info['sell_price']
        return {'snap': True}, None

    monkeypatch.setattr(asp, 'CRM_SPIDER_AVAILABLE', True)
    monkeypatch.setattr(asp, 'get_adapt_product_brand', lambda *a, **k: _adapt())
    monkeypatch.setattr(asp, 'get_crm_brand_names', lambda name, desc: [name])
    monkeypatch.setattr(asp, '_run_price_check', fake_price_check)
    monkeypatch.setattr(asp, 'construct_crm_quote_item', lambda *a, **k: {'quote': 'item'})
    monkeypatch.setattr(asp, '_get_crm_spider',
                        lambda company='fsbbr': FakeSpider(FakeResponse(json_data=_crm_ok())))

    asp.process_crm_spot_quote(_detail(), 'fsbbr')

    assert captured['price'] == 13  # math.ceil(12.5)


# ---------------------------------------------------------------------------
# 跳过类出口（不产生记录）
# ---------------------------------------------------------------------------

def test_processed_item_is_skipped(monkeypatch):
    """processed_item_ids 命中 → 直接跳过，不调用适配接口与 CRM 接口"""
    spider = _patch_happy_chain(monkeypatch)
    adapt_calls = []
    monkeypatch.setattr(asp, 'get_adapt_product_brand',
                        lambda *a, **k: adapt_calls.append(1) or _adapt())

    quote_items, _, failed, _, _, traces = asp.process_crm_spot_quote(
        _detail(), 'fsbbr', processed_item_ids={('EN1', 'i1')})

    assert quote_items == {}
    assert failed == {}
    assert traces == []
    assert spider.calls == []
    assert adapt_calls == []


def test_non_waiting_status_is_skipped(monkeypatch):
    """非报价状态（如已关闭）跳过处理"""
    spider = _patch_happy_chain(monkeypatch)

    _, _, failed, _, _, traces = asp.process_crm_spot_quote(
        _detail(status='CLOSED'), 'fsbbr')

    assert failed == {}
    assert traces == []
    assert spider.calls == []


def test_part_quote_failure_also_recorded(monkeypatch):
    """PART_QUOTE 已报价条目失败同样落库（修复前已报价条目失败不记录）"""
    _patch_happy_chain(monkeypatch, adapt={'data': {'brandList': []}})

    _, _, failed, _, _, _ = asp.process_crm_spot_quote(
        _detail(status='PART_QUOTE'), 'fsbbr')

    assert failed['i1'][0] == asp.FAIL_ADAPT_LIST_EMPTY


def test_brand_matched_but_no_effective_price(monkeypatch):
    """品牌+partNo 命中但无有效价格 → FAIL_NO_EFFECTIVE_PRICE（推进最远失败阶段）"""
    crm_products = [{
        'brand_name': '博世滤清', 'brand_code': 'PN-001', 'frey_no': '',
        'number': 'OE-1', 'qpl_price': '',  # 无有效价格
    }]
    _patch_happy_chain(monkeypatch, response=FakeResponse(json_data=_crm_ok(crm_products)))

    _, _, failed, brand_names, _, traces = asp.process_crm_spot_quote(_detail(), 'fsbbr')

    assert failed['i1'][0] == asp.FAIL_NO_EFFECTIVE_PRICE
    assert brand_names.get('i1') == '博世滤清'
    assert traces[0]['fail_stage'] == '价格校验'


# ---------------------------------------------------------------------------
# 奔驰出口
# ---------------------------------------------------------------------------

def test_mercedes_no_original_records_failure(monkeypatch):
    """奔驰适配校验失败（无原厂产品）→ 落库退出，不再每轮死循环重跑"""
    monkeypatch.setattr(asp, 'MERCEDES_SERVICE_AVAILABLE', True)
    monkeypatch.setattr(asp, '_validate_adapt_list',
                        lambda *a, **k: (None, asp.FAIL_NO_ORIGINAL_PRODUCT))

    result = asp.process_mercedes_order(_detail(car_type5='奔驰C260'), 'fsbbr')

    quote_items, summary, failed_items, failed_brand_names, _, traces = result
    assert failed_items['i1'] == asp.FAIL_NO_ORIGINAL_PRODUCT
    assert failed_brand_names['i1'] == '无原厂'
    assert quote_items == {}
    assert traces[0]['flow_status'] == '失败'


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
