"""
CRM 产品添加模块的 API 入口

职责：
- 供后端调用的各种处理入口
- 统一协调 Excel 读取、CRM 处理、结果保存
"""

import os
from typing import Callable, Optional

from config import create_crm_session
from .excel_data_loader import load_product_data, load_alias_data
from .excel_reader import read_excel_file, filter_sheets_by_mode, build_items
from .crm_processor import process_items
from .result_saver import save_multi_sheet_results


def _load_common_data():
    """加载产品/别名数据"""
    return load_product_data(), load_alias_data()


def _process_excel_file(file_path: str, mode: str, company: str = 'fsbbr', progress_callback: Optional[Callable] = None):
    """
    统一处理 Excel/CSV 文件

    Args:
        file_path: 文件路径
        mode: two_column 或 three_column
        company: 门店/组织代码
        progress_callback: 进度回调函数

    Returns:
        (result_path, all_results, all_items)
        result_path: 结果文件路径
        all_results: {sheet_name: {'df': DataFrame, 'results': {(oe, brand): ProcessResult}, 'oe_col': str, 'brand_col': str}}
        all_items: 所有 sheet 的 item 列表合并
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    session = create_crm_session(company)
    product_df, alias_df = _load_common_data()

    try:
        all_sheets = read_excel_file(file_path)
        valid_sheets = filter_sheets_by_mode(all_sheets, mode)

        if not valid_sheets:
            raise ValueError("没有找到符合要求的工作表")

        total_items = sum(len(sheet['df']) for sheet in valid_sheets.values())
        processed = 0
        all_results = {}
        all_items = []

        for sheet_name, sheet_info in valid_sheets.items():
            df = sheet_info['df']
            columns = sheet_info['columns']
            oe_col = columns[0]

            items = build_items(df, columns, mode)
            results = process_items(
                items, product_df, alias_df, session,
                progress_callback=progress_callback,
                progress_offset=processed,
                total_items=total_items
            )

            all_results[sheet_name] = {
                'df': df,
                'results': results,
                'oe_col': oe_col,
                'brand_col': columns[1]
            }
            all_items.extend(items)
            processed += len(items)

        result_path = save_multi_sheet_results(all_results, file_path)
        return result_path, all_results, all_items

    finally:
        session.close()


def process_excel_async_wrapper(file_path: str, mode: str, company: str = 'fsbbr', progress_callback=None):
    """
    Excel 异步处理包装器
    支持进度回调，供异步任务调用

    Args:
        file_path: Excel/CSV 文件路径
        mode: 处理模式，two_column 或 three_column
        company: 门店/组织代码，默认 fsbbr
        progress_callback: 进度回调函数

    Returns:
        {
            'result_file': 结果文件路径,
            'result_data': {
                'oe_list': [...],
                'oe_brand_list': [{'oe': ..., 'brand': ...}, ...],
                'total': int,
                'success_count': int,
                'fail_count': int
            }
        }
    """
    result_path, all_results, all_items = _process_excel_file(file_path, mode, company, progress_callback)

    processed_oe_set = set()
    success_count = 0
    fail_count = 0

    for sheet_data in all_results.values():
        for (oe, brand), result in sheet_data['results'].items():
            processed_oe_set.add(oe)
            if result.is_success():
                success_count += 1
            else:
                fail_count += 1

    oe_brand_list = []
    seen = set()
    for item in all_items:
        oe = item.get('oe_number', '')
        brand = item.get('brand', '')
        if not oe or not brand:
            continue
        key = (oe, brand)
        result = None
        for sheet_data in all_results.values():
            if key in sheet_data['results']:
                result = sheet_data['results'][key]
                break
        if result and result.is_success() and key not in seen:
            oe_brand_list.append({'oe': oe, 'brand': brand})
            seen.add(key)

    result_data = {
        'oe_list': sorted(processed_oe_set),
        'oe_brand_list': oe_brand_list,
        'total': len(processed_oe_set),
        'success_count': success_count,
        'fail_count': fail_count
    }

    # 清理上传的临时文件
    try:
        os.remove(file_path)
    except Exception:
        pass

    return {
        'result_file': result_path,
        'result_data': result_data
    }


