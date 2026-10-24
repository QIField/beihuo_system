# -*- coding:utf-8 -*-
# @Time    : 2026/10/23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : test_edit_processor.py

"""
页内核对编辑替换号处理逻辑（edit_processor）单元测试

不依赖数据库和真实 CRM 接口：
1. 阶段一行分类：缺字段 / 仅品牌号唯一结果 / OE+品牌
2. 原厂号与其他号拆分（原厂系 vs 其他品牌），其他号剔除与原厂号重复的值
3. OE 未匹配 → 未匹配到产品
4. 阶段二逐产品更新与按行聚合（成功/失败），未提交行继承检查阶段状态
5. updateNumber 成功判定：status==200 或 msg=='操作成功'

运行方式：
    python tests/app/services/replace_number_service/test_edit_processor.py
"""

import os
import sys
import shutil
import tempfile

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..', '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd

from app.services.replace_number_service import edit_processor as ep
from app.services.replace_number_service import matcher as rn_matcher
from app.utils.replace_number import excel_utils


def _child(number, brand, product_id='', replace=None):
    return {
        'number': number,
        'brand_name': brand,
        'product_id': product_id,
        'display_number': [{'number': n} for n in (replace or [])],
    }


def _api_data(*children):
    return {'data': [{'child': list(children)}]}


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


def _patch_crm(mp, oe_map=None, update_results=None):
    """安装 CRM 搜索/更新桩，返回调用记录"""
    oe_map = oe_map or {}
    update_results = update_results or {}
    calls = {'search': [], 'update': []}

    def fake_search(company, numberlist):
        calls['search'].append((company, numberlist))
        return oe_map.get(numberlist)

    def fake_update(company, product_id, numbers):
        calls['update'].append((company, product_id, list(numbers)))
        return update_results.get(product_id, {'status': 200, 'msg': '操作成功'})

    mp.setattr(ep, 'search_products_by_numberlist', fake_search)
    mp.setattr(rn_matcher, 'search_products_by_numberlist', fake_search)
    mp.setattr(ep, 'update_product_numbers', fake_update)
    return calls


def _write_excel(rows_data):
    """生成检查用 Excel，返回文件路径（列：oe/品牌/品牌号）"""
    df = pd.DataFrame(rows_data, columns=['oe', '品牌', '品牌号'])
    path = os.path.join(tempfile.mkdtemp(), 'rn_check_test.xlsx')
    df.to_excel(path, index=False)
    return path


def test_check_rows_classification():
    """阶段一行分类：OE+品牌 / 仅品牌号唯一结果 / 缺字段"""
    mp = _MonkeyPatch()
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        mp.setattr(excel_utils, 'TASK_LOG_DIR', tmp_dir)
        oe_map = {
            'A1': _api_data(_child('A1', '博世', product_id='1', replace=['R1', 'R2'])),
            'BN1': _api_data(_child('P1', '原厂', product_id='2', replace=['N1'])),
        }
        _patch_crm(mp, oe_map=oe_map)

        file_path = _write_excel([
            ['A1', '博世', ''],
            ['', '', 'BN1'],
            ['A3', '', ''],  # 有 OE 无品牌 → 缺少字段（全空行会被 Excel 读写丢弃，无法构造）
        ])
        result = ep.check_replace_number_wrapper(file_path, 'fsbbr')
        items = {it['row_index']: it for it in result['result_data']['items']}

        # OE+品牌行：待更新，博世非原厂系，其替换号归其他号
        assert items[0]['status'] == '待更新'
        assert items[0]['oe'] == 'A1'
        assert items[0]['original_numbers'] == ''
        assert items[0]['other_numbers'] == 'R1,R2'
        assert items[0]['is_upload'] == 1
        assert len(items[0]['products']) == 1
        # 品牌号行：唯一结果直接采用，OE/品牌取产品值，原厂品牌进原厂号
        assert items[1]['status'] == '待更新'
        assert items[1]['oe'] == 'P1'
        assert items[1]['brand'] == '原厂'
        assert items[1]['original_numbers'] == 'N1'
        # 缺字段行
        assert items[2]['status'] == '缺少字段'
        assert items[2]['is_upload'] == 0
        # 统计
        assert result['result_data']['matched_count'] == 2
        assert result['result_data']['unmatched_count'] == 1
    finally:
        mp.undo()
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def test_original_other_split_and_dedup():
    """原厂号与其他号拆分：原厂系归原厂号，其他号剔除与原厂号重复的值"""
    mp = _MonkeyPatch()
    try:
        api_data = _api_data(
            _child('A2', '原厂', product_id='1', replace=['R1', 'R2']),
            _child('A2', '原厂国内4S件', product_id='2', replace=['R2', 'R4']),
            _child('A2', '马勒', product_id='3', replace=['R5']),
            _child('A2', '博世', product_id='4', replace=['R1']),
        )
        all_products = rn_matcher.extract_all_products(api_data)
        matched = rn_matcher.match_products(api_data, 'A2', '马勒')

        item = ep._build_edit_item(0, 'A2', '马勒', '', all_products, matched)

        assert item['original_numbers'] == 'R1,R2,R4'
        assert item['other_numbers'] == 'R5'
        assert set(item['original_brands']) == {'原厂', '原厂国内4S件'}
        assert item['status'] == '待更新'
        assert item['is_upload'] == 1
        # 将更新产品仅含品牌匹配命中的马勒 child
        assert len(item['products']) == 1
        assert item['products'][0]['brand_name'] == '马勒'
        assert item['products'][0]['product_id'] == '3'
    finally:
        mp.undo()


