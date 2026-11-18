# -*- coding:utf-8 -*-
"""
汽配龙自动报价重构 · 落库层单元测试

覆盖目标：
  1. upsert_order / upsert_items：SQL 带 ON DUPLICATE KEY UPDATE（幂等写入）
  2. upsert_items 的 UPDATE 子句不含状态机字段（重复入库不重置终态）
  3. record_attempt：纯 INSERT 不带 ON DUPLICATE（append-only），dict 快照序列化
  4. mark_item_failed：临时失败走 IF 冷却/耗尽判定，确定性失败直接终态
  5. fetch_pending_items：状态过滤 + 冷却到期条件，DictCursor 查询
  6. reset_item_for_retry：打回 pending 并清零计数
  7. 异常时连接仍被关闭（try/finally）
  8. 三表建表 DDL：CREATE TABLE IF NOT EXISTS × 3
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from app.services.qpl_auto_quote import persistence as ps
from app.services.qpl_auto_quote import constants as qc
from app.utils.database.tables import qpl_auto_quote_tables as tables


class FakeCursor:
    def __init__(self, conn, dict_mode=False):
        self._conn = conn
        self._dict_mode = dict_mode

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self._conn.records.append((sql, params))
        if self._conn.raise_on_execute:
            raise RuntimeError('模拟数据库异常')

    def fetchall(self):
        return self._conn.fetch_result


class FakeConn:
    def __init__(self, raise_on_execute=False, fetch_result=None):
        self.records = []
        self.commit_count = 0
        self.close_count = 0
        self.raise_on_execute = raise_on_execute
        self.fetch_result = fetch_result or []
        self.dict_cursor_requested = False

    def cursor(self, cursor_class=None):
        if cursor_class is not None:
            self.dict_cursor_requested = True
        return FakeCursor(self, dict_mode=cursor_class is not None)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        pass

    def close(self):
        self.close_count += 1


def _patch_conn(monkeypatch, conn):
    monkeypatch.setattr(ps, 'get_db_connection', lambda: conn)


# ---------------------------------------------------------------------------
# upsert_order / upsert_items
# ---------------------------------------------------------------------------

def test_upsert_order_uses_upsert_sql(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    ps.upsert_order('fsbbr', {'supplier_enquiry_no': 'SIQR001'})

    sql, _ = conn.records[0]
    assert 'INSERT INTO qpl_order ' in sql
    assert 'ON DUPLICATE KEY UPDATE' in sql
    assert conn.commit_count == 1
    assert conn.close_count == 1


def test_upsert_items_batch_and_upsert_sql(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    items = [{'enquiry_item_id': 1, 'item_oe': 'A1'}, {'enquiry_item_id': 2, 'item_oe': 'A2'}]
    ps.upsert_items('fsbbr', 'SIQR001', items)

    assert len(conn.records) == 2
    sql, params = conn.records[0]
    assert 'ON DUPLICATE KEY UPDATE' in sql
    assert params[1] == 'SIQR001'      # supplier_enquiry_no
    assert params[3] == 1              # enquiry_item_id


def test_upsert_items_empty_list_no_sql(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    ps.upsert_items('fsbbr', 'SIQR001', [])

    assert conn.records == []
    assert conn.close_count == 0  # 空列表提前返回，不开连接


def test_upsert_items_does_not_touch_status_fields(monkeypatch):
    """UPDATE 子句绝不能含 status/fail/retry 字段，否则重复入库会重置终态"""
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    ps.upsert_items('fsbbr', 'SIQR001', [{'enquiry_item_id': 1}])

    sql, _ = conn.records[0]
    update_clause = sql.split('ON DUPLICATE KEY UPDATE')[1]
    for forbidden in ('status', 'fail_stage', 'fail_reason', 'retry_count', 'next_retry_time'):
        assert forbidden not in update_clause, f"UPDATE 子句不应包含 {forbidden}"


# ---------------------------------------------------------------------------
# record_attempt（append-only）
# ---------------------------------------------------------------------------

def test_record_attempt_plain_insert(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    ps.record_attempt('fsbbr', 'SIQR001', 1, '20261118100000_fsbbr',
                      qc.ACTION_SUBMIT, qc.RESULT_SUCCESS)

    sql, params = conn.records[0]
    assert 'INSERT INTO qpl_quote_attempt' in sql
    assert 'ON DUPLICATE KEY UPDATE' not in sql  # 只插不改
    assert params[4] == 'submit'
    assert params[5] == '成功'


def test_record_attempt_snapshot_dict_serialized(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    ps.record_attempt('fsbbr', 'SIQR001', 1, 'r1', 'price_check', '失败',
                      request_snapshot={'price': 87}, response_snapshot='原始文本')

    _, params = conn.records[0]
    assert json.loads(params[9]) == {'price': 87}   # dict → JSON 串
    assert params[10] == '原始文本'                  # 字符串原样


# ---------------------------------------------------------------------------
# mark_item_quoted / mark_item_failed / reset_item_for_retry
# ---------------------------------------------------------------------------

def test_mark_item_quoted_sets_terminal_status(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    ps.mark_item_quoted('fsbbr', 1, quote_source='CRM现货', item_sell_price=87)

    sql, params = conn.records[0]
    assert "status = 'quoted'" in sql
    assert params[-1] == 1
    assert params[0] == 'CRM现货'


def test_mark_item_failed_temp_uses_cooldown_if(monkeypatch):
    """临时失败：SQL 内 IF 判定冷却与重试耗尽"""
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    ps.mark_item_failed('fsbbr', 1, '接口请求', '超时', is_temp=True)

    sql, params = conn.records[0]
    assert "IF(retry_count + 1 >=" in sql
    assert "DATE_ADD(NOW(), INTERVAL" in sql
    assert "retry_count = retry_count + 1" in sql
    assert params[0] == ps.MAX_RETRY
    assert params[2] == ps.COOLING_HOURS


def test_mark_item_failed_biz_direct_terminal(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    ps.mark_item_failed('fsbbr', 1, '价格校验', '校验不过', is_temp=False)

    sql, _ = conn.records[0]
    assert "status = 'failed_biz'" in sql
    assert 'retry_count' not in sql        # 确定性失败不动重试计数
    assert 'next_retry_time = NULL' in sql


def test_reset_item_for_retry(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)

    ps.reset_item_for_retry('fsbbr', 1)

    sql, _ = conn.records[0]
    assert "status = 'pending'" in sql
    assert 'retry_count = 0' in sql
    assert 'next_retry_time = NOW()' in sql


# ---------------------------------------------------------------------------
# fetch_pending_items
# ---------------------------------------------------------------------------

def test_fetch_pending_items_filters_and_dict_cursor(monkeypatch):
    conn = FakeConn(fetch_result=[{'enquiry_item_id': 1}])
    _patch_conn(monkeypatch, conn)

    class DictCursorStub:
        def execute(self, sql, params=None):
            conn.records.append((sql, params))

        def fetchall(self):
            return conn.fetch_result

        def close(self):
            pass

    monkeypatch.setattr(ps, 'get_dict_cursor', lambda c: DictCursorStub())

    rows = ps.fetch_pending_items('fsbbr')

    sql, params = conn.records[0]
    assert "i.status IN ('pending', 'failed_temp')" in sql
    assert 'i.next_retry_time IS NULL OR i.next_retry_time <= NOW()' in sql
    assert 'JOIN qpl_order o' in sql
    assert params == ('fsbbr',)
    assert rows == [{'enquiry_item_id': 1}]
    assert conn.close_count == 1


# ---------------------------------------------------------------------------
# 异常安全 / 工具函数
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('func,args', [
    (ps.upsert_order, ('fsbbr', {'supplier_enquiry_no': 'S1'})),
    (ps.upsert_items, ('fsbbr', 'S1', [{'enquiry_item_id': 1}])),
    (ps.record_attempt, ('fsbbr', 'S1', 1, 'r', 'submit', '成功')),
    (ps.mark_item_quoted, ('fsbbr', 1)),
    (ps.mark_item_failed, ('fsbbr', 1, 'x', 'y', False)),
])
def test_conn_closed_on_error(monkeypatch, func, args):
    conn = FakeConn(raise_on_execute=True)
    _patch_conn(monkeypatch, conn)

    with pytest.raises(RuntimeError):
        func(*args)

    assert conn.close_count == 1


def test_make_round_id_format():
    from datetime import datetime
    rid = ps.make_round_id('fsbbr', datetime(2026, 11, 18, 10, 0, 0))
    assert rid == '20261118100000_fsbbr'


def test_next_cooling_time():
    from datetime import datetime
    nxt = ps.next_cooling_time(datetime(2026, 11, 18, 10, 0, 0))
    assert (nxt - datetime(2026, 11, 18, 10, 0, 0)).total_seconds() == ps.COOLING_HOURS * 3600


# ---------------------------------------------------------------------------
# 三表建表 DDL
# ---------------------------------------------------------------------------

def test_init_tables_executes_three_ddl(monkeypatch):
    conn = FakeConn()
    # tables 模块内是延迟导入 get_db_connection，需 patch 源模块
    monkeypatch.setattr('app.utils.database_connection.get_db_connection', lambda: conn)

    tables.init_qpl_auto_quote_tables()

    assert len(conn.records) == 3
    sqls = [sql for sql, _ in conn.records]
    assert all('CREATE TABLE IF NOT EXISTS' in s for s in sqls)
    assert 'CREATE TABLE IF NOT EXISTS qpl_order ' in sqls[0]
    assert 'CREATE TABLE IF NOT EXISTS qpl_order_item' in sqls[1]
    assert 'CREATE TABLE IF NOT EXISTS qpl_quote_attempt' in sqls[2]
    assert 'uk_company_enquiry' in sqls[0]
    assert 'uk_company_item' in sqls[1]
    assert "INDEX idx_status_retry" in sqls[1]
    assert conn.commit_count == 3
    assert conn.close_count == 3
