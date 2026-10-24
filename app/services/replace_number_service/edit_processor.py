# -*- coding:utf-8 -*-
# @Time    : 2026/10/23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : edit_processor.py

"""
页内核对编辑替换号处理逻辑（两阶段）

阶段一 check_replace_number_wrapper：读取 Excel 并做 CRM 匹配检查，不写 CRM，
返回核对清单供 Excel 处理页表格展示；
阶段二 update_replace_number_wrapper：按用户确认的清单逐产品调用 CRM
updateNumber 更新替换号，输出结果 Excel。
"""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

from app.utils.logger_config import get_task_logger
from app.utils.replace_number.crm_api_client import (
    search_products_by_numberlist,
    update_product_numbers,
)
from app.utils.replace_number.constants import ORIGINAL_BRANDS
from app.utils.replace_number.excel_utils import (
    dedup_numbers,
    read_replace_number_excel,
    save_direct_result,
)
from .matcher import extract_all_products, match_products, search_by_brand_number


logger = get_task_logger('replace_number')

STATUS_PENDING = '待更新'
STATUS_SUCCESS = '更新成功'


def _search_oe_batch(company: str, oe_list: List[str]) -> Dict[str, dict]:
    """批量搜索 OE，返回每个 OE 对应的所有产品及原始 API 数据"""
    result = {}
    for oe in oe_list:
        if not oe:
            result[oe] = {'all': [], 'api_data': None}
            continue
        api_data = search_products_by_numberlist(company, oe)
        if api_data:
            result[oe] = {
                'all': extract_all_products(api_data),
                'api_data': api_data
            }
        else:
            result[oe] = {'all': [], 'api_data': None}
    return result


def search_all_products_by_oe(company: str, oe_list: List[str]) -> Dict[str, dict]:
    """
    对每个 OE 调用 CRM 列表接口，返回所有产品及原始 API 数据

    Args:
        company: 公司代码
        oe_list: OE 列表

    Returns:
        {oe: {'all': [MatchedProduct, ...], 'api_data': {...}}}
    """
    unique_oe_list = list(set(oe_list))
    mid = len(unique_oe_list) // 2
    batches = [unique_oe_list[:mid], unique_oe_list[mid:]]

    final_result = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_search_oe_batch, company, batch) for batch in batches]
        for future in futures:
            final_result.update(future.result())

    return final_result


def _missing_item(row_index: int, oe: str, brand: str, brand_number: str, status: str) -> dict:
    """构建一行无法核对编辑的数据（缺字段/未匹配/品牌号异常）"""
    return {
        'row_index': row_index,
        'oe': oe,
        'brand': brand,
        'brand_number': brand_number,
        'original_numbers': '',
        'other_numbers': '',
        'original_brands': [],
        'is_upload': 0,
        'status': status,
        'products': []
    }


def _build_edit_item(row_index: int, oe: str, brand: str, brand_number: str,
                     all_products: list, matched_products: list) -> dict:
    """根据搜索到的所有产品构建一行核对数据"""
    original_numbers = []
    other_numbers = []
    original_brands = set()

    for p in all_products:
        if p.brand_name in ORIGINAL_BRANDS:
            original_numbers.extend(p.display_numbers)
            original_brands.add(p.brand_name)
        else:
            other_numbers.extend(p.display_numbers)

    original_numbers = dedup_numbers(original_numbers)
    other_numbers = dedup_numbers([n for n in other_numbers if n not in original_numbers])

    product_details = [{
        'product_id': p.product_id,
        'number': p.number,
        'brand_name': p.brand_name,
        'display_numbers': p.display_numbers
    } for p in matched_products]

    return {
        'row_index': row_index,
        'oe': oe,
        'brand': brand,
        'brand_number': brand_number,
        'original_numbers': ','.join(original_numbers),
        'other_numbers': ','.join(other_numbers),
        'original_brands': list(original_brands),
        'is_upload': 1,
        'status': STATUS_PENDING,
        'products': product_details
    }


def _check_oe_rows(company: str, pairs: List[tuple], items: List[dict], progress_callback=None) -> None:
    """OE+品牌齐全的行：批量查 CRM 后按品牌规则匹配"""
    if not pairs:
        return
    matched_map = search_all_products_by_oe(company, [oe for _, oe, _, _ in pairs])

    total = len(pairs)
    for idx, (row_index, oe, brand, brand_number) in enumerate(pairs, 1):
        oe_result = matched_map.get(oe, {'all': [], 'api_data': None})
        all_products = oe_result.get('all', [])
        api_data = oe_result.get('api_data')
        if all_products:
            matched_products = match_products(api_data, oe, brand) if api_data else []
            items.append(_build_edit_item(row_index, oe, brand, brand_number, all_products, matched_products))
        else:
            items.append(_missing_item(row_index, oe, brand, brand_number, '未匹配到产品'))
        if progress_callback:
            progress_callback(idx, total, f"匹配检查 {idx}/{total}")


def _check_brand_number_rows(company: str, rows: List[tuple], items: List[dict]) -> None:
    """仅品牌号的行：唯一结果才采用"""
    for row_index, oe, brand, brand_number in rows:
        product, _brand_codes, status = search_by_brand_number(company, brand_number)
        if status:
            items.append(_missing_item(row_index, oe, brand, brand_number, status))
        else:
            display_oe = oe or product.number
            display_brand = brand or product.brand_name
            items.append(_build_edit_item(row_index, display_oe, display_brand, brand_number, [product], [product]))


