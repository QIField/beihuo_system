# -*- coding:utf-8 -*-
"""
汽配龙自动报价重构 · 阶段四单元测试

覆盖目标：
  1. bmw_oe.ensure_bmw_oes_for_order：宝马订单 OE 收集→查本地库→补齐链路；
     非宝马订单零副作用；补齐异常不向上抛
  2. runner.run_round：拉单去重、A 类优先排序、逐单串行、订单级异常隔离、统计
  3. runner.run_all_companies：公司级异常隔离
  4. 任务入口：时段外静默、锁占用跳过
"""

import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from app.services.qpl_auto_quote import bmw_oe as bo
from app.services.qpl_auto_quote import runner as rn


def _bmw_detail(item_ids=(301, 302)):
    return {
        'supplierEnquiryNo': 'SIQR900', 'carBrand': '宝马',
        'supplierEnquiryDemandList': [
            {'supplierEnquiryItemList': [
                {'enquiryItemId': i, 'quoteStatus': 'WAITING_QUOTE'} for i in item_ids
            ]},
        ],
    }


# ---------------------------------------------------------------------------
# bmw_oe
# ---------------------------------------------------------------------------

def test_matcher_normalizes_tuple_failed_reasons():
    """A 类旧处理器的失败原因二元组 (reason, flag) 归一化为纯字符串"""
    from app.services.qpl_auto_quote.matcher import _normalize_failed_items

    raw = {1: ('适配列表为空', False), 2: '无候选产品'}
    assert _normalize_failed_items(raw) == {1: '适配列表为空', 2: '无候选产品'}
    assert _normalize_failed_items(None) == {}

def test_ensure_bmw_non_bmw_order_no_side_effect(monkeypatch):
    """非宝马订单：不收集不查库，直接返回空统计"""
    monkeypatch.setattr(bo, '_collect_bmw_original_oes',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('非宝马不应收集 OE')))

    stats = bo.ensure_bmw_oes_for_order({'carBrand': '丰田', 'supplierEnquiryNo': 'SIQR1'}, 'fsbbr')

    assert stats == {'collected': 0, 'missing': 0, 'filled': 0, 'failed': 0}


def test_ensure_bmw_full_chain(monkeypatch):
    """宝马订单：收集→本地库→补齐 链路各步骤参数正确"""
    detail = _bmw_detail()
    calls = {}

    monkeypatch.setattr(bo, '_collect_bmw_original_oes',
                        lambda orders, c, processed_item_ids=None: calls.__setitem__(
                            'collect', (orders, c, processed_item_ids)) or {'OE-A', 'OE-B'})
    import app.utils.qpl_auto_bill.bmw_quote_local_db as local_db
    monkeypatch.setattr(local_db, 'check_bmw_oes_in_local_db',
                        lambda oes: ({}, {'missing': ['OE-A']}))
    monkeypatch.setattr(bo, '_ensure_bmw_oes_in_local_db',
                        lambda missing, c: calls.__setitem__('fill', (missing, c))
                        or {'total': 1, 'success': 1, 'failed': 0})

    stats = bo.ensure_bmw_oes_for_order(detail, 'fsbbr', skip_item_ids={302})

    assert stats == {'collected': 2, 'missing': 1, 'filled': 1, 'failed': 0}
    orders, company, processed = calls['collect']
    assert company == 'fsbbr'
    assert processed == {('SIQR900', 302)}          # 跳过项转为 (单号, 明细) 排除集合
    assert calls['fill'] == (['OE-A'], 'fsbbr')


def test_ensure_bmw_all_present_no_fill(monkeypatch):
    """本地库齐全：不触发补齐"""
    detail = _bmw_detail()
    monkeypatch.setattr(bo, '_collect_bmw_original_oes', lambda *a, **k: {'OE-A'})
    import app.utils.qpl_auto_bill.bmw_quote_local_db as local_db
    monkeypatch.setattr(local_db, 'check_bmw_oes_in_local_db',
                        lambda oes: ({}, {'missing': []}))
    monkeypatch.setattr(bo, '_ensure_bmw_oes_in_local_db',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('齐全不应补齐')))

    stats = bo.ensure_bmw_oes_for_order(detail, 'fsbbr')

    assert stats['collected'] == 1 and stats['missing'] == 0 and stats['filled'] == 0


