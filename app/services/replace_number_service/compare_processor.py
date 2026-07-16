"""
对比添加替换号处理逻辑
"""

from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Dict

from app.utils.replace_number.crm_api_client import search_products_by_numberlist
from app.utils.replace_number.constants import ORIGINAL_BRANDS
from app.utils.replace_number.excel_utils import dedup_numbers
from app.utils.logger_config import get_task_logger
from .matcher import match_products


logger = get_task_logger('replace_number')


def _search_batch(company: str, batch: List[Tuple[str, str]]) -> Dict:
    """批量搜索，线程内串行"""
    result = {}
    for oe, brand in batch:
        if not oe or not brand:
            result[(oe, brand)] = []
            continue

        api_data = search_products_by_numberlist(company, oe)
        if api_data:
            result[(oe, brand)] = match_products(api_data, oe, brand)
        else:
            result[(oe, brand)] = []

    return result


def search_oe_brand_products(company: str, oe_brand_list: List[Tuple[str, str]]) -> Dict:
    """
    批量搜索 OE+品牌 对应的产品

    Args:
        company: 公司代码
        oe_brand_list: [(oe, brand), ...]

    Returns:
        {(oe, brand): [MatchedProduct, ...]}
    """
    mid = len(oe_brand_list) // 2
    batches = [oe_brand_list[:mid], oe_brand_list[mid:]]

    final_result = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_search_batch, company, batch) for batch in batches]
        for future in futures:
            final_result.update(future.result())

    return final_result


def build_replace_number_edit_list(company: str, oe_brand_list: List[dict], page: int = 1, limit: int = 10):
    """
    构建替换号编辑页面列表数据

    Args:
        company: 公司代码
        oe_brand_list: [{'oe': ..., 'brand': ...}, ...]
        page: 页码
        limit: 每页条数

    Returns:
        (data_list, total)
    """
    logger.info(f"构建替换号编辑列表: company={company}, count={len(oe_brand_list)}, page={page}, limit={limit}")

    valid_pairs = []
    missing_rows = []

    for item in oe_brand_list:
        oe = str(item.get('oe', '')).strip()
        brand = str(item.get('brand', '')).strip()
        if oe and brand:
            valid_pairs.append((oe, brand))
        else:
            missing_rows.append({
                'oe': oe,
                'brand': brand,
                'original_numbers': '',
                'other_numbers': '',
                'is_upload': 0,
                'will_update_products': [],
                'status': '缺少字段'
            })

    matched_map = search_oe_brand_products(company, valid_pairs)

    data_list = []
    for oe, brand in valid_pairs:
        products = matched_map.get((oe, brand), [])

        original_numbers = []
        other_numbers = []
        will_update_products = []
        product_details = []

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
            else:
                other_numbers.extend(p.display_numbers)

        data_list.append({
            'oe': oe,
            'brand': brand,
            'original_numbers': ','.join(dedup_numbers(original_numbers)),
            'other_numbers': ','.join(dedup_numbers(other_numbers)),
            'is_upload': 1,
            'will_update_products': will_update_products,
            'status': '待更新',
            'products': product_details
        })

    data_list.extend(missing_rows)

    total = len(data_list)
    start = (page - 1) * limit
    end = start + limit

    logger.info(f"替换号编辑列表构建完成: total={total}")
    return data_list[start:end], total
