#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙虚拟库存导入模板 Excel 生成工具
基于 static/excel/qpl_virtual_qty.xlsx 模板填充数据
"""

import os
import shutil

import openpyxl

# 模板路径（只读）
TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    'static', 'excel', 'qpl_virtual_qty.xlsx'
)

# 数据起始行（第1行说明，第2行表头）
DATA_START_ROW = 3

# 列号映射（A=1）
COL_PRODUCT_NAME = 1
COL_BRAND = 2
COL_QUALITY = 3
COL_OE = 4
COL_BRAND_PART_NO = 5
COL_MERCHANT_CODE = 6
COL_PRICE = 7
COL_STOCK = 8
COL_IN_STOCK = 9
COL_STOCK_TIME = 10
COL_AUTO_QUOTE = 11


def _safe_float(value):
    if value is None:
        return 0.0
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return 0.0


def _safe_int(value):
    if value is None:
        return 0
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return 0


def build_import_excel(rows, output_path):
    """
    根据模板生成汽配龙虚拟库存导入 Excel

    Args:
        rows: 可迭代对象，元素为 dict，需包含
              product_name, brand, quality, oe, brand_part_no,
              price, stock, in_stock, stock_time, auto_quote
        output_path: 生成的 Excel 文件路径

    Returns:
        str: output_path
    """
    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"模板文件不存在: {TEMPLATE_PATH}")

    shutil.copyfile(TEMPLATE_PATH, output_path)

    wb = openpyxl.load_workbook(output_path)
    ws = wb.active

    # 清空第3行起的旧数据
    max_row = ws.max_row
    if max_row >= DATA_START_ROW:
        ws.delete_rows(DATA_START_ROW, max_row - DATA_START_ROW + 1)

    for row_data in rows:
        row = DATA_START_ROW
        ws.cell(row=row, column=COL_PRODUCT_NAME, value=row_data.get('product_name'))
        ws.cell(row=row, column=COL_BRAND, value=row_data.get('brand'))
        ws.cell(row=row, column=COL_QUALITY, value=row_data.get('quality'))
        ws.cell(row=row, column=COL_OE, value=row_data.get('oe'))
        ws.cell(row=row, column=COL_BRAND_PART_NO, value=row_data.get('brand_part_no'))
        ws.cell(row=row, column=COL_MERCHANT_CODE, value=row_data.get('merchant_code'))
        ws.cell(row=row, column=COL_PRICE, value=row_data.get('price'))
        ws.cell(row=row, column=COL_STOCK, value=row_data.get('stock'))
        ws.cell(row=row, column=COL_IN_STOCK, value=row_data.get('in_stock'))
        ws.cell(row=row, column=COL_STOCK_TIME, value=row_data.get('stock_time'))
        ws.cell(row=row, column=COL_AUTO_QUOTE, value=row_data.get('auto_quote'))
        DATA_START_ROW += 1

    wb.save(output_path)
    wb.close()
    return output_path


def convert_records_to_rows(records):
    """
    将数据库记录列表转换为 Excel 行数据

    Args:
        records: 元素为 dict，需包含
                 product_name, oe, brand_part_no, reference_price, number_of_inventories

    Returns:
        list[dict]: Excel 行数据列表
    """
    rows = []
    for record in records:
        reference_price = _safe_float(record.get('reference_price'))
        sale_price = round(reference_price * 1.15, 2) if reference_price else 0.0

        rows.append({
            'product_name': record.get('product_name'),
            'brand': record.get('brand'),
            'quality': record.get('quality'),
            'oe': record.get('oe'),
            'brand_part_no': record.get('brand_part_no'),
            'merchant_code': None,
            'price': sale_price,
            'stock': _safe_int(record.get('number_of_inventories')),
            'in_stock': '否',
            'stock_time': '1天',
            'auto_quote': '是',
        })
    return rows
