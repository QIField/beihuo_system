"""
供应商价格对比服务单测（mock 数据库游标，不连真实库）

覆盖：供应商候选（排除巴博瑞）、基准映射（同OE最低价）、四态判定
（higher/lower/equal/no_bbri）、价差计算、分页参数、参数校验
"""
import pytest

from app.services.cass_inquiry_service import price_compare_service as svc


class RoutedCursor:
    """按 SQL 特征路由返回数据的假游标：COUNT→计数、GROUP BY→基准、其余→报价行"""

    def __init__(self, count_rows, quote_rows, baseline_rows):
        self.count_rows = count_rows
        self.quote_rows = quote_rows
        self.baseline_rows = baseline_rows
        self.executed = []
        self.last_sql = ''

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.executed.append((sql, params))

    def fetchone(self):
        rows = self._rows()
        return rows[0] if rows else None

    def fetchall(self):
        return self._rows()

    def _rows(self):
        if 'COUNT(*)' in self.last_sql:
            return self.count_rows
        if 'GROUP BY' in self.last_sql:
            return self.baseline_rows
        return self.quote_rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def patch_db(monkeypatch, count_rows=None, quote_rows=None, baseline_rows=None):
    cursor = RoutedCursor(count_rows or [], quote_rows or [], baseline_rows or [])
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


# ===== 比对状态与价差 =====

def test_compare_status_and_diff(monkeypatch):
    baseline_rows = [('OE-A', 88.0), ('OE-B', 45.5)]
    quote_rows = [
        ('OE-A', '博世', '火花塞', '品牌件', '2', '97.50'),   # 高于基准 +9.50
        ('OE-A', '博世', '火花塞', '品牌件', '2', '88.00'),   # 持平
        ('OE-A', '博世', '火花塞', '品牌件', '2', '80.20'),   # 低于基准 -7.80
        ('OE-B', '曼牌', '机滤', '品牌件', '1', '40.00'),     # 低于基准 -5.50
        ('OE-C', 'NGK', '其他件', '品牌件', '1', '60.00'),    # 巴博瑞无同OE报价
    ]
    patch_db(monkeypatch, count_rows=[(5,)], quote_rows=quote_rows, baseline_rows=baseline_rows)

    result = svc.query_price_compare('广州鸿达汽配')

    assert result['code'] == 0
    assert result['data']['total'] == 5
    items = result['data']['list']
    assert [i['compare_status'] for i in items] == ['higher', 'equal', 'lower', 'lower', 'no_bbri']
    assert items[0]['bbri_price'] == 88.0
    assert items[0]['diff'] == 9.5
    assert items[1]['diff'] == 0.0
    assert items[2]['diff'] == -7.8
    assert items[4]['bbri_price'] is None
    assert items[4]['diff'] is None


def test_baseline_takes_min_price(monkeypatch):
    """基准 SQL 聚合同 OE 最低价（MIN），服务层直接映射"""
    baseline_rows = [('OE-A', 45.0)]
    quote_rows = [('OE-A', '博世', '火花塞', '品牌件', '2', '50.00')]
    patch_db(monkeypatch, count_rows=[(1,)], quote_rows=quote_rows, baseline_rows=baseline_rows)

    items = svc.query_price_compare('深圳巨牛汽配')['data']['list']
    assert items[0]['bbri_price'] == 45.0
    assert items[0]['compare_status'] == 'higher'
    assert items[0]['diff'] == 5.0


def test_baseline_ignores_non_positive(monkeypatch):
    """基准价 0/None 等非法值不参与映射，对应行判为 no_bbri"""
    baseline_rows = [('OE-A', 0), ('OE-B', None)]
    quote_rows = [
        ('OE-A', '博世', '火花塞', '品牌件', '2', '50.00'),
        ('OE-B', '曼牌', '机滤', '品牌件', '1', '40.00'),
    ]
    patch_db(monkeypatch, count_rows=[(2,)], quote_rows=quote_rows, baseline_rows=baseline_rows)

    items = svc.query_price_compare('深圳巨牛汽配')['data']['list']
    assert all(i['compare_status'] == 'no_bbri' for i in items)
    assert all(i['bbri_price'] is None and i['diff'] is None for i in items)


