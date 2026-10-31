"""
供应商价格对比服务单测（mock 数据库游标，不连真实库）

覆盖：供应商候选（排除巴博瑞）、基准映射（同OE最低价）、方向拆分（higher/lower，
持平与无基准行不展示）、价差计算、供应商留空=全部供应商（仅按日期过滤）、
列筛选候选、分页、排序、参数校验
"""
import pytest

from app.services.cass_inquiry_service import price_compare_service as svc


def quote_row(decode_num='OE-A', parts_num='P-1', brand='博世', parts='火花塞',
              quality='品牌件', num='2', warehouse='华南仓', price='97.50'):
    """报价行构造（与 _fetch_store_quotes SELECT 列顺序一致）"""
    return (decode_num, parts_num, brand, parts, quality, num, warehouse, price)


class RoutedCursor:
    """按 SQL 特征路由返回数据的假游标：GROUP BY→基准、其余→报价行"""

    def __init__(self, quote_rows, baseline_rows):
        self.quote_rows = quote_rows
        self.baseline_rows = baseline_rows
        self.executed = []
        self.last_sql = ''

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.executed.append((sql, params))

    def fetchone(self):
        return self._rows()[0] if self._rows() else None

    def fetchall(self):
        return self._rows()

    def _rows(self):
        if 'GROUP BY' in self.last_sql:
            return self.baseline_rows
        return self.quote_rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def patch_db(monkeypatch, quote_rows=None, baseline_rows=None):
    cursor = RoutedCursor(quote_rows or [], baseline_rows or [])
    monkeypatch.setattr(svc, 'db_cursor', lambda dict_cursor=False: cursor)
    return cursor


# ===== 供应商候选 =====

def test_list_stores_excludes_bbri_and_empty(monkeypatch):
    cursor = patch_db(monkeypatch, quote_rows=[('广州鸿达汽配',), ('深圳巨牛汽配',)])
    result = svc.list_stores()
    assert result['code'] == 0
    assert result['data']['stores'] == ['广州鸿达汽配', '深圳巨牛汽配']
    sql, params = cursor.executed[0]
    assert 'DISTINCT store_name' in sql
    assert params == (svc.BBRI_STORE_NAME,)  # SQL 内排除巴博瑞自身


# ===== 方向拆分与价差 =====

def test_higher_lower_split_and_diff(monkeypatch):
    """higher/lower 各查一个方向；持平不展示；无基准行不比对、不返回"""
    baseline_rows = [('OE-A', '博世', 88.0), ('OE-B', '曼牌', 45.5)]
    quote_rows = [
        quote_row('OE-A', price='97.50'),   # 高于基准 +9.50
        quote_row('OE-A', price='88.00'),   # 持平（不展示）
        quote_row('OE-A', price='80.20'),   # 低于基准 -7.80
        quote_row('OE-B', brand='曼牌', parts='机滤', price='40.00'),  # 低于基准 -5.50
        quote_row('OE-C', brand='NGK', parts='其他件', price='60.00'),  # 巴博瑞无同OE报价
    ]
    patch_db(monkeypatch, quote_rows=quote_rows, baseline_rows=baseline_rows)

    higher = svc.query_price_compare('广州鸿达汽配', status='higher')['data']['list']
    assert [(i['decode_num'], i['diff']) for i in higher] == [('OE-A', 9.5)]
    assert higher[0]['bbri_price'] == 88.0

    lower = svc.query_price_compare('广州鸿达汽配', status='lower')['data']['list']
    assert [(i['decode_num'], i['diff']) for i in lower] == [('OE-A', -7.8), ('OE-B', -5.5)]

    # 方向由所在表格区分，行内不携带状态字段
    assert all('compare_status' not in i for i in higher + lower)
    # 无基准行（OE-C）与持平行（88.00）均不返回
    assert all(i['decode_num'] != 'OE-C' for i in higher + lower)
    assert all(i['seller_price'] != 88.0 for i in higher + lower)


def test_baseline_takes_min_price(monkeypatch):
    """基准 SQL 聚合同 OE 最低价（MIN），服务层直接映射"""
    baseline_rows = [('OE-A', '博世', 45.0)]
    patch_db(monkeypatch, quote_rows=[quote_row(price='50.00')], baseline_rows=baseline_rows)

    items = svc.query_price_compare('深圳巨牛汽配', status='higher')['data']['list']
    assert items[0]['bbri_price'] == 45.0
    assert items[0]['diff'] == 5.0


