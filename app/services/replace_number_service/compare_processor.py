"""
对比添加替换号处理逻辑
"""

from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Dict

from app.utils.replace_number.crm_api_client import search_products_by_numberlist
from app.utils.replace_number.constants import ORIGINAL_BRANDS
from app.utils.replace_number.excel_utils import dedup_numbers
from app.utils.logger_config import get_task_logger
from .matcher import extract_all_products, search_by_brand_number


logger = get_task_logger('replace_number')


def _search_oe_batch(company: str, oe_list: List[str]) -> Dict[str, list]:
    """批量搜索 OE，返回每个 OE 对应的所有产品"""
    result = {}
    for oe in oe_list:
        if not oe:
            result[oe] = []
            continue
        api_data = search_products_by_numberlist(company, oe)
        if api_data:
            result[oe] = extract_all_products(api_data)
        else:
            result[oe] = []
    return result


def search_all_products_by_oe(company: str, oe_list: List[str]) -> Dict[str, list]:
    """
    对每个 OE 调用 CRM 列表接口，返回所有产品（不过滤品牌）

    Args:
        company: 公司代码
        oe_list: OE 列表

    Returns:
        {oe: [MatchedProduct, ...]}
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


def _build_edit_row(oe: str, brand: str, brand_number: str, products: list):
    """根据搜索到的所有产品构建编辑页一行数据"""
    original_numbers = []
    other_numbers = []
    will_update_products = []
    product_details = []
    original_brands = set()

    for p in products:
        will_update_products.append(f"{p.number} {p.brand_name}")
        product_details.append({
            'product_id': p.product_id,
            'number': p.number,
            'brand_name': p.brand_name,
            'display_numbers': p.display_numbers
        })
        if p.brand_name in ORIGINAL_BRANDS:
            original_numbers.extend(p.display_numbers)
            original_brands.add(p.brand_name)
        else:
            other_numbers.extend(p.display_numbers)

    original_numbers = dedup_numbers(original_numbers)
    other_numbers = dedup_numbers([n for n in other_numbers if n not in original_numbers])

    return {
        'oe': oe,
        'brand': brand,
        'brand_number': brand_number,
        'original_numbers': ','.join(original_numbers),
        'other_numbers': ','.join(other_numbers),
        'original_brands': list(original_brands),
        'is_upload': 1,
        'will_update_products': will_update_products,
        'status': '待更新',
        'products': product_details
    }


def build_replace_number_edit_list(company: str, oe_brand_list: List[dict], page: int = 1, limit: int = 10):
    """
    构建替换号编辑页面列表数据

    Args:
        company: 公司代码
        oe_brand_list: [{'oe': ..., 'brand': ..., 'brand_number': ...}, ...]
        page: 页码
        limit: 每页条数

    Returns:
        (data_list, total)
    """
    logger.info(f"构建替换号编辑列表: company={company}, count={len(oe_brand_list)}, page={page}, limit={limit}")

    valid_pairs = []
    brand_number_items = []
    data_list = []

    for item in oe_brand_list:
        oe = str(item.get('oe', '')).strip()
        brand = str(item.get('brand', '')).strip()
        brand_number = str(item.get('brand_number', '')).strip()
        if oe and brand:
            valid_pairs.append((oe, brand, brand_number))
        elif brand_number:
            brand_number_items.append((oe, brand, brand_number))
        else:
            data_list.append({
                'oe': oe,
                'brand': brand,
                'brand_number': brand_number,
                'original_numbers': '',
                'other_numbers': '',
                'is_upload': 0,
                'will_update_products': [],
                'status': '缺少字段'
            })

    matched_map = search_all_products_by_oe(company, [oe for oe, _, _ in valid_pairs])

    for oe, brand, brand_number in valid_pairs:
        products = matched_map.get(oe, [])
        if products:
            data_list.append(_build_edit_row(oe, brand, brand_number, products))
        else:
            data_list.append({
                'oe': oe,
                'brand': brand,
                'brand_number': brand_number,
                'original_numbers': '',
                'other_numbers': '',
                'is_upload': 0,
                'will_update_products': [],
                'status': '未匹配到产品'
            })

    for oe, brand, brand_number in brand_number_items:
        product, _brand_codes, status = search_by_brand_number(company, brand_number)
        if status:
            data_list.append({
                'oe': oe,
                'brand': brand,
                'brand_number': brand_number,
                'original_numbers': '',
                'other_numbers': '',
                'is_upload': 0,
                'will_update_products': [],
                'status': status
            })
        else:
            display_oe = oe or product.number
            display_brand = brand or product.brand_name
            data_list.append(_build_edit_row(display_oe, display_brand, brand_number, [product]))

    total = len(data_list)
    start = (page - 1) * limit
    end = start + limit

    logger.info(f"替换号编辑列表构建完成: total={total}")
    return data_list[start:end], total
