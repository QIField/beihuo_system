# -*- coding:utf-8 -*-
# @Time    : 2026/06/17
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : excel_import_bmw_service.py
# @Software : trae-cn

"""
华晨宝马配件库 Excel 导入服务
负责流式读取 Excel/CSV 文件，验证数据，批量保存到 car_parts_library_bmw 表
"""

import os
import csv
from typing import List, Dict, Any, Tuple
from io import BytesIO

# ============================================================
# 列名映射：Excel 中文列名 → 数据库英文字段名
# 按 car_parts_library_bmw 表字段定义
# ============================================================
COLUMN_MAPPING = {
    '配件编号': 'part_number',
    '零件名称': 'part_name',
    '销售单位': 'sales_unit',
    '物料组': 'material_group',
    '毛重': 'gross_weight',
    '净重': 'net_weight',
    '体积': 'volume',
    '零售价': 'retail_price',
    '折扣-Stock': 'discount_stock',
    '折扣-Rush': 'discount_rush',
    '经销商净值-Stock': 'dealer_net_stock',
    '经销商净值-Rush': 'dealer_net_rush',
    '可用库存': 'available_stock',
    '采集时间': 'data_collect_time',
}

# 批量大小
BATCH_SIZE = 500


def try_import_openpyxl():
    """尝试导入 openpyxl，失败返回 None"""
    try:
        from openpyxl import load_workbook
        return load_workbook
    except ImportError:
        return None


def read_excel_header(file_obj) -> List[str]:
    """流式读取 Excel 文件表头"""
    load_workbook = try_import_openpyxl()
    if not load_workbook:
        raise ImportError("需要安装 openpyxl 库: pip install openpyxl")

    file_obj.seek(0)
    wb = load_workbook(file_obj, read_only=True, data_only=True)
    ws = wb.active

    header = []
    for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True), []):
        header.append(str(cell).strip() if cell is not None else '')

    wb.close()
    file_obj.seek(0)
    return header


def read_csv_header(file_obj, encoding='utf-8') -> List[str]:
    """流式读取 CSV 文件表头"""
    file_obj.seek(0)
    reader = csv.reader(file_obj)
    header = next(reader, [])
    header = [str(cell).strip() for cell in header]
    file_obj.seek(0)
    return header


def validate_columns(header: List[str]) -> Tuple[bool, str]:
    """验证列名是否符合要求（至少包含配件编号）"""
    if '配件编号' not in header:
        return False, '缺少必要列：配件编号'
    return True, ''


def build_column_index_map(header: List[str]) -> Dict[str, int]:
    """构建列名到索引的映射"""
    col_index_map = {}
    for idx, col_name in enumerate(header):
        col_index_map[col_name] = idx
    return col_index_map


def validate_row(row: List[Any], col_index_map: Dict[str, int], row_num: int) -> Dict[str, Any]:
    """验证单行数据，将 Excel 行转换为数据库字段字典"""
    result = {}

    # 获取配件编号
    part_number_idx = col_index_map.get('配件编号')
    if part_number_idx is None or part_number_idx >= len(row):
        raise ValueError(f'第 {row_num} 行：配件编号不能为空')

    part_number = row[part_number_idx]
    if part_number is None or (isinstance(part_number, str) and not part_number.strip()):
        raise ValueError(f'第 {row_num} 行：配件编号不能为空')

    part_number = str(part_number).replace(' ', '')
    if len(part_number) > 510:
        raise ValueError(f'第 {row_num} 行：配件编号长度不能超过 510')

    result['part_number'] = part_number

    # 处理其他字段（字符串类型，直接存，超出长度截断）
    for chn_name, eng_name in COLUMN_MAPPING.items():
        if chn_name == '配件编号':
            continue

        col_idx = col_index_map.get(chn_name)
        if col_idx is None or col_idx >= len(row):
            continue

        value = row[col_idx]

        # 处理空值
        if value is None or (isinstance(value, str) and not value.strip()):
            result[eng_name] = None
            continue

        # BMW 字段全部为 varchar，统一做字符串转换与长度截断
        str_value = str(value).strip()
        if len(str_value) > 510:
            str_value = str_value[:510]
        elif len(str_value) > 100 and eng_name in ['material_group']:
            str_value = str_value[:100]
        elif eng_name in ['sales_unit', 'gross_weight', 'net_weight', 'volume',
                          'retail_price', 'discount_stock', 'discount_rush',
                          'dealer_net_stock', 'dealer_net_rush', 'available_stock',
                          'data_collect_time']:
            if len(str_value) > 50:
                str_value = str_value[:50]

        result[eng_name] = str_value

    return result


