# -*- coding:utf-8 -*-
# @Time    : 2026/05/27
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : excel_import_service.py
# @Software: trae-cn

"""
奔驰配件库Excel导入服务
负责流式读取Excel/CSV文件，验证数据，批量保存到数据库
"""

import os
import csv
from typing import List, Dict, Any, Tuple, Optional
from io import BytesIO

# 列名映射字典
COLUMN_MAPPING = {
    '配件编号': 'part_number',
    '英文描述': 'descriptions',
    '中文描述': 'description_cn',
    '品牌': 'brand',
    '分类': 'category',
    '营销代码': 'marketing_code',
    '营销代码描述': 'marketing_code_description',
    '经销商折扣组': 'dealer_discount_group',
    '经销商固定利润': 'dealer_fixed_nominal_margin',
    '批发价格': 'wholesale_price',
    '建议零售价': 'msrp',
    '巴博瑞采购价': 'purchase_price',
    '数量单位': 'quantity_unit',
    '销售包装规格': 'sales_pack_size',
    '重量': 'weight',
    '长度': 'length',
    '宽度': 'width',
    '高度': 'height',
    '体积': 'volume',
    '生效日期': 'effective_date',
    'CCC标识': 'ccc_mark',
    '危险货物代码': 'hazmat_code',
    '原产地': 'origin_country',
    '存储期限': 'shelf_life',
    '防盗标识/危险品': 'is_hazmat',
    '车型中文名': 'l_model_zh'
}

# 数值字段列表
NUMERIC_FIELDS = [
    'dealer_fixed_nominal_margin', 'wholesale_price', 'msrp',
    'purchase_price', 'weight', 'volume'
]

# 整数字段
INTEGER_FIELDS = ['weight']

# Decimal字段
DECIMAL_FIELDS = ['volume', 'purchase_price']

# 批量大小
BATCH_SIZE = 500


def try_import_openpyxl():
    """尝试导入openpyxl，失败返回None"""
    try:
        from openpyxl import load_workbook
        return load_workbook
    except ImportError:
        return None


def read_excel_header(file_obj) -> List[str]:
    """流式读取Excel文件表头"""
    load_workbook = try_import_openpyxl()
    if not load_workbook:
        raise ImportError("需要安装openpyxl库: pip install openpyxl")
    
    file_obj.seek(0)
    wb = load_workbook(file_obj, read_only=True, data_only=True)
    ws = wb.active
    
    # 读取第一行作为表头
    header = []
    for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True), []):  # pyright: ignore[reportOptionalMemberAccess]
        header.append(str(cell).strip() if cell is not None else '')
    
    wb.close()
    file_obj.seek(0)
    return header


def read_csv_header(file_obj, encoding='utf-8') -> List[str]:
    """流式读取CSV文件表头"""
    file_obj.seek(0)
    reader = csv.reader(file_obj)
    header = next(reader, [])
    header = [str(cell).strip() for cell in header]
    file_obj.seek(0)
    return header


def validate_columns(header: List[str]) -> Tuple[bool, str]:
    """验证列名是否符合要求"""
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
    """验证单行数据"""
    result = {}
    
    # 获取配件编号
    part_number_idx = col_index_map.get('配件编号')
    if part_number_idx is None or part_number_idx >= len(row):
        raise ValueError(f'第 {row_num} 行：配件编号不能为空')
    
    part_number = row[part_number_idx]
    if part_number is None or (isinstance(part_number, str) and not part_number.strip()):
        raise ValueError(f'第 {row_num} 行：配件编号不能为空')
    
    part_number = str(part_number).replace(" ", "")
    if len(part_number) > 510:
        raise ValueError(f'第 {row_num} 行：配件编号长度不能超过510')
    
    result['part_number'] = part_number
    
    # 处理其他字段
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
        
        # 数值字段处理
        if eng_name in NUMERIC_FIELDS:
            try:
                if eng_name in INTEGER_FIELDS:
                    result[eng_name] = int(value)
                else:
                    result[eng_name] = float(value)
            except (ValueError, TypeError):
                raise ValueError(f'第 {row_num} 行：{chn_name}格式错误，应为数值')
        # 字符串字段处理
        else:
            str_value = str(value).strip()
            # 长度限制（根据数据库字段）
            if eng_name in ['part_number', 'descriptions', 'description_cn', 'marketing_code', 
                           'dealer_discount_group', 'marketing_code_description', 'quantity_unit',
                           'sales_pack_size', 'length', 'width', 'height', 'effective_date']:
                if len(str_value) > 510:
                    str_value = str_value[:510]
            elif eng_name in ['brand', 'category', 'origin_country', 'shelf_life']:
                if len(str_value) > 100:
                    str_value = str_value[:100]
            elif eng_name in ['ccc_mark', 'hazmat_code']:
                if len(str_value) > 50:
                    str_value = str_value[:50]
            elif eng_name in ['is_hazmat']:
                if len(str_value) > 10:
                    str_value = str_value[:10]
            
            result[eng_name] = str_value
    
    # 设置数据来源
    result['data_source'] = 'excel_import'
    
    return result