def check_replace_number_wrapper(file_path: str, company: str = 'fsbbr', progress_callback=None) -> dict:
    """
    阶段一：匹配检查（不写 CRM），返回核对清单

    Args:
        file_path: 上传的 Excel 临时文件路径
        company: 公司代码
        progress_callback: 进度回调（由异步任务框架注入）

    Returns:
        异步任务结果结构，result_data.items 为核对清单
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    _df, rows = read_replace_number_excel(file_path)
    logger.info(f"替换号匹配检查开始: file={file_path}, rows={len(rows)}, company={company}")

    oe_pairs = []
    brand_number_rows = []
    items = []
    for row in rows:
        row_index = int(row['row_index'])
        oe = str(row.get('oe', '') or '').strip()
        brand = str(row.get('brand', '') or '').strip()
        brand_number = str(row.get('brand_number', '') or '').strip()
        if oe and brand:
            oe_pairs.append((row_index, oe, brand, brand_number))
        elif brand_number:
            brand_number_rows.append((row_index, oe, brand, brand_number))
        else:
            items.append(_missing_item(row_index, oe, brand, brand_number, '缺少字段'))

    _check_oe_rows(company, oe_pairs, items, progress_callback)
    _check_brand_number_rows(company, brand_number_rows, items)

    matched_count = sum(1 for it in items if it['status'] == STATUS_PENDING)
    logger.info(f"替换号匹配检查完成: total={len(items)}, pending={matched_count}")
    return {
        'result_file': None,
        'result_data': {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'items': items,
            'matched_count': matched_count,
            'unmatched_count': len(items) - matched_count
        }
    }


def _update_submitted_rows(company: str, check_items: List[dict], submitted_items: List[dict],
                           progress_callback=None) -> Dict[int, dict]:
    """逐行执行更新，返回 {row_index: {'status', 'updated_numbers', 'product_desc'}}"""
    product_info = {}
    for it in check_items:
        for p in it.get('products', []):
            product_info[str(p.get('product_id', ''))] = (p.get('number', ''), p.get('brand_name', ''))

    results = {}
    total = len(submitted_items)
    for idx, item in enumerate(submitted_items, 1):
        row_index = int(item['row_index'])
        ok_all = True
        updated_numbers = []
        product_desc = []
        fail_msg = ''

        for product in item.get('products', []):
            product_id = str(product.get('product_id', '') or '')
            numbers = [str(n).strip() for n in product.get('numbers', []) if str(n).strip()]
            number, brand_name = product_info.get(product_id, ('', ''))
            if not product_id or not numbers:
                ok_all = False
                fail_msg = '更新失败: 缺少产品ID或替换号'
                break
            response = update_product_numbers(company, product_id, numbers)
            if response.get('status') == 200 or response.get('msg') == '操作成功':
                updated_numbers.extend(numbers)
                product_desc.append(f"{number}/{brand_name}".strip('/'))
            else:
                ok_all = False
                fail_msg = f"更新失败: {response.get('msg', '未知错误')}"
                break

        if ok_all:
            results[row_index] = {'status': STATUS_SUCCESS, 'updated_numbers': dedup_numbers(updated_numbers),
                                  'product_desc': product_desc}
        else:
            results[row_index] = {'status': fail_msg or '更新失败', 'updated_numbers': [],
                                  'product_desc': product_desc}
        if progress_callback:
            progress_callback(idx, total, f"更新替换号 {idx}/{total}")

    return results


def update_replace_number_wrapper(file_path: str, check_items: List[dict], submitted_items: List[dict],
                                  company: str = 'fsbbr', progress_callback=None) -> dict:
    """
    阶段二：按核对清单逐产品更新 CRM，输出结果 Excel

    Args:
        file_path: 阶段一上传的 Excel 临时文件路径（结果文件由它派生）
        check_items: 阶段一核对清单（用于补齐未提交行状态与产品信息）
        submitted_items: 用户确认提交的行，[{row_index, products: [{product_id, numbers}]}]
        company: 公司代码
        progress_callback: 进度回调（由异步任务框架注入）

    Returns:
        异步任务结果结构，含统计与结果文件路径
    """
    logger.info(f"替换号更新开始: rows={len(submitted_items)}, company={company}")
    results = _update_submitted_rows(company, check_items, submitted_items, progress_callback)

    df, raw_rows = read_replace_number_excel(file_path)
    check_status_map = {int(it.get('row_index')): it.get('status', '') for it in check_items}
    success_count = 0
    fail_count = 0
    for raw in raw_rows:
        raw['row_index'] = int(raw['row_index'])
        row_result = results.get(raw['row_index'])
        if row_result:
            raw['status'] = row_result['status']
            raw['updated_numbers'] = row_result['updated_numbers']
            raw['product_desc'] = row_result['product_desc']
            if row_result['status'] == STATUS_SUCCESS:
                success_count += 1
            else:
                fail_count += 1
        else:
            # 未提交的行沿用检查阶段结论
            raw['status'] = check_status_map.get(raw['row_index'], '')

    result_path = save_direct_result(file_path, df, raw_rows)
    logger.info(f"替换号更新完成: success={success_count}, fail={fail_count}, result={result_path}")
    return {
        'result_file': result_path,
        'result_data': {
            'success_count': success_count,
            'fail_count': fail_count
        }
    }
