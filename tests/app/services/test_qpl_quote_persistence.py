# -*- coding:utf-8 -*-
"""
汽配龙报价落库幂等性 单元测试

覆盖目标：
  1. save_quote_records：SQL 带 ON DUPLICATE KEY UPDATE（同订单明细不重复插入）；
     brand_name 为 None 时兜底为空串（MySQL 唯一索引对 NULL 不去重）
  2. save_quote_records / save_flow_trace_records：执行异常时连接仍被关闭（try/finally）
  3. save_flow_trace_records：SQL 带 ON DUPLICATE KEY UPDATE（多轮任务不堆积追踪记录）
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from app.services import qpl_quote_persistence as qp


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self._conn.records.append((sql, params))
        if self._conn.raise_on_execute:
            raise RuntimeError('模拟数据库异常')


class FakeConn:
    def __init__(self, raise_on_execute=False):
        self.records = []
        self.commit_count = 0
        self.close_count = 0
        self.raise_on_execute = raise_on_execute

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        pass

    def close(self):
        self.close_count += 1


def _patch_conn(monkeypatch, conn):
    monkeypatch.setattr(qp, 'get_db_connection', lambda: conn)


# ---------------------------------------------------------------------------
# save_quote_records
# ---------------------------------------------------------------------------

def test_save_quote_records_uses_upsert_sql(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    qp.save_quote_records('SIQR001', [{'enquiry_item_id': '1', 'brand_name': '菲尔'}], {}, '2026-11-18 10:00:00')

    sql, _ = conn.records[0]
    assert 'ON DUPLICATE KEY UPDATE' in sql
    assert conn.commit_count == 1
    assert conn.close_count == 1


def test_save_quote_records_none_brand_defaults_to_empty(monkeypatch):
    """brand_name=None 必须兜底为 ''，否则唯一键不去重导致明细重复堆积"""
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    detail = {'enquiry_item_id': '1', 'brand_name': None}
    qp.save_quote_records('SIQR001', [detail], {}, '2026-11-18 10:00:00')

    _, params = conn.records[0]
    assert params[8] == ''  # 第 9 个参数为 brand_name


def test_save_quote_records_missing_brand_defaults_to_empty(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    qp.save_quote_records('SIQR001', [{'enquiry_item_id': '1'}], {}, '2026-11-18 10:00:00')

    _, params = conn.records[0]
    assert params[8] == ''


def test_save_quote_records_closes_conn_on_error(monkeypatch):
    conn = FakeConn(raise_on_execute=True)
    _patch_conn(monkeypatch, conn)

    with pytest.raises(RuntimeError):
        qp.save_quote_records('SIQR001', [{'enquiry_item_id': '1'}], {}, '2026-11-18 10:00:00')

    assert conn.close_count == 1


# ---------------------------------------------------------------------------
# save_flow_trace_records
# ---------------------------------------------------------------------------

def test_save_flow_trace_records_uses_upsert_sql(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    trace = {
        'supplier_enquiry_no': 'SIQR001',
        'enquiry_item_id': '1',
        'flow_name': 'CRM现货',
        'flow_status': '失败',
        'fail_reason': '无库存',
    }
    qp.save_flow_trace_records([trace], company='fsbbr')

    sql, _ = conn.records[0]
    assert 'ON DUPLICATE KEY UPDATE' in sql
    assert conn.commit_count == 1
    assert conn.close_count == 1


def test_save_flow_trace_records_closes_conn_on_error(monkeypatch):
    conn = FakeConn(raise_on_execute=True)
    _patch_conn(monkeypatch, conn)

    trace = {'supplier_enquiry_no': 'SIQR001', 'enquiry_item_id': '1', 'flow_name': 'CRM现货'}
    with pytest.raises(RuntimeError):
        qp.save_flow_trace_records([trace], company='fsbbr')

    assert conn.close_count == 1


def test_save_flow_trace_records_empty_list_skips(monkeypatch):
    def _boom():
        raise AssertionError('空列表不应创建数据库连接')

    _patch_conn(monkeypatch, _boom)
    qp.save_flow_trace_records([])
