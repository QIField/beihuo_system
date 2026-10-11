# -*- coding:utf-8 -*-
"""
购物车软删除单元测试

不依赖真实数据库：
1. 清空购物车改为 UPDATE 标记，写入 deleted_by，不再出现 DELETE
2. 批量删除（有条码/无条码）均为 UPDATE 软删，且 WHERE 带 is_deleted = 0
3. 单条删除复用批量软删
4. 定时高库存清理：查询只取未删除行，删除改 UPDATE，操作人记 system
5. 列表/COUNT 一律过滤 is_deleted = 0（所有用户均不可见已删行）
6. 物理清理任务 DELETE 仅针对超保留期且 deleted_time 非空的已删行

运行方式：
    python tests/app/services/cart_service/test_cart_soft_delete.py
"""

import os
import re
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..', '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.cart_service.cart_remove import CartRemoveService
from app.services.cart_service.cart_data_service import CartDataService
import app.services.cart_service.cart_remove as crm_module
import app.services.cart_service.cart_data_service as cds_module


def _normalize(sql):
    return re.sub(r'\s+', ' ', sql).strip()


class _MonkeyPatch:
    """极简 monkeypatch，支持脱离 pytest 直接运行"""

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


class FakeCursor:
    """记录全部 SQL 的假游标"""

    def __init__(self, fetch_queues=None, dict_cursor=False):
        self.executed = []
        self.rowcount = 1
        self._fetch_queues = list(fetch_queues or [])

    def execute(self, sql, params=None):
        self.executed.append((_normalize(sql), params))

    def executemany(self, sql, seq):
        self.executed.append((_normalize(sql), seq))
        self.rowcount = len(seq)

    def fetchall(self):
        return self._fetch_queues.pop(0)

    def fetchone(self):
        return self._fetch_queues.pop(0)


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def cursor(self, *args, **kwargs):
        return self._cursor

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def install_fake_db(mp, **cursor_kwargs):
    cursor = FakeCursor(**cursor_kwargs)
    conn = FakeConn(cursor)
    mp.setattr(crm_module, 'get_db_connection', lambda: conn)
    return cursor, conn


def test_clear_cart_is_soft_delete():
    mp = _MonkeyPatch()
    try:
        cursor, conn = install_fake_db(mp)
        service = CartRemoveService()

        result = service.clear_cart('fsbbr', 'alice')

        sql, params = cursor.executed[0]
        assert sql.startswith('UPDATE crmapp_cart')
        assert 'is_deleted = 1' in sql
        assert 'deleted_time = NOW()' in sql
        assert 'deleted_by = %s' in sql
        assert sql.endswith('WHERE store = %s AND is_deleted = 0')
        assert params == ('alice', 'fsbbr')
        assert 'DELETE' not in sql
        assert conn.commits == 1
        assert result['code'] == 0
        assert result['deleted_count'] == 1
    finally:
        mp.undo()


def test_remove_multiple_with_barcode_is_soft_delete():
    mp = _MonkeyPatch()
    try:
        cursor, _ = install_fake_db(mp)
        service = CartRemoveService()
        items = [
            {'item_oe': 'OE1', 'item_barcode': 'B1'},
            {'item_oe': 'OE2', 'item_barcode': 'B2'},
        ]

        result = service.remove_multiple_items('fsbbr', items, 'alice')

        assert len(cursor.executed) == 2
        for sql, params in cursor.executed:
            assert sql.startswith('UPDATE crmapp_cart')
            assert 'is_deleted = 1' in sql
            assert 'WHERE oe = %s AND barcode = %s AND store = %s AND is_deleted = 0' in sql
            assert 'DELETE' not in sql
        assert cursor.executed[0][1] == ('alice', 'OE1', 'B1', 'fsbbr')
        assert result['code'] == 0
        assert result['deleted_count'] == 2
    finally:
        mp.undo()