def get_part_number_from_row(row: List[Any], col_index_map: Dict[str, int]) -> Optional[str]:
    """从行中获取配件编号"""
    part_number_idx = col_index_map.get('配件编号')
    if part_number_idx is None or part_number_idx >= len(row):
        return None
    
    part_number = row[part_number_idx]
    if part_number is None:
        return None
    
    return str(part_number).replace(" ", "")


def iter_excel_rows(file_obj):
    """迭代Excel文件行数据"""
    load_workbook = try_import_openpyxl()
    if not load_workbook:
        raise ImportError("需要安装openpyxl库: pip install openpyxl")
    
    file_obj.seek(0)
    wb = load_workbook(file_obj, read_only=True, data_only=True)
    ws = wb.active
    
    # 跳过表头
    rows_iter = ws.iter_rows(min_row=2, values_only=True)  # pyright: ignore[reportOptionalMemberAccess]
    
    for row in rows_iter:
        yield row
    
    wb.close()


def iter_csv_rows(file_obj, encoding='utf-8'):
    """迭代CSV文件行数据"""
    file_obj.seek(0)
    reader = csv.reader(file_obj)
    # 跳过表头
    next(reader, None)
    
    for row in reader:
        yield row


def process_file_stream(file_obj, filename, dao) -> Dict[str, Any]:
    """
    流式处理文件
    
    :param file_obj: 文件对象
    :param filename: 文件名
    :param dao: CarPartsLibraryBenzDao实例
    :return: 统计信息
    """
    # 初始化统计
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'errors': [],
        'success_part_numbers': []  # 新增：成功的配件编号列表
    }
    
    batch_data = []
    
    # 根据文件扩展名选择处理方式
    ext = os.path.splitext(filename)[1].lower()
    
    # 1. 读取表头
    if ext in ['.xlsx', '.xls']:
        header = read_excel_header(file_obj)
    elif ext == '.csv':
        header = read_csv_header(file_obj)
    else:
        raise ValueError(f'不支持的文件格式：{ext}')
    
    # 2. 验证列名
    valid, msg = validate_columns(header)
    if not valid:
        raise ValueError(msg)
    
    # 3. 准备列映射
    col_index_map = build_column_index_map(header)
    
    # 4. 选择行迭代器
    if ext in ['.xlsx', '.xls']:
        row_iterator = iter_excel_rows(file_obj)
    else:  # .csv
        row_iterator = iter_csv_rows(file_obj)
    
    # 5. 逐行处理
    for row_num, row in enumerate(row_iterator, start=2):
        stats['total'] += 1
        
        try:
            # 验证行数据
            validated_data = validate_row(row, col_index_map, row_num)  # pyright: ignore[reportArgumentType]
            
            # 收集成功的配件编号
            stats['success_part_numbers'].append(validated_data['part_number'])
            
            # 加入批次
            batch_data.append(validated_data)
            
            # 批次满则提交
            if len(batch_data) >= BATCH_SIZE:
                save_batch(batch_data, dao)
                stats['success'] += len(batch_data)
                batch_data = []  # 清空批次，释放内存
                
        except Exception as e:
            stats['failed'] += 1
            stats['errors'].append({
                'row': row_num,
                'part_number': get_part_number_from_row(row, col_index_map),  # pyright: ignore[reportArgumentType]
                'error': str(e)
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
    :param dao: CarPartsLibraryBenzDao实例
    """
    from app.utils.orm.session import orm_session
    
    with orm_session() as session:
        dao.batch_upsert(session, data_list)
        session.commit()


def generate_template() -> BytesIO:
    """
    生成Excel模板文件
    
    :return: BytesIO对象，包含Excel模板
    """
    load_workbook = try_import_openpyxl()
    if not load_workbook:
        raise ImportError("需要安装openpyxl库: pip install openpyxl")
    
    from openpyxl import Workbook
    
    wb = Workbook()
    ws = wb.active
    ws.title = '配件数据'  # pyright: ignore[reportOptionalMemberAccess]
    
    # 写入表头
    headers = list(COLUMN_MAPPING.keys())
    ws.append(headers)  # pyright: ignore[reportOptionalMemberAccess]
    
    # 调整列宽
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[chr(64 + col)].width = 15  # pyright: ignore[reportOptionalMemberAccess]
    
    # 保存到BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    return output

