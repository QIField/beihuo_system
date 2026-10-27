"""
修理厂询价单 · 供应商价格对比服务

以译码OE号(decode_num)为比对键，将所选供应商报价与巴博瑞（佛山巴博瑞汽配）比对，
价格字段取卖家价格(seller_price，varchar 转数值)；巴博瑞同 OE 多条记录时取最低价作基准。
连接方式：PyMySQL db_cursor，与 query_service 同源（跟随启动菜单选库）。
"""

import json

from app.utils.database_connection import db_cursor

# 巴博瑞供应商名（与前端 BBRI_STORE_NAME 一致）
BBRI_STORE_NAME = '佛山巴博瑞汽配'

# 允许排序的列白名单（数值列按 float 比较，文本列按字符串比较；bbri_price/diff 为计算列，内存排序）
NUMERIC_SORT_COLUMNS = {'seller_price', 'bbri_price', 'diff', 'num'}
TEXT_SORT_COLUMNS = {'decode_num', 'brand_name', 'parts_name', 'quality_name'}
SORTABLE_COLUMNS = NUMERIC_SORT_COLUMNS | TEXT_SORT_COLUMNS

# 允许列头菜单筛选的列（含计算列 compare_status，中文案与表格显示一致）
FILTERABLE_COLUMNS = {'decode_num', 'brand_name', 'parts_name', 'quality_name', 'num', 'compare_status'}

# 对比结果状态码与中文文案映射（筛选值用中文，比对时映射回状态码）
COMPARE_STATUS_TEXT = {
    'higher': '高于巴博瑞',
    'lower': '低于巴博瑞',
    'equal': '与巴博瑞持平',
    'no_bbri': '巴博瑞无同OE报价',
}
STATUS_CODE_BY_TEXT = {text: code for code, text in COMPARE_STATUS_TEXT.items()}
# 状态码固定展示顺序
COMPARE_STATUS_ORDER = list(COMPARE_STATUS_TEXT.keys())


def list_stores() -> list:
    """
    查询供应商候选（全表去重，排除巴博瑞自身与空值）

    :return: {'code': 0, 'data': {'stores': [...]}}
    """
    sql = """
        SELECT DISTINCT store_name
        FROM cass_inquiry_quote
        WHERE store_name IS NOT NULL AND store_name != ''
          AND store_name != %s
        ORDER BY store_name
    """
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute(sql, (BBRI_STORE_NAME,))
        rows = cursor.fetchall()
    return {'code': 0, 'data': {'stores': [row[0] for row in rows]}}


def _build_baseline() -> dict:
    """
    构建巴博瑞基准价映射：decode_num -> 同 OE 最低卖家价格（数值比较，排除非法值）
    """
    sql = """
        SELECT decode_num, MIN(seller_price + 0)
        FROM cass_inquiry_quote
        WHERE store_name = %s
          AND decode_num IS NOT NULL AND decode_num != ''
        GROUP BY decode_num
    """
    baseline = {}
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute(sql, (BBRI_STORE_NAME,))
        for decode_num, min_price in cursor.fetchall():
            price = float(min_price) if min_price is not None else 0
            if price > 0:
                baseline[decode_num] = round(price, 2)
    return baseline


def query_price_compare(store_name=None, page=1, page_size=20, sort_column=None, sort_dir=None,
                        column_filters=None):
    """
    分页查询供应商与巴博瑞的价格对比

    :param store_name: 供应商名称（必填，精确匹配）
    :param page: 页码（从1开始）
    :param page_size: 每页条数
    :param sort_column: 排序列（白名单内，含计算列 bbri_price/diff；白名单外回落默认排序）
    :param sort_dir: 排序方向（asc/desc），空值行恒排最后
    :param column_filters: 列头菜单筛选 JSON（如 {"brand_name": ["博世"]}，列间 AND，白名单外忽略）
    :return: {'code': 0, 'data': {'list': [...], 'total': n, 'page': p, 'page_size': s}}
             每行含 decode_num/brand_name/parts_name/quality_name/num/seller_price/
             bbri_price/diff/compare_status（higher/lower/equal/no_bbri）
    """
    store = (store_name or '').strip()
    if not store:
        raise ValueError('请选择供应商')
    if store == BBRI_STORE_NAME:
        raise ValueError('巴博瑞自身无需比对')
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 200)

    rows = _fetch_store_quotes(store)
    baseline = _build_baseline()
    items = [_build_compare_row(row, baseline) for row in rows]
    items = _apply_column_filters(items, _parse_column_filters(column_filters))
    items = _sort_items(items, sort_column, sort_dir)

    total = len(items)
    offset = (page - 1) * page_size

    return {
        'code': 0,
        'data': {
            'list': items[offset:offset + page_size],
            'total': total,
            'page': page,
            'page_size': page_size,
        }
    }


