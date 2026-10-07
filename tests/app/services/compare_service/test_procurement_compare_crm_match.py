# -*- coding:utf-8 -*-
"""
比价 OE 匹配（CRM numberlist）单元测试

不依赖数据库和真实 CRM 接口：
1. 品牌规则过滤（非目标品牌被丢弃）
2. 原厂 / 原厂国内4s件 互通
3. child 字段映射 + 替换号去重保序拼接
4. numberlist 每次只传单 OE，不拼接逗号
5. 单个 OE 接口失败不影响其他 OE
6. 同 OE 多品牌时品牌集合取并集

运行方式：
    python tests/app/services/compare_service/test_procurement_compare_crm_match.py
"""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..', '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.compare_service import procurement_compare_service as pcs

Service = pcs.ProcurementCompareService


def _child(number, brand, frey_no='', name='', spec='', vehicle='', replace=None,
           stock=None, stock_zaitu=None, safe_stock=None):
    return {
        'number': number,
        'brand_name': brand,
        'frey_no': frey_no,
        'l_name_zh': name,
        'l_model_zh': spec,
        'cass_oebrand_name': vehicle,
        'display_number': [{'number': n} for n in (replace or [])],
        'stock': stock,
        'stock_zaitu': stock_zaitu,
        'safe_stock': safe_stock,
    }


def _api_data(*children):
    return {'data': [{'child': list(children)}]}


def _install_stubs(monkeypatch, oe_data_map, fail_oes=None):
    """安装品牌规则和 CRM 接口桩"""
    fail_oes = fail_oes or set()
    calls = []

    def fake_match_brands(brand, oem_brands=None):
        if brand in ('原厂', '原厂国内4s件'):
            return ['原厂', '原厂国内4s件']
        return [brand]

    def fake_search(company, numberlist):
        calls.append((company, numberlist))
        if numberlist in fail_oes:
            raise RuntimeError('CRM 不可用')
        return oe_data_map.get(numberlist)

    monkeypatch.setattr(Service, '_get_match_brands', staticmethod(fake_match_brands))
    monkeypatch.setattr(pcs, 'search_products_by_numberlist', fake_search)
    return calls


class _MonkeyPatch:
    """极简 monkeypatch 上下文，支持脱离 pytest 直接运行"""

    def __init__(self):
        self._undo = []

    def setattr(self, target, name, value):
        old = getattr(target, name)
        setattr(target, name, value)
        self._undo.append((target, name, old))

    def undo(self):
        for target, name, old in reversed(self._undo):
            setattr(target, name, old)
        self._undo.clear()


def test_filter_by_brand_and_field_mapping():
    mp = _MonkeyPatch()
    try:
        bosch = _child(
            'A12345', '博世', frey_no='F001', name='刹车片', spec='规格X',
            vehicle='宝马', replace=['R1', 'R2', 'R1'],
            stock='12', stock_zaitu=3, safe_stock=5.0,
        )
        mahle = _child('A12345', '马勒', frey_no='F002', name='滤芯')
        _install_stubs(mp, {'A12345': _api_data(bosch, mahle)})

        result = Service._batch_query_crm_by_oe(
            [{'oe': 'A12345', 'brand': '博世'}], 'fsbbr'
        )

        assert list(result.keys()) == ['A12345']
        rows = result['A12345']
        assert len(rows) == 1
        row = rows[0]
        assert row['oe'] == 'A12345'
        assert row['brand'] == '博世'
        assert row['frey_no'] == 'F001'
        assert row['product_name'] == '刹车片'
        assert row['l_model_zh'] == '规格X'
        assert row['cass_oebrand_name'] == '宝马'
        # 替换号去重保序，中文逗号拼接
        assert row['replace_number'] == 'R1，R2'
        # CRM 库存三字段统一转 int
        assert row['stock'] == 12
        assert row['stock_zaitu'] == 3
        assert row['safe_stock'] == 5
    finally:
        mp.undo()


def test_oem_brand_interop():
    mp = _MonkeyPatch()
    try:
        oem_4s = _child('B67890', '原厂国内4s件')
        other = _child('B67890', '马勒')
        _install_stubs(mp, {'B67890': _api_data(oem_4s, other)})

        result = Service._batch_query_crm_by_oe(
            [{'oe': 'B67890', 'brand': '原厂'}], 'fsbbr'
        )

        brands = [r['brand'] for r in result['B67890']]
        assert brands == ['原厂国内4s件']
    finally:
        mp.undo()


def test_one_oe_per_call_no_comma():
    mp = _MonkeyPatch()
    try:
        calls = _install_stubs(mp, {
            'AAA': _api_data(_child('AAA', '博世')),
            'BBB': _api_data(_child('BBB', '马勒')),
        })

        Service._batch_query_crm_by_oe(
            [{'oe': 'AAA', 'brand': '博世'}, {'oe': 'BBB', 'brand': '马勒'}],
            'fsbbr',
        )

        assert len(calls) == 2
        for company, numberlist in calls:
            assert company == 'fsbbr'
            assert ',' not in numberlist and '，' not in numberlist
        assert {n for _, n in calls} == {'AAA', 'BBB'}
    finally:
        mp.undo()


def test_failed_oe_returns_empty_without_affecting_others():
    mp = _MonkeyPatch()
    try:
        _install_stubs(
            mp,
            {'BBB': _api_data(_child('BBB', '马勒'))},
            fail_oes={'AAA'},
        )

        result = Service._batch_query_crm_by_oe(
            [{'oe': 'AAA', 'brand': '博世'}, {'oe': 'BBB', 'brand': '马勒'}],
            'fsbbr',
        )

        assert result['AAA'] == []
        assert len(result['BBB']) == 1
    finally:
        mp.undo()


def test_same_oe_multiple_brands_union():
    mp = _MonkeyPatch()
    try:
        _install_stubs(mp, {
            'A12345': _api_data(
                _child('A12345', '博世'),
                _child('A12345', '马勒'),
            ),
        })

        result = Service._batch_query_crm_by_oe(
            [{'oe': 'A12345', 'brand': '博世'}, {'oe': 'A12345', 'brand': '马勒'}],
            'fsbbr',
        )

        assert {r['brand'] for r in result['A12345']} == {'博世', '马勒'}
    finally:
        mp.undo()


def test_empty_items():
    mp = _MonkeyPatch()
    try:
        calls = _install_stubs(mp, {})
        assert Service._batch_query_crm_by_oe([], 'fsbbr') == {}
        assert calls == []
    finally:
        mp.undo()


def test_stock_fields_blank_to_none():
    mp = _MonkeyPatch()
    try:
        child = _child(
            'C999', '博世',
            stock='', stock_zaitu=None, safe_stock='abc',
        )
        _install_stubs(mp, {'C999': _api_data(child)})

        row = Service._batch_query_crm_by_oe(
            [{'oe': 'C999', 'brand': '博世'}], 'fsbbr'
        )['C999'][0]
        assert row['stock'] is None
        assert row['stock_zaitu'] is None
        assert row['safe_stock'] is None
    finally:
        mp.undo()


def main():
    test_filter_by_brand_and_field_mapping()
    test_oem_brand_interop()
    test_one_oe_per_call_no_comma()
    test_failed_oe_returns_empty_without_affecting_others()
    test_same_oe_multiple_brands_union()
    test_empty_items()
    test_stock_fields_blank_to_none()
    print('全部 CRM numberlist 匹配测试通过（7/7）')


if __name__ == '__main__':
    main()