def test_oe_no_match():
    """OE 查询无产品 → 未匹配到产品"""
    mp = _MonkeyPatch()
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        mp.setattr(excel_utils, 'TASK_LOG_DIR', tmp_dir)
        _patch_crm(mp, oe_map={})

        file_path = _write_excel([['A9', '博世', '']])
        result = ep.check_replace_number_wrapper(file_path, 'fsbbr')
        items = result['result_data']['items']

        assert items[0]['status'] == '未匹配到产品'
        assert items[0]['is_upload'] == 0
        assert items[0]['products'] == []
        assert result['result_data']['matched_count'] == 0
    finally:
        mp.undo()
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def test_update_success_and_status_inherit():
    """阶段二全部成功：按行聚合成功数，未提交行继承检查阶段状态"""
    mp = _MonkeyPatch()
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        mp.setattr(excel_utils, 'TASK_LOG_DIR', tmp_dir)
        oe_map = {
            'A1': _api_data(_child('A1', '博世', product_id='1', replace=['R1'])),
            'A2': _api_data(_child('A2', '马勒', product_id='3', replace=['X1'])),
            'A9': _api_data(),
        }
        _patch_crm(mp, oe_map=oe_map, update_results={
            '1': {'status': 200, 'msg': '操作成功'},
            '3': {'status': 0, 'msg': '操作成功'},
        })

        file_path = _write_excel([
            ['A1', '博世', ''],
            ['A2', '马勒', ''],
            ['A9', '博世', ''],
        ])
        check = ep.check_replace_number_wrapper(file_path, 'fsbbr')
        check_items = check['result_data']['items']

        submitted = [
            {'row_index': 0, 'products': [{'product_id': '1', 'numbers': ['R1', 'N9']}]},
            {'row_index': 1, 'products': [{'product_id': '3', 'numbers': ['X1', 'N5']}]},
        ]
        result = ep.update_replace_number_wrapper(
            check['result_data']['file_path'], check_items, submitted, 'fsbbr'
        )

        assert result['result_data']['success_count'] == 2
        assert result['result_data']['fail_count'] == 0
        assert os.path.exists(result['result_file'])

        out = pd.read_excel(result['result_file'], dtype=str)
        status_col = out['更新是否成功'].tolist()
        assert status_col[0] == '更新成功'
        assert status_col[1] == '更新成功'
        # 未提交行沿用检查阶段结论
        assert status_col[2] == '未匹配到产品'
    finally:
        mp.undo()
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def test_update_failure_aggregation():
    """阶段二任一产品失败：整行标记失败并带原因"""
    mp = _MonkeyPatch()
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        mp.setattr(excel_utils, 'TASK_LOG_DIR', tmp_dir)
        oe_map = {
            'A1': _api_data(
                _child('A1', '博世', product_id='1', replace=['R1']),
                _child('A1', '博世', product_id='2', replace=['R2']),
            ),
        }
        _patch_crm(mp, oe_map=oe_map, update_results={
            '2': {'status': 500, 'msg': '服务器错误'},
        })

        file_path = _write_excel([['A1', '博世', '']])
        check = ep.check_replace_number_wrapper(file_path, 'fsbbr')
        check_items = check['result_data']['items']

        submitted = [
            {'row_index': 0, 'products': [
                {'product_id': '1', 'numbers': ['R1']},
                {'product_id': '2', 'numbers': ['R2']},
            ]},
        ]
        result = ep.update_replace_number_wrapper(
            check['result_data']['file_path'], check_items, submitted, 'fsbbr'
        )

        assert result['result_data']['success_count'] == 0
        assert result['result_data']['fail_count'] == 1

        out = pd.read_excel(result['result_file'], dtype=str)
        assert out['更新是否成功'].tolist()[0] == '更新失败: 服务器错误'
    finally:
        mp.undo()
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    tests = [
        test_check_rows_classification,
        test_original_other_split_and_dedup,
        test_oe_no_match,
        test_update_success_and_status_inherit,
        test_update_failure_aggregation,
    ]
    for test in tests:
        test()
        print(f"通过: {test.__name__}")
    print(f"\n全部 {len(tests)} 个测试通过")


if __name__ == '__main__':
    main()