def filter_values(column, store_name, column_filters=None):
    """
    查询某列的全量去重候选值及出现次数（供列头菜单筛选勾选）

    候选值按"其他列已生效筛选"级联（本列自身条件不参与，由前端排除后传入）

    :return: {'code': 0, 'data': {'values': [{'value': v, 'count': n}, ...]}}
    """
    if column not in FILTERABLE_COLUMNS:
        raise ValueError(f'不支持的筛选列: {column}')
    store = (store_name or '').strip()
    if not store:
        raise ValueError('请选择供应商')

    rows = _fetch_store_quotes(store)
    filters = _parse_column_filters(column_filters)
    filters.pop(column, None)  # 兜底排除本列（本列条件不缩小自己的候选）
    groups = {}

    if column == 'compare_status':
        # 计算列：构建比对行后按状态码计数，候选值为中文文案、按固定顺序输出
        baseline = _build_baseline()
        items = [_build_compare_row(row, baseline) for row in rows]
        items = _apply_column_filters(items, filters)
        counts = {}
        for item in items:
            counts[item['compare_status']] = counts.get(item['compare_status'], 0) + 1
        values = [
            {'value': COMPARE_STATUS_TEXT[code], 'count': counts[code]}
            for code in COMPARE_STATUS_ORDER if code in counts
        ]
        return {'code': 0, 'data': {'values': values}}

    for row in rows:
        item = dict(zip(
            ('decode_num', 'brand_name', 'parts_name', 'quality_name', 'num', 'seller_price'),
            row,
        ))
        if not _match_column_filters(item, filters):
            continue
        value = item.get(column)
        if value is None or str(value).strip() == '':
            continue
        key = str(value)
        groups[key] = groups.get(key, 0) + 1

    values = [{'value': key, 'count': count} for key, count in sorted(groups.items())]
    return {'code': 0, 'data': {'values': values}}


def _parse_column_filters(column_filters):
    """
    解析列头菜单筛选 JSON（列间 AND，白名单外字段忽略）

    :return: {列名: [值, ...]}，解析失败或为空返回 {}
    """
    if not column_filters:
        return {}
    try:
        raw = json.loads(column_filters)
    except (TypeError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    filters = {}
    for col, values in raw.items():
        col = str(col)
        if col not in FILTERABLE_COLUMNS or not isinstance(values, list):
            continue
        cleaned = [str(v) for v in values if v is not None]
        if not cleaned:
            continue
        if col == 'compare_status':
            # 中文文案映射回状态码（兼容直接传状态码）
            filters[col] = [STATUS_CODE_BY_TEXT.get(v, v) for v in cleaned]
        else:
            filters[col] = cleaned
    return filters


def _apply_column_filters(items, filters):
    """应用列头菜单筛选（列间 AND，白名单外字段已在解析时忽略）"""
    if not filters:
        return items
    return [item for item in items if _match_column_filters(item, filters)]


def _match_column_filters(item, filters):
    """单行匹配：所有筛选列的值均需命中候选列表（str 口径，空值不命中）"""
    for col, allowed in filters.items():
        value = item.get(col)
        if value is None or str(value) not in allowed:
            return False
    return True


def _fetch_store_quotes(store):
    """
    全量查询供应商报价记录（含译码OE号非空行），默认按译码OE号升序、同OE内卖家价格降序

    单供应商记录量为几百~几千行级，全量取出后在内存排序分页，
    使计算列（巴博瑞基准价/价差）也能参与排序
    """
    sql = """
        SELECT decode_num, brand_name, parts_name, quality_name, num, seller_price
        FROM cass_inquiry_quote
        WHERE store_name = %s AND decode_num IS NOT NULL AND decode_num != ''
        ORDER BY decode_num, seller_price + 0 DESC, id DESC
    """
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute(sql, (store,))
        return cursor.fetchall()


def _sort_items(items, sort_column, sort_dir):
    """
    内存排序：数值列 float 比较（varchar/None 容错），文本列字符串比较；空值行恒排最后

    排序列不在白名单时回落默认顺序（SQL 已按 decode_num 升序返回）
    """
    if sort_column not in SORTABLE_COLUMNS:
        return items
    desc = str(sort_dir or '').upper() == 'DESC'

    if sort_column in NUMERIC_SORT_COLUMNS:
        def value_key(item):
            value = item.get(sort_column)
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    else:
        def value_key(item):
            value = item.get(sort_column)
            return None if value is None else str(value)

    non_null = [it for it in items if value_key(it) is not None]
    null_items = [it for it in items if value_key(it) is None]
    return sorted(non_null, key=value_key, reverse=desc) + null_items


def _build_compare_row(row, baseline):
    """
    组装单行对比结果：状态与价差均基于巴博瑞同 OE 最低价基准
    """
    decode_num, brand_name, parts_name, quality_name, num, seller_price = row
    price = _to_float(seller_price)
    base = baseline.get(decode_num)

    if base is None:
        status = 'no_bbri'
        diff = None
    elif price is None or base <= 0:
        status = 'no_bbri'
        diff = None
    elif price > base:
        status = 'higher'
        diff = round(price - base, 2)
    elif price < base:
        status = 'lower'
        diff = round(price - base, 2)
    else:
        status = 'equal'
        diff = 0.0

    return {
        'decode_num': decode_num,
        'brand_name': brand_name,
        'parts_name': parts_name,
        'quality_name': quality_name,
        'num': num,
        'seller_price': price,
        'bbri_price': base,
        'diff': diff,
        'compare_status': status,
    }


def _to_float(value):
    """价格字段转 float（varchar 口径），非法值返回 None"""
    if value is None:
        return None
    try:
        price = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return round(price, 2) if price > 0 else None