def test_invalid_seller_price_row(monkeypatch):
    """卖家价格非法（None/非数字/非正数）时不参与比较，判为 no_bbri"""
    baseline_rows = [('OE-A', 88.0)]
    quote_rows = [
        ('OE-A', '博世', '火花塞', '品牌件', '2', None),
        ('OE-A', '博世', '火花塞', '品牌件', '2', 'abc'),
        ('OE-A', '博世', '火花塞', '品牌件', '2', '0'),
    ]
    patch_db(monkeypatch, count_rows=[(3,)], quote_rows=quote_rows, baseline_rows=baseline_rows)

    items = svc.query_price_compare('深圳巨牛汽配')['data']['list']
    assert all(i['compare_status'] == 'no_bbri' for i in items)
    assert all(i['seller_price'] is None for i in items)


# ===== 分页 =====

def test_memory_pagination(monkeypatch):
    """全量查询 + 内存分页：25 行、第2页每页20条 → 返回5行"""
    quote_rows = [('OE-%02d' % i, '博世', '火花塞', '品牌件', '2', str(100 + i)) for i in range(25)]
    patch_db(monkeypatch, quote_rows=quote_rows, baseline_rows=[])
    result = svc.query_price_compare('深圳巨牛汽配', page=2, page_size=20)
    assert result['data']['total'] == 25
    assert len(result['data']['list']) == 5
    assert result['data']['list'][0]['decode_num'] == 'OE-20'


def test_pagination_bounds(monkeypatch):
    patch_db(monkeypatch, quote_rows=[])
    result = svc.query_price_compare('深圳巨牛汽配', page=-1, page_size=999)
    assert result['data']['page'] == 1
    assert result['data']['page_size'] == 200  # 上限 200


# ===== 排序 =====

def _sort_fixture_rows():
    return [
        ('OE-A', '博世', '火花塞', '品牌件', '4', '97.50'),   # diff +9.50
        ('OE-A', '博世', '火花塞', '品牌件', '2', '88.00'),   # diff 0
        ('OE-B', '曼牌', '机滤', '品牌件', '1', '40.00'),     # diff -5.50
        ('OE-C', 'NGK', '其他件', '品牌件', '1', '60.00'),    # no_bbri → bbri_price/diff 为 None
    ]


def test_sort_numeric_desc_nulls_last(monkeypatch):
    """数值列降序：None（无基准行）恒排最后"""
    baseline_rows = [('OE-A', 88.0), ('OE-B', 45.5)]
    patch_db(monkeypatch, quote_rows=_sort_fixture_rows(), baseline_rows=baseline_rows)

    items = svc.query_price_compare('深圳巨牛汽配', sort_column='diff', sort_dir='DESC')['data']['list']
    diffs = [i['diff'] for i in items]
    assert diffs[:3] == [9.5, 0.0, -5.5]
    assert items[3]['compare_status'] == 'no_bbri'  # None 排最后


def test_sort_numeric_asc(monkeypatch):
    """数值列升序：bbri_price 45.5 < 88.0 < None"""
    baseline_rows = [('OE-A', 88.0), ('OE-B', 45.5)]
    patch_db(monkeypatch, quote_rows=_sort_fixture_rows(), baseline_rows=baseline_rows)

    items = svc.query_price_compare('深圳巨牛汽配', sort_column='bbri_price', sort_dir='asc')['data']['list']
    assert [i['decode_num'] for i in items[:3]] == ['OE-B', 'OE-A', 'OE-A']
    assert items[3]['compare_status'] == 'no_bbri'  # None 排最后


def test_sort_text_column(monkeypatch):
    """文本列按字符串比较"""
    patch_db(monkeypatch, quote_rows=_sort_fixture_rows(), baseline_rows=[])
    items = svc.query_price_compare('深圳巨牛汽配', sort_column='decode_num', sort_dir='desc')['data']['list']
    assert [i['decode_num'] for i in items] == ['OE-C', 'OE-B', 'OE-A', 'OE-A']


def test_sort_fallback_on_unknown_column(monkeypatch):
    """白名单外列回落默认排序（SQL 返回顺序：decode_num 升序、同OE价格降序）"""
    patch_db(monkeypatch, quote_rows=_sort_fixture_rows(), baseline_rows=[])
    items = svc.query_price_compare('深圳巨牛汽配', sort_column='_action', sort_dir='desc')['data']['list']
    assert [i['decode_num'] for i in items] == ['OE-A', 'OE-A', 'OE-B', 'OE-C']
    assert [i['seller_price'] for i in items[:2]] == [97.5, 88.0]


# ===== 参数校验 =====

def test_empty_store_raises(monkeypatch):
    patch_db(monkeypatch)
    with pytest.raises(ValueError):
        svc.query_price_compare('  ')


def test_bbri_store_raises(monkeypatch):
    patch_db(monkeypatch)
    with pytest.raises(ValueError):
        svc.query_price_compare(svc.BBRI_STORE_NAME)