def test_baseline_ignores_non_positive(monkeypatch):
    """基准价 0/None 等非法值不参与映射，对应行无基准、不返回"""
    baseline_rows = [('OE-A', '博世', 0), ('OE-B', '曼牌', None)]
    patch_db(monkeypatch, quote_rows=[
        quote_row(price='50.00'),
        quote_row('OE-B', brand='曼牌', parts='机滤', price='40.00'),
    ], baseline_rows=baseline_rows)

    items = svc.query_price_compare('深圳巨牛汽配', status='higher')['data']['list']
    assert items == []


def test_invalid_seller_price_row(monkeypatch):
    """卖家价格非法（None/非数字/非正数）时不参与比较、不返回"""
    baseline_rows = [('OE-A', '博世', 88.0)]
    patch_db(monkeypatch, quote_rows=[
        quote_row(price=None),
        quote_row(price='abc'),
        quote_row(price='0'),
    ], baseline_rows=baseline_rows)

    items = svc.query_price_compare('深圳巨牛汽配', status='higher')['data']['list']
    assert items == []


# ===== 供应商留空=全部供应商 =====

def test_empty_store_queries_all_suppliers(monkeypatch):
    """供应商留空=全部供应商（排除巴博瑞自身与空值），SQL 不再按单店过滤"""
    cursor = patch_db(monkeypatch, quote_rows=[quote_row(price='97.50')],
                      baseline_rows=[('OE-A', '博世', 88.0)])
    result = svc.query_price_compare(None, status='higher')

    assert result['code'] == 0
    assert result['data']['total'] == 1
    sql, params = cursor.executed[0]
    assert 'store_name = %s' not in sql
    assert "store_name != %s" in sql
    assert params[0] == svc.BBRI_STORE_NAME


def test_all_suppliers_rows_each_compared(monkeypatch):
    """全部供应商模式下，不同供应商的同 OE 行各自与基准比对"""
    baseline_rows = [('OE-A', '博世', 88.0), ('OE-A', '曼牌', 88.0)]
    patch_db(monkeypatch, quote_rows=[
        quote_row('OE-A', parts_num='P-1', price='97.50'),  # 高于
        quote_row('OE-A', parts_num='P-2', brand='曼牌', price='80.00'),  # 低于
    ], baseline_rows=baseline_rows)

    higher = svc.query_price_compare('', status='higher')['data']
    lower = svc.query_price_compare('', status='lower')['data']
    assert [(i['merchant_parts_num'], i['diff']) for i in higher['list']] == [('P-1', 9.5)]
    assert [(i['merchant_parts_num'], i['diff']) for i in lower['list']] == [('P-2', -8.0)]


def test_date_only_search_all_suppliers(monkeypatch):
    """核心场景：供应商留空、仅按日期过滤即出全部供应商对比结果"""
    cursor = patch_db(monkeypatch, quote_rows=[quote_row(price='97.50')],
                      baseline_rows=[('OE-A', '博世', 88.0)])
    result = svc.query_price_compare('', start_date='2026-10-01', end_date='2026-10-31',
                                     status='higher')

    assert result['data']['total'] == 1
    sql, params = cursor.executed[0]
    assert 'SUBSTRING(inquiry_date, 1, 10) >= %s' in sql
    assert params == [svc.BBRI_STORE_NAME, '2026-10-01', '2026-10-31']


def test_filter_values_allows_empty_store(monkeypatch):
    """列筛选候选同样支持供应商留空（全部供应商口径）"""
    patch_db(monkeypatch, quote_rows=[quote_row(brand='博世', price='97.50')],
             baseline_rows=[('OE-A', '博世', 88.0)])
    result = svc.filter_values('brand_name', '', status='higher')
    assert result['code'] == 0
    assert result['data']['values'] == [{'value': '博世', 'count': 1}]


# ===== 分页 =====

