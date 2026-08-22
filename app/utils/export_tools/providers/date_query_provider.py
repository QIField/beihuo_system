# -*- coding:utf-8 -*-
"""
日期查询页面导出数据提供者

数据来源于当前用户/组织的 crmapp_date_search 缓存表，
过滤逻辑与 /api/date_ordercount_search 保持一致。
"""

import pymysql
from flask import session

from app.services.sales_frequency_service import enrich_data_with_frequency
from app.utils.database_connection import get_db_connection
from app.utils.export_tools import ExportConfig
from app.utils.export_tools.export_utils import build_supplier_field
from app.utils.search.parser import parse_comma, parse_space


# 导出字段顺序（排除选择框与行号）
DATE_QUERY_FIELDS = [
    'oe', '物料名称', '品牌', '物料条码', '品牌号', '替换号',
    '车型品牌', '标签', '车型', '库存数量', '在途数量', '销量',
    '销量数据', '库存金额', '成本价', '成品可卖天数', '预警状态',
    '供应商', '近1个月询价量', '近3个月月均询价量',
    '全国近1个月询价量', '全国近3个月月均询价量',
    '内部备注', 'waiting_time', 'frequency'
]

# 字段 → 中文表头映射
DATE_QUERY_HEADERS = {
    'oe': 'OE',
    '物料名称': '物料名称',
    '品牌': '品牌',
    '物料条码': '物料条码',
    '品牌号': '品牌号',
    '替换号': '替换号',
    '车型品牌': '车型品牌',
    '标签': '标签',
    '车型': '车型',
    '库存数量': '库存数量',
    '在途数量': '在途数量',
    '销量': '销量',
    '销量数据': '销量数据',
    '库存金额': '库存金额',
    '成本价': '成本价',
    '成品可卖天数': '成品可卖天数',
    '预警状态': '预警状态',
    '供应商': '供应商',
    '近1个月询价量': '近1个月询价量',
    '近3个月月均询价量': '近3个月月均询价量',
    '全国近1个月询价量': '全国近1个月询价量',
    '全国近3个月月均询价量': '全国近3个月月均询价量',
    '内部备注': '内部备注',
    'waiting_time': '待仓时间',
    'frequency': '频次',
}


def _parse_filter_list(value):
    """将多行/空格分隔的搜索值解析为列表。"""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value)
    if '\n' in text:
        return [item.strip() for item in text.split('\n') if item.strip()]
    return parse_space(text)


def _match_list_field(item_value, filter_list):
    """支持模糊包含匹配。"""
    if not filter_list:
        return True
    row_value = str(item_value or '').lower()
    return any(str(f).lower() in row_value for f in filter_list)


def _match_exact_list_field(item_value, filter_list):
    """支持精确匹配（用于筛选面板）。"""
    if not filter_list:
        return True
    row_value = str(item_value or '')
    return row_value in [str(f) for f in filter_list]


def fetch_date_query_data(**search_params) -> list:
    """
    根据搜索条件查询日期查询缓存表全量数据。

    搜索参数：
        company: 组织代码（默认从 session 读取）
        username: 用户名（默认从 session 读取）
        oe, barcode, material_name, brand, car_brand, tag: 搜索面板条件
        filter_品牌, filter_车型品牌, filter_标签: 筛选面板精确匹配条件
        field, order: 排序字段与方向
    """
    company = search_params.get('company') or session.get('last_date_ordercount_company')
    username = search_params.get('username') or session.get('username', 'default_user')

    if not company:
        return []

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        cursor.execute(
            """
            SELECT * FROM crmapp_date_search
            WHERE username = %s AND company = %s
            ORDER BY id
            """,
            (username, company)
        )
        cached_data = cursor.fetchall()
    finally:
        conn.close()

    if not cached_data:
        return []

    # 解析搜索面板条件
    oe_list = _parse_filter_list(search_params.get('oe'))
    barcode_list = _parse_filter_list(search_params.get('barcode'))
    material_name_list = parse_comma(search_params.get('material_name', '')) if search_params.get('material_name') else []
    brand_list = _parse_filter_list(search_params.get('brand'))
    car_brand_list = _parse_filter_list(search_params.get('car_brand'))
    tag_list = _parse_filter_list(search_params.get('tag'))

    # 解析筛选面板条件
    panel_brand = search_params.get('filter_品牌') or search_params.get('filterBrand') or []
    panel_car_brand = search_params.get('filter_车型品牌') or search_params.get('filterCarBrand') or []
    panel_tag = search_params.get('filter_标签') or search_params.get('filterTag') or []

    filtered_data = []
    for item in cached_data:
        if oe_list and item.get('oe', '') not in oe_list:
            continue

        if not _match_list_field(item.get('物料条码', ''), barcode_list):
            if not _match_list_field(item.get('品牌号', ''), barcode_list):
                continue

        if not _match_list_field(item.get('物料名称', ''), material_name_list):
            if not _match_list_field(item.get('品牌号', ''), material_name_list):
                continue

        if not _match_list_field(item.get('品牌', ''), brand_list):
            continue

        if not _match_list_field(item.get('车型品牌', ''), car_brand_list):
            continue

        if not _match_list_field(item.get('标签', ''), tag_list):
            continue

        # 筛选面板精确匹配
        if not _match_exact_list_field(item.get('品牌', ''), panel_brand):
            continue
        if not _match_exact_list_field(item.get('车型品牌', ''), panel_car_brand):
            continue
        if not _match_exact_list_field(item.get('标签', ''), panel_tag):
            continue

        filtered_data.append(item)

    # 排序
    field = search_params.get('field', '').strip()
    order = search_params.get('order', '').strip()
    if field and order:
        reverse_order = order.lower() == 'desc'
        numeric_fields = {
            '今日销量', '昨日销量', '本月销量', '近1个月询价量', '近3个月月均询价量',
            '近7天销量', '近6个月月均销量', '近12个月月均销量', '库存数量', '成本价',
            '库存金额', '成品可卖天数', '在途数量'
        }
        try:
            if field in numeric_fields:
                filtered_data.sort(key=lambda x: float(x.get(field, 0) or 0), reverse=reverse_order)
            else:
                filtered_data.sort(key=lambda x: str(x.get(field, '') or '').lower(), reverse=reverse_order)
        except Exception as e:
            print(f"[日期查询导出] 排序失败: {e}")

    # 补充频次数据
    search_start_date = session.get('last_date_ordercount_start_date')
    search_end_date = session.get('last_date_ordercount_end_date')
    if filtered_data and search_start_date and search_end_date:
        filtered_data, freq_error = enrich_data_with_frequency(
            data_list=filtered_data,
            barcode_field='物料条码',
            start_date=search_start_date,
            end_date=search_end_date,
            frequency_field='frequency'
        )
        if freq_error:
            print(f"[日期查询导出] 频次计算错误: {freq_error}")
    elif filtered_data:
        for item in filtered_data:
            item['frequency'] = 0

    # 供应商字段优先使用 purchase_records JSON，否则回退原字段
    for item in filtered_data:
        item['供应商'] = build_supplier_field(
            item.get('供应商'),
            item.get('purchase_records')
        )

    return filtered_data


DATE_QUERY_EXPORT_CONFIG = ExportConfig(
    fields=DATE_QUERY_FIELDS,
    headers=DATE_QUERY_HEADERS,
    filename_template='日期查询数据_{timestamp}.xlsx',
    sheet_name='日期查询数据',
)