def test_remove_multiple_without_barcode_is_soft_delete():
    mp = _MonkeyPatch()
    try:
        cursor, _ = install_fake_db(mp)
        service = CartRemoveService()

        service.remove_multiple_items('fsbbr', [{'item_oe': 'OE9'}], 'bob')

        sql, params = cursor.executed[0]
        assert sql.startswith('UPDATE crmapp_cart')
        assert 'WHERE oe = %s AND store = %s AND is_deleted = 0' in sql
        assert params == ('bob', 'OE9', 'fsbbr')
    finally:
        mp.undo()


def test_remove_single_item_uses_soft_delete():
    mp = _MonkeyPatch()
    try:
        cursor, _ = install_fake_db(mp)
        service = CartRemoveService()

        result = service.remove_single_item('fsbbr', 'OE1', 'B1', 'alice')

        sql, params = cursor.executed[0]
        assert sql.startswith('UPDATE crmapp_cart')
        assert 'is_deleted = 1' in sql
        assert params == ('alice', 'OE1', 'B1', 'fsbbr')
        assert result['code'] == 0
    finally:
        mp.undo()


def test_auto_remove_high_stock_is_soft_delete():
    mp = _MonkeyPatch()
    try:
        cart_rows = [{'id': 1, 'barcode': 'B1'}]
        stock_rows = [{'物料条码': 'B1', '库存数量': 25}]
        cursor, _ = install_fake_db(mp, fetch_queues=[cart_rows, stock_rows])
        service = CartRemoveService()

        result = service.auto_remove_high_stock_items('fsbbr', 20)

        query_cart_sql = cursor.executed[0][0]
        assert 'is_deleted = 0' in query_cart_sql
        delete_sql, delete_params = cursor.executed[-1]
        assert delete_sql.startswith('UPDATE crmapp_cart')
        assert 'is_deleted = 1' in delete_sql
        assert delete_sql.endswith('AND store = %s AND is_deleted = 0')
        assert delete_params == ['system', 1, 'fsbbr']
        assert result['code'] == 0
        assert result['deleted_count'] == 1
    finally:
        mp.undo()


class FakeDBCursorContext:
    """db_cursor 上下文管理器的假实现"""

    def __init__(self, cursor):
        self._cursor = cursor

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self._cursor

    def __exit__(self, *exc):
        return False


def test_purge_deleted_items_physical_delete():
    mp = _MonkeyPatch()
    try:
        cursor, conn = install_fake_db(mp)
        service = CartRemoveService()

        result = service.purge_deleted_items(retention_days=90)

        sql, params = cursor.executed[0]
        assert sql.startswith('DELETE FROM crmapp_cart')
        assert 'is_deleted = 1' in sql
        assert 'deleted_time IS NOT NULL' in sql
        assert 'deleted_time < DATE_SUB(NOW(), INTERVAL %s DAY)' in sql
        assert params == (90,)
        assert conn.commits == 1
        assert result['code'] == 0
        assert result['purged_count'] == 1
        assert result['retention_days'] == 90
    finally:
        mp.undo()


def test_get_cart_data_default_filters_deleted():
    mp = _MonkeyPatch()
    try:
        cursor = FakeCursor(fetch_queues=[{'total': 0}, []])
        mp.setattr(cds_module, 'db_cursor', FakeDBCursorContext(cursor))

        data, total = CartDataService().get_cart_data('fsbbr')

        list_sql = cursor.executed[0][0]
        count_sql = cursor.executed[1][0]
        assert 'WHERE store = %s AND is_deleted = 0' in list_sql
        assert 'WHERE store = %s AND is_deleted = 0' in count_sql
        assert data == []
        assert total == 0
    finally:
        mp.undo()


def main():
    test_clear_cart_is_soft_delete()
    test_remove_multiple_with_barcode_is_soft_delete()
    test_remove_multiple_without_barcode_is_soft_delete()
    test_remove_single_item_uses_soft_delete()
    test_auto_remove_high_stock_is_soft_delete()
    test_purge_deleted_items_physical_delete()
    test_get_cart_data_default_filters_deleted()
    print('全部购物车软删除测试通过（7/7）')


if __name__ == '__main__':
    main()