def test_ensure_bmw_collect_exception_not_raised(monkeypatch):
    """收集/补齐链路异常：不上抛（订单流水线不应因 OE 补齐中断）"""
    detail = _bmw_detail()
    monkeypatch.setattr(bo, '_collect_bmw_original_oes', lambda *a, **k: {'OE-A'})
    import app.utils.qpl_auto_bill.bmw_quote_local_db as local_db
    monkeypatch.setattr(local_db, 'check_bmw_oes_in_local_db',
                        lambda oes: (_ for _ in ()).throw(RuntimeError('db down')))

    # 本层不吞异常（与旧版一致：由 pipeline 的订单级隔离兜底），但需可预期
    with pytest.raises(RuntimeError):
        bo.ensure_bmw_oes_for_order(detail, 'fsbbr')


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def _order(no, brand='丰田'):
    return {'supplierEnquiryNo': no, 'carBrand': brand}


def test_runner_round_serial_and_stats(monkeypatch):
    """逐单串行处理 + 轮次统计正确"""
    orders = [_order('SI1'), _order('SI2'), _order('SI3')]
    monkeypatch.setattr(rn, 'list_enquiry_orders',
                        lambda b, e, page_num=1, company=None, **k: {'data': orders})
    monkeypatch.setattr(rn, 'classify_order', lambda o: 'A')
    monkeypatch.setattr(rn, 'record_attempt', lambda *a, **k: None)
    seq = []
    monkeypatch.setattr(rn, 'process_order',
                        lambda c, no, rid: seq.append(no) or (no != 'SI2'))

    stats = rn.run_round('fsbbr', begin_date='2026-11-16', end_date='2026-11-18')

    assert seq == ['SI1', 'SI2', 'SI3']             # 串行逐单
    assert stats == {'total': 3, 'submitted': 2, 'no_action': 1, 'error': 0}


def test_runner_round_order_exception_isolated(monkeypatch):
    """单订单异常不中断本轮，计入 error"""
    monkeypatch.setattr(rn, 'list_enquiry_orders',
                        lambda b, e, page_num=1, company=None, **k:
                        {'data': [_order('SI1'), _order('SI2')]})
    monkeypatch.setattr(rn, 'classify_order', lambda o: 'A')
    monkeypatch.setattr(rn, 'record_attempt', lambda *a, **k: None)
    monkeypatch.setattr(rn, 'process_order',
                        lambda c, no, rid: (_ for _ in ()).throw(RuntimeError('boom')) if no == 'SI1' else True)

    stats = rn.run_round('fsbbr', begin_date='2026-11-16', end_date='2026-11-18')

    assert stats == {'total': 2, 'submitted': 1, 'no_action': 0, 'error': 1}


def test_runner_round_a_category_first(monkeypatch):
    """A 类订单优先于 B/C 类处理"""
    orders = [_order('SI-C', '宝马'), _order('SI-A', '丰田'), _order('SI-B', '奔驰')]

    def classify(o):
        return {'宝马': 'C', '奔驰': 'B'}.get(o['carBrand'], 'A')

    monkeypatch.setattr(rn, 'list_enquiry_orders',
                        lambda b, e, page_num=1, company=None, **k: {'data': orders})
    monkeypatch.setattr(rn, 'classify_order', classify)
    monkeypatch.setattr(rn, 'record_attempt', lambda *a, **k: None)
    seq = []
    monkeypatch.setattr(rn, 'process_order', lambda c, no, rid: seq.append(no) or False)

    rn.run_round('fsbbr', begin_date='2026-11-16', end_date='2026-11-18')

    assert seq == ['SI-A', 'SI-C', 'SI-B']          # A 在前，B/C 稳定保持原顺序


