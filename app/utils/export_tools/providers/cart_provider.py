# -*- coding:utf-8 -*-
"""
购物车页面导出数据提供者
"""

import pymysql

from app.utils.database_connection import get_db_connection
from app.utils.export_tools import ExportConfig
from app.utils.export_tools.export_utils import (
    parse_supplier_string,
    parse_purchase_records,
    build_supplier_field,
)


# 导出字段顺序（与页面展示顺序保持一致）
CART_FIELDS = [
    'oe', 'supplier', 'brand', 'material_name', 'barcode', 'brand_code',
    'car_brand', 'tag', 'car_model', 'stock', 'on_way',
    'today_sales', 'sales_yesterday', 'sales_7d', 'sales_month', 'avg_sales_6m', 'avg_sales_12m',
    'inquiry_1m', 'inquiry_3m', 'national_inquiry_1m', 'national_inquiry_3m',
    'internal_remarks', 'stock_amount', 'sellable_days', 'cost_price', 'warning_status',
    'quantity', 'added_time', 'added_by'
]

# 字段 → 中文表头映射
CART_HEADERS = {
    'oe': 'OE',
    'supplier': '供应商',
    'brand': '品牌',
    'material_name': '物料名称',
    'barcode': '物料条码',
    'brand_code': '品牌号',
    'car_brand': '车型品牌',
    'tag': '标签',
    'car_model': '车型',
    'stock': '库存数量',
    'on_way': '在途数量',
    'today_sales': '今日销量',
    'sales_yesterday': '昨日销量',
    'sales_7d': '近7天销量',
    'sales_month': '本月销量',
    'avg_sales_6m': '近6个月月均销量',
    'avg_sales_12m': '近12个月月均销量',
    'inquiry_1m': '近1个月询价量',
    'inquiry_3m': '近3个月月均询价量',
    'national_inquiry_1m': '全国近1个月询价量',
    'national_inquiry_3m': '全国近3个月月均询价量',
    'internal_remarks': '内部备注',
    'stock_amount': '库存金额',
    'sellable_days': '成品可卖天数',
    'cost_price': '成本价',
    'warning_status': '预警状态',
    'quantity': '数量',
    'added_time': '加入时间',
    'added_by': '账户名',
}


def fetch_cart_data(**search_params) -> list:
    """
    根据搜索条件查询购物车表全量数据。

    搜索参数：
        store: 门店代码（必填）
        dimension: product/supplier，默认 product
        oe, barcode, material_name, brand, tag, car_model
    """
    store = search_params.get('store')
    if not store:
        return []

    dimension = search_params.get('dimension', 'product')

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        # 导出字段外额外查询 purchase_records，用于重构供应商字段
        query_fields = CART_FIELDS + ['purchase_records']
        fields_str = ', '.join([f'`{f}`' for f in query_fields])
        where_parts = ["`store` = %s"]
        params = [store]

        if search_params.get('oe'):
            where_parts.append("`oe` LIKE %s")
            params.append(f"%{search_params['oe']}%")

        if search_params.get('barcode'):
            where_parts.append("(`barcode` LIKE %s OR `brand_code` LIKE %s)")
            params.append(f"%{search_params['barcode']}%")
            params.append(f"%{search_params['barcode']}%")

        if search_params.get('material_name'):
            where_parts.append("`material_name` LIKE %s")
            params.append(f"%{search_params['material_name']}%")

        if search_params.get('brand'):
            where_parts.append("`brand` = %s")
            params.append(search_params['brand'])

        if search_params.get('tag'):
            where_parts.append("`tag` = %s")
            params.append(search_params['tag'])

        if search_params.get('car_model'):
            where_parts.append("`car_model` LIKE %s")
            params.append(f"%{search_params['car_model']}%")

        where_clause = " WHERE " + " AND ".join(where_parts)
        sql = f"SELECT {fields_str} FROM `crmapp_cart`{where_clause} ORDER BY added_time DESC"

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # 供应商维度：优先按 purchase_records 拆分，否则回退原 supplier 字符串
        if dimension == 'supplier':
            expanded_rows = []
            for row in rows:
                purchase_records = row.get('purchase_records', '')
                suppliers = parse_purchase_records(purchase_records)
                fallback_to_string = not suppliers
                if fallback_to_string:
                    supplier_tuples = parse_supplier_string(row.get('supplier', ''))
                    # 补齐日期、数量占位符，保持统一四元组格式
                    suppliers = [('', name, '-', price) for name, price in supplier_tuples]

                for date, supplier_name, quantity, price in suppliers:
                    new_row = row.copy()
                    if fallback_to_string and price == 'N/A':
                        new_row['supplier'] = supplier_name
                    elif date:
                        new_row['supplier'] = f"{date} - {supplier_name} - {quantity} - {price}"
                    else:
                        new_row['supplier'] = f"{supplier_name} - {quantity} - {price}"
                    expanded_rows.append(new_row)
            rows = expanded_rows
        else:
            # 产品维度：供应商字段优先使用 purchase_records JSON，否则回退原字段
            for row in rows:
                row['supplier'] = build_supplier_field(
                    row.get('supplier'),
                    row.get('purchase_records')
                )

        return rows
    finally:
        conn.close()


CART_EXPORT_CONFIG = ExportConfig(
    fields=CART_FIELDS,
    headers=CART_HEADERS,
    filename_template='购物车_{timestamp}.xlsx',
    sheet_name='购物车数据',
)
