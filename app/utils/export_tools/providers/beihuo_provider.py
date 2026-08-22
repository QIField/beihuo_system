# -*- coding:utf-8 -*-
"""
主页面备货表格导出数据提供者
"""

import pymysql

from app.utils.database_connection import get_db_connection
from app.utils.export_tools import ExportConfig
from app.utils.export_tools.export_utils import build_supplier_field


# 导出字段顺序（与页面展示顺序保持一致）
BEIHUO_FIELDS = [
    'oe', '物料名称', '品牌', '物料条码', '车型品牌', '标签',
    '库存金额', '成本价', '库存数量', '近12个月月均销量', '近6个月月均销量',
    '本月销量', '近7天销量', '昨日销量', '今日销量', '成品可卖天数',
    '预警状态', '供应商', '近1个月询价量', '近3个月月均询价量',
    '全国近1个月询价量', '全国近3个月月均询价量', '品牌号', '内部备注',
    '在途数量', '车型'
]

# 字段 → 中文表头映射
BEIHUO_HEADERS = {field: field for field in BEIHUO_FIELDS}


def fetch_beihuo_data(**search_params) -> list:
    """
    根据搜索条件查询备货表全量数据。

    搜索参数：
        store: 门店/组织代码（必填）
        oe, supplier, brand, material_name, tag, barcode, car_brand
    """
    store = search_params.get('store')
    if not store:
        return []

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        # 导出字段外额外查询 purchase_records，用于重构供应商字段
        query_fields = BEIHUO_FIELDS + ['purchase_records']
        fields_str = ', '.join([f'`{f}`' for f in query_fields])
        where_parts = ["`company` = %s"]
        params = [store]

        if search_params.get('oe'):
            where_parts.append("`oe` LIKE %s")
            params.append(f"%{search_params['oe']}%")

        if search_params.get('supplier'):
            where_parts.append("`供应商` LIKE %s")
            params.append(f"%{search_params['supplier']}%")

        if search_params.get('brand'):
            where_parts.append("`品牌` = %s")
            params.append(search_params['brand'])

        if search_params.get('material_name'):
            where_parts.append("`物料名称` LIKE %s")
            params.append(f"%{search_params['material_name']}%")

        if search_params.get('tag'):
            where_parts.append("`标签` = %s")
            params.append(search_params['tag'])

        if search_params.get('barcode'):
            where_parts.append("`物料条码` LIKE %s")
            params.append(f"%{search_params['barcode']}%")

        if search_params.get('car_brand'):
            where_parts.append("`车型品牌` = %s")
            params.append(search_params['car_brand'])

        where_clause = " WHERE " + " AND ".join(where_parts)
        sql = (
            f"SELECT {fields_str} FROM `crmapp_beihuo`{where_clause} "
            "ORDER BY CASE WHEN `oe` IS NULL OR `oe` = '' THEN 1 ELSE 0 END, `oe`"
        )

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # 供应商字段优先使用 purchase_records JSON，否则回退原字段
        for row in rows:
            row['供应商'] = build_supplier_field(
                row.get('供应商'),
                row.get('purchase_records')
            )

        return rows
    finally:
        conn.close()


BEIHUO_EXPORT_CONFIG = ExportConfig(
    fields=BEIHUO_FIELDS,
    headers=BEIHUO_HEADERS,
    filename_template='备货数据_{timestamp}.xlsx',
    sheet_name='备货数据',
)
