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
from .crm_processor import process_items, _query_product_list, _find_existed_children, _get_brand_info
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


def check_excel_items_wrapper(file_path: str, mode: str, company: str = 'fsbbr', progress_callback: Optional[Callable] = None):
    """
    匹配检查包装器（阶段一，不写CRM）

    读取 Excel 构建条目，按 OE 去重查询 CRM 判定是否已存在；
    同时按别名池规则匹配 CRM 系统品牌（与新建流程 _get_brand_id 同规则）；
    已存在的条目按 CRM 命中明细全展开（brand_code/product_id 直接取自 list 接口）。

    Returns:
        {
            'result_file': None（检查阶段不生成结果文件）,
            'result_data': {
                'file_path': 临时文件路径（保留给确认阶段重读）,
                'file_name': 原文件名,
                'mode': 处理模式,
                'items': [{sheet_name, oe, brand, brand_code, crm_brand_code, status}],
                'matched_count': 已存在条数,
                'unmatched_count': 待新建条数
            }
        }
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    session = create_crm_session(company)

    try:
        all_sheets = read_excel_file(file_path)
        valid_sheets = filter_sheets_by_mode(all_sheets, mode)

        if not valid_sheets:
            raise ValueError("没有找到符合要求的工作表")

        items = []
        for sheet_name, sheet_info in valid_sheets.items():
            for item in build_items(sheet_info['df'], sheet_info['columns'], mode):
                items.append({
                    'sheet_name': sheet_name,
                    'oe': item['oe_number'],
                    'brand': item['brand'],
                    'brand_code': item.get('brand_code', ''),
                    'crm_brand_code': '',
                    'status': 'to_create'
                })

        total = len(items)
        oe_children_cache = {}
        brand_info_cache = {}
        matched_count = 0
        output_items = []

        for idx, entry in enumerate(items, 1):
            # 品牌ID匹配（顺便，同品牌只查一次；与新建流程 _get_brand_id 同规则）
            brand_key = entry['brand']
            if brand_key not in brand_info_cache:
                brand_info_cache[brand_key] = _get_brand_info(session, brand_key)
            brand_info = brand_info_cache[brand_key]
            if brand_info:
                entry['system_brand'] = brand_info[1]
                entry['brand_matched'] = True
            else:
                entry['system_brand'] = ''
                entry['brand_matched'] = False

            oe = entry['oe']
            if oe not in oe_children_cache:
                oe_children_cache[oe] = _query_product_list(session, oe)
            children = oe_children_cache[oe]

            existed_children = _find_existed_children(oe, entry['brand'], children) if children is not None else []
            if existed_children:
                # 已存在：按文件行计 1 条；明细按 CRM 命中全展开（brand_code/product_id 直接取自 list 接口）
                matched_count += 1
                for child in existed_children:
                    output_items.append({
                        'sheet_name': entry['sheet_name'],
                        'oe': entry['oe'],
                        'brand': entry['brand'],
                        'brand_code': entry['brand_code'],
                        'system_brand': entry['system_brand'],
                        'brand_matched': entry['brand_matched'],
                        'crm_brand_code': child[3] or '',
                        'product_id': child[2],
                        'status': 'existed'
                    })
            else:
                entry['product_id'] = ''
                output_items.append(entry)

            if progress_callback:
                progress_callback(idx, total, f"匹配检查 {idx}/{total}")

        return {
            'result_file': None,
            'result_data': {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'mode': mode,
                'items': output_items,
                'matched_count': matched_count,
                'unmatched_count': total - matched_count
            }
        }
    finally:
        session.close()


def create_confirmed_items_wrapper(file_path: str, confirmed_items: list, mode: str, company: str = 'fsbbr', progress_callback: Optional[Callable] = None):
    """
    确认新建包装器（阶段二）

    仅处理用户确认的待新建条目，重读原文件以保持结果文件格式不变
    （原Excel数据 + 新建结果列），完成后清理临时文件。

    Args:
        confirmed_items: [{sheet_name, oe, brand, brand_code}]

    Returns:
        {'result_file': 结果文件路径, 'result_data': 统计与成功清单}
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    session = create_crm_session(company)
    product_df, alias_df = _load_common_data()

    try:
        all_sheets = read_excel_file(file_path)
        valid_sheets = filter_sheets_by_mode(all_sheets, mode)

        grouped = {}
        for it in confirmed_items:
            sheet_name = str(it.get('sheet_name', '') or '')
            grouped.setdefault(sheet_name, []).append(it)

        all_results = {}
        all_items = []
        processed = 0
        total = len(confirmed_items)

        for sheet_name, sheet_confirm_items in grouped.items():
            sheet_info = valid_sheets.get(sheet_name)
            if not sheet_info:
                continue

            items = [{
                'oe_number': str(it.get('oe', '') or '').strip(),
                'brand': str(it.get('brand', '') or '').strip(),
                'brand_code': str(it.get('brand_code', '') or '').strip(),
                'mode': mode
            } for it in sheet_confirm_items]
            items = [it for it in items if it['oe_number'] and it['brand']]
            if not items:
                continue

            results = process_items(
                items, product_df, alias_df, session,
                progress_callback=progress_callback,
                progress_offset=processed,
                total_items=total
            )

            columns = sheet_info['columns']
            all_results[sheet_name] = {
                'df': sheet_info['df'],
                'results': results,
                'oe_col': columns[0],
                'brand_col': columns[1]
            }
            all_items.extend(items)
            processed += len(items)

        if not all_results:
            raise ValueError("确认的条目没有匹配到有效的工作表数据，请重新上传检查")

        result_path = save_multi_sheet_results(all_results, file_path)

        success_count = 0
        fail_count = 0
        processed_oe_set = set()
        oe_brand_list = []
        seen = set()
        for item in all_items:
            key = (item['oe_number'], item['brand'])
            result = None
            for sheet_data in all_results.values():
                if key in sheet_data['results']:
                    result = sheet_data['results'][key]
                    break
            if result is None:
                continue
            processed_oe_set.add(item['oe_number'])
            if result.is_success():
                success_count += 1
                if key not in seen:
                    oe_brand_list.append({'oe': item['oe_number'], 'brand': item['brand']})
                    seen.add(key)
            else:
                fail_count += 1

        return {
            'result_file': result_path,
            'result_data': {
                'oe_list': sorted(processed_oe_set),
                'oe_brand_list': oe_brand_list,
                'total': len(processed_oe_set),
                'success_count': success_count,
                'fail_count': fail_count
            }
        }
    finally:
        session.close()
        # 处理完成后清理上传的临时文件
        try:
            os.remove(file_path)
        except Exception:
            pass