def get_part_number_from_row(row: List[Any], col_index_map: Dict[str, int]) -> str:
    """从行中获取配件编号（仅用于错误提示）"""
    part_number_idx = col_index_map.get('配件编号')
    if part_number_idx is None or part_number_idx >= len(row):
        return ''

    part_number = row[part_number_idx]
    if part_number is None:
        return ''

    return str(part_number).replace(' ', '')


def iter_excel_rows(file_obj):
    """迭代 Excel 文件行数据（跳过表头）"""
    load_workbook = try_import_openpyxl()
    if not load_workbook:
        raise ImportError("需要安装 openpyxl 库: pip install openpyxl")

    file_obj.seek(0)
    wb = load_workbook(file_obj, read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(min_row=2, values_only=True)

    for row in rows_iter:
        yield row

    wb.close()


def iter_csv_rows(file_obj, encoding='utf-8'):
    """迭代 CSV 文件行数据（跳过表头）"""
    file_obj.seek(0)
    reader = csv.reader(file_obj)
    next(reader, None)

    for row in reader:
        yield row


def process_file_stream(file_obj, filename, dao) -> Dict[str, Any]:
    """
    流式处理文件

    :param file_obj: 文件对象
    :param filename: 文件名
    :param dao: CarPartsLibraryBmwDao 实例
    :return: 统计信息
    """
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'errors': [],
        'success_part_numbers': [],
    }

    batch_data = []

    # 根据文件扩展名选择处理方式
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.xls':
        raise ValueError('不支持 .xls 格式的文件，请使用 .xlsx 格式或转换为 .csv 格式')

    # 1. 读取表头
    if ext == '.xlsx':
        header = read_excel_header(file_obj)
    elif ext == '.csv':
        header = read_csv_header(file_obj)
    else:
        raise ValueError(f'不支持的文件格式：{ext}。仅支持 .xlsx 和 .csv 格式')

    # 2. 验证列名
    valid, msg = validate_columns(header)
    if not valid:
        raise ValueError(msg)

    # 3. 准备列映射
    col_index_map = build_column_index_map(header)

    # 4. 选择行迭代器
    if ext == '.xlsx':
        row_iterator = iter_excel_rows(file_obj)
    else:
        row_iterator = iter_csv_rows(file_obj)

    # 5. 逐行处理
    for row_num, row in enumerate(row_iterator, start=2):
        stats['total'] += 1

        # 空行跳过
        if row is None or all(cell is None or (isinstance(cell, str) and not cell.strip()) for cell in row):
            continue

        try:
            validated_data = validate_row(row, col_index_map, row_num)

            stats['success_part_numbers'].append(validated_data['part_number'])

            batch_data.append(validated_data)

            # 批次满则提交
            if len(batch_data) >= BATCH_SIZE:
                save_batch(batch_data, dao)
                stats['success'] += len(batch_data)
                batch_data = []

        except Exception as e:
            stats['failed'] += 1
            stats['errors'].append({
                'row': row_num,
                'part_number': get_part_number_from_row(row, col_index_map),
                'error': str(e),
            })

    # 6. 处理剩余数据
    if batch_data:
        save_batch(batch_data, dao)
        stats['success'] += len(batch_data)

    return stats


def save_batch(data_list: List[Dict], dao):
    """
    批量保存数据（插入更新模式）

    :param data_list: 数据列表
    :param dao: CarPartsLibraryBmwDao 实例
    """
    from app.utils.orm.session import orm_session

    with orm_session() as session:
        dao.batch_upsert(session, data_list)
        session.commit()


def generate_template() -> BytesIO:
    """
    生成 Excel 模板文件

    :return: BytesIO 对象，包含 Excel 模板
    """
    load_workbook = try_import_openpyxl()
    if not load_workbook:
        raise ImportError("需要安装 openpyxl 库: pip install openpyxl")

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = '宝马配件数据'

    # 写入表头（中文列名，按 COLUMN_MAPPING 的顺序）
    headers = list(COLUMN_MAPPING.keys())
    ws.append(headers)

    # 调整列宽
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[chr(64 + col)].width = 18

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return output