def test_memory_pagination(monkeypatch):
    """全量查询 + 内存分页：25 行、第2页每页20条 → 返回5行"""
    quote_rows = [quote_row('OE-%02d' % i, price=str(100 + i)) for i in range(25)]
    baseline_rows = [('OE-%02d' % i, '博世', 50.0) for i in range(25)]
    patch_db(monkeypatch, quote_rows=quote_rows, baseline_rows=baseline_rows)

    result = svc.query_price_compare('深圳巨牛汽配', page=2, page_size=20, status='higher')
    assert result['data']['total'] == 25
    assert len(result['data']['list']) == 5
    assert result['data']['list'][0]['decode_num'] == 'OE-20'


def test_pagination_bounds(monkeypatch):
    patch_db(monkeypatch)
    result = svc.query_price_compare('深圳巨牛汽配', page=-1, page_size=999, status='higher')
    assert result['data']['page'] == 1
    assert result['data']['page_size'] == 200  # 上限 200


# ===== 排序 =====

def _sort_fixture_rows():
    """默认排序：decode_num 升序、同OE卖家价格降序；OE-C 无基准不返回"""
    return [
        quote_row('OE-A', price='80.20'),   # diff -7.80
        quote_row('OE-A', price='70.00'),   # diff -18.00
        quote_row('OE-B', brand='曼牌', parts='机滤', price='40.00'),  # diff -5.50
        quote_row('OE-C', brand='NGK', parts='其他件', price='60.00'),  # 无基准
    ]


def _sort_patch(monkeypatch):
    baseline_rows = [('OE-A', '博世', 88.0), ('OE-B', '曼牌', 45.5)]
    return patch_db(monkeypatch, quote_rows=_sort_fixture_rows(), baseline_rows=baseline_rows)


def test_sort_numeric_desc(monkeypatch):
    _sort_patch(monkeypatch)
    items = svc.query_price_compare('深圳巨牛汽配', sort_column='diff', sort_dir='DESC',
                                    status='lower')['data']['list']
    assert [i['diff'] for i in items] == [-5.5, -7.8, -18.0]


def test_sort_numeric_asc(monkeypatch):
    _sort_patch(monkeypatch)
    items = svc.query_price_compare('深圳巨牛汽配', sort_column='bbri_price', sort_dir='asc',
                                    status='lower')['data']['list']
    assert [i['decode_num'] for i in items] == ['OE-B', 'OE-A', 'OE-A']


def test_sort_text_column_nulls_last(monkeypatch):
    """文本列按字符串比较，None 值恒排最后"""
    baseline_rows = [('OE-A', '博世', 88.0), ('OE-B', '曼牌', 45.5)]
    rows = _sort_fixture_rows()[:3] + [
        quote_row('OE-B', brand='曼牌', parts='机滤', warehouse=None, price='30.00'),
    ]
    patch_db(monkeypatch, quote_rows=rows, baseline_rows=baseline_rows)

    items = svc.query_price_compare('深圳巨牛汽配', sort_column='warehouse', sort_dir='desc',
                                    status='lower')['data']['list']
    assert items[-1]['warehouse'] is None
    assert all(i['warehouse'] is not None for i in items[:-1])


def test_sort_fallback_on_unknown_column(monkeypatch):
    """白名单外列回落默认排序（SQL 返回顺序）"""
    _sort_patch(monkeypatch)
    items = svc.query_price_compare('深圳巨牛汽配', sort_column='_action', sort_dir='desc',
                                    status='lower')['data']['list']
    assert [i['decode_num'] for i in items] == ['OE-A', 'OE-A', 'OE-B']
    assert [i['seller_price'] for i in items[:2]] == [80.2, 70.0]


# ===== 参数校验 =====

def test_bbri_store_raises(monkeypatch):
    patch_db(monkeypatch)
    with pytest.raises(ValueError):
        svc.query_price_compare(svc.BBRI_STORE_NAME, status='higher')


def test_invalid_status_raises(monkeypatch):
    patch_db(monkeypatch)
    with pytest.raises(ValueError):
        svc.query_price_compare('深圳巨牛汽配', status='bad')


def test_invalid_date_raises(monkeypatch):
    patch_db(monkeypatch)
    with pytest.raises(ValueError):
        svc.query_price_compare('深圳巨牛汽配', start_date='2026/10/01', status='higher')