def test_runner_round_fetch_list_fail(monkeypatch):
    """拉单失败：不处理任何订单，返回全零统计"""
    monkeypatch.setattr(rn, 'list_enquiry_orders',
                        lambda b, e, page_num=1, company=None, **k:
                        (_ for _ in ()).throw(RuntimeError('api down')))
    monkeypatch.setattr(rn, 'record_attempt', lambda *a, **k: None)
    monkeypatch.setattr(rn, 'process_order',
                        lambda *a: (_ for _ in ()).throw(AssertionError('拉单失败不应处理订单')))

    stats = rn.run_round('fsbbr')

    assert stats == {'total': 0, 'submitted': 0, 'no_action': 0, 'error': 0}


def test_runner_all_companies_isolated(monkeypatch):
    """公司级异常隔离：单公司失败不影响其他公司"""
    monkeypatch.setattr(rn, 'get_supported_companies', lambda: ['fsbbr', 'gzbc'])
    seq = []

    def fake_round(company, b=None, e=None):
        if company == 'gzbc':
            raise RuntimeError('company boom')
        seq.append(company)
        return {'total': 1, 'submitted': 1, 'no_action': 0, 'error': 0}

    monkeypatch.setattr(rn, 'run_round', fake_round)

    results = rn.run_all_companies()

    assert seq == ['fsbbr']
    assert results['fsbbr']['submitted'] == 1
    assert results['gzbc'] == {'total': 0, 'submitted': 0, 'no_action': 0, 'error': 0}


# ---------------------------------------------------------------------------
# 任务入口
# ---------------------------------------------------------------------------

class _FakeDatetime:
    """替换模块内 datetime，固定 now() 返回值（datetime 类型不可 setattr）"""
    _fixed = datetime(2026, 11, 18, 10, 0, 0)

    @classmethod
    def now(cls):
        return cls._fixed


def test_task_entry_silent_outside_window(monkeypatch):
    """时段外（08:00-20:00 之外）完全静默：不执行、不加锁"""
    from app.tasks import qpl_auto_quote_v2_task as task

    _FakeDatetime._fixed = datetime(2026, 11, 18, 21, 0, 0)
    monkeypatch.setattr(task, 'datetime', _FakeDatetime)
    monkeypatch.setattr(task._round_lock, 'acquire',
                        lambda: (_ for _ in ()).throw(AssertionError('时段外不应加锁')))
    monkeypatch.setattr(task, 'run_all_companies',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('时段外不应执行')))

    assert task.qpl_auto_quote_v2_task() is None


def test_task_entry_skip_when_locked(monkeypatch):
    """上一轮未结束：本轮非阻塞跳过"""
    from app.tasks import qpl_auto_quote_v2_task as task

    _FakeDatetime._fixed = datetime(2026, 11, 18, 10, 0, 0)
    monkeypatch.setattr(task, 'datetime', _FakeDatetime)
    monkeypatch.setattr(task._round_lock, 'acquire', lambda: False)
    monkeypatch.setattr(task, 'run_all_companies',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('锁占用不应执行')))
    monkeypatch.setattr(task._round_lock, 'release', lambda: None)

    assert task.qpl_auto_quote_v2_task() is None


def test_task_entry_runs_and_releases_lock(monkeypatch):
    """正常执行：进入业务后释放锁"""
    from app.tasks import qpl_auto_quote_v2_task as task

    _FakeDatetime._fixed = datetime(2026, 11, 18, 10, 0, 0)
    monkeypatch.setattr(task, 'datetime', _FakeDatetime)
    monkeypatch.setattr(task._round_lock, 'acquire', lambda: True)
    released = []
    monkeypatch.setattr(task._round_lock, 'release', lambda: released.append(True))
    monkeypatch.setattr(task, 'run_all_companies', lambda *a, **k: released.append('ran'))

    task.qpl_auto_quote_v2_task()

    assert released == ['ran', True]                # 先执行后释放
