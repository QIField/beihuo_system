"""
修理厂询价单查询服务单测（mock 数据库游标，不连真实库）

覆盖：车辆品牌（car_model 车型）模糊搜索条件、多条件 AND 组合、
查询与列筛选候选值级联传参
"""
from app.services.cass_inquiry_service import query_service as qs
from app.services.cass_inquiry_service.query_service import CassInquiryQueryService

svc = CassInquiryQueryService()


class FakeCursor:
    """按 SQL 特征路由返回数据的假游标：COUNT→计数、其余→配置行"""

    def __init__(self, count_rows=(), rows=()):
        self.count_rows = count_rows
        self.rows = rows
        self.executed = []
        self.last_sql = ''

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.executed.append((sql, params))

    def fetchone(self):
        if 'COUNT(*)' in self.last_sql:
            return self.count_rows[0] if self.count_rows else (0,)
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def patch_db(monkeypatch, count_rows=(), rows=()):
    cursor = FakeCursor(count_rows=count_rows, rows=rows)
    monkeypatch.setattr(qs, 'db_cursor', lambda dict_cursor=False: cursor)
    return cursor


# ===== 车辆品牌（车型）搜索条件 =====

def test_build_where_car_model_like():
    """车辆品牌按 car_model 模糊匹配，关键词去空格"""
    where, params = svc._build_where(None, None, None, None, ' 奔驰 ', None, None)
    assert where == 'WHERE car_model LIKE %s'
    assert params == ['%奔驰%']


def test_build_where_combined_conditions():
    """car_model 与日期/品牌/供应商等条件 AND 组合，参数按占位符顺序"""
    where, params = svc._build_where(
        '2026-10-01', '2026-10-31', None, '博世', '奔驰', '广州鸿达', None)
    assert where == ('WHERE inquiry_date >= %s AND inquiry_date < %s '
                     'AND brand_name LIKE %s AND car_model LIKE %s AND store_name LIKE %s')
    assert params == ['2026-10-01', '2026-11-01', '%博世%', '%奔驰%', '%广州鸿达%']


def test_query_quotes_passes_car_model(monkeypatch):
    """列表查询 SQL 携带 car_model 模糊条件"""
    cursor = patch_db(monkeypatch, count_rows=[(3,)], rows=[])
    result = svc.query_quotes(car_model='奔驰')

    assert result['code'] == 0
    assert result['data']['total'] == 3
    count_sql, count_params = cursor.executed[0]
    assert 'car_model LIKE %s' in count_sql
    assert '%奔驰%' in count_params


def test_filter_values_cascades_car_model(monkeypatch):
    """列筛选候选值级联车辆品牌条件"""
    cursor = patch_db(monkeypatch, rows=[('博世', 2)])
    result = svc.filter_values('brand_name', car_model='奔驰')

    assert result['code'] == 0
    assert result['data']['values'] == [{'value': '博世', 'count': 2}]
    sql, params = cursor.executed[0]
    assert 'car_model LIKE %s' in sql
    assert '%奔驰%' in params
