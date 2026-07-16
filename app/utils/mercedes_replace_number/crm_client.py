# -*- coding: utf-8 -*-
"""
CRM 产品搜索 + 替换号更新
"""

import time
from typing import Dict, List

from app.utils.crm_product.crm_productAdd.crm_get_oe_link import get_oe_link
from app.utils.crm_product.crm_productAdd.crm_Product_Add import add_product
from app.utils.replace_number.crm_api_client import (
    search_products_by_numberlist,
    update_product_numbers,
)
from app.utils.replace_number.excel_utils import dedup_numbers
from app.utils.logger_config import get_task_logger
from config import create_crm_session

from .config import DEFAULT_COMPANY, MAX_RETRY_TIMES, TASK_NAME
from .models import OePair, UpdateRecord


logger = get_task_logger(TASK_NAME)

# 未搜索到产品时自动创建的两个品牌（固定 ID）
DEFAULT_CREATE_BRANDS = [
    {'brand_id': '79', 'brand_name': '原厂'},
    {'brand_id': '220', 'brand_name': '原厂国内4s件'},
]


def search_products(company: str, oe_code: str) -> List[Dict]:
    """
    调用 CRM Product.Product/list 搜索产品。

    Returns:
        产品列表，每个产品包含 product_id、brand_name、number、display_numbers。
        过滤掉\"找不到产品\"等占位项。
    """
    try:
        api_data = search_products_by_numberlist(company, oe_code)
        if not api_data or api_data.get('total', 0) == 0:
            return []
        products = []
        for group in api_data.get('data', []):
            for child in group.get('child', []):
                product_id = str(child.get('product_id', '')).strip()
                if not product_id:
                    continue
                products.append({
                    'product_id': product_id,
                    'brand_name': str(child.get('brand_name', '') or '').strip(),
                    'number': str(child.get('number', '') or '').strip(),
                    'display_numbers': _extract_display_numbers(child.get('display_number')),
                })
        return products
    except Exception:
        logger.exception(f"CRM 搜索失败: {oe_code}")
        return []


def _make_failure_record(oe: str, message: str) -> UpdateRecord:
    """生成一条新建产品失败的记录。"""
    return UpdateRecord(
        oe=oe,
        brand_name='新建产品失败',
        product_id='',
        numbers_before=[],
        numbers_after=[],
        status='失败',
        message=message,
    )


def _ensure_products_exist(
    company: str,
    oe_pair: OePair
):
    """
    确保 CRM 中存在该 OE 对应的产品。
    如果搜索不到，则创建两个品牌（原厂、原厂国内4s件）的产品，
    等待 CRM 同步后再搜索并返回结果。

    创建前会先获取 OE 信息，产品名称、车型、OE 品牌任一缺失则直接失败。

    Returns:
        (products, failure_records)
    """
    products = search_products(company, oe_pair.without_a)
    if products:
        return products, []

    logger.warning(f"CRM 未搜索到产品，准备创建: {oe_pair.without_a}")

    session = create_crm_session(company)

    # 获取 OE 信息，缺失则失败
    oe_info = get_oe_link(oe_pair.without_a, session)
    if not oe_info:
        msg = f"未获取到 OE 信息: {oe_pair.without_a}"
        logger.warning(f"CRM 创建产品失败，{msg}")
        return [], [_make_failure_record(oe_pair.without_a, msg)]

    product_name = oe_info.get('product_name', '')
    vehicle_name = oe_info.get('vehicle_name', '')
    oe_brand_name = oe_info.get('brand_name', '')

    if not product_name:
        msg = f"缺少 product_name: {oe_pair.without_a}"
        logger.warning(f"CRM 创建产品失败，{msg}")
        return [], [_make_failure_record(oe_pair.without_a, msg)]
    if not vehicle_name:
        msg = f"缺少 vehicle_name: {oe_pair.without_a}"
        logger.warning(f"CRM 创建产品失败，{msg}")
        return [], [_make_failure_record(oe_pair.without_a, msg)]
    if not oe_brand_name:
        msg = f"缺少 brand_name: {oe_pair.without_a}"
        logger.warning(f"CRM 创建产品失败，{msg}")
        return [], [_make_failure_record(oe_pair.without_a, msg)]

    created_any = False
    for brand in DEFAULT_CREATE_BRANDS:
        payload = {
            'number': oe_pair.without_a,
            'brand_id': brand['brand_id'],
            'l_name_zh': product_name,
            'l_name_zh_store': product_name,
            'cass_oebrand_name': oe_brand_name,
            'l_model_zh': vehicle_name,
        }
        response = add_product(payload, session)
        logger.info(
            f"CRM 创建产品 {oe_pair.without_a} 品牌={brand['brand_name']} "
            f"响应={response}"
        )
        if response and response.get('status') in (200, 201):
            created_any = True

    if not created_any:
        msg = f"add_product 全部失败: {oe_pair.without_a}"
        logger.warning(f"CRM {msg}")
        return [], [_make_failure_record(oe_pair.without_a, msg)]

    # 创建后等待 CRM 同步，再重新搜索
    time.sleep(3)
    products = search_products(company, oe_pair.without_a)

    if not products:
        msg = f"创建产品后仍未搜索到: {oe_pair.without_a}"
        logger.warning(f"CRM {msg}")
        return [], [_make_failure_record(oe_pair.without_a, msg)]

    return products, []


def update_oe_replace_numbers(
    company: str,
    oe_pair: OePair,
    replace_numbers: List[str]
) -> List[UpdateRecord]:
    """
    用不带 A 的 OE 搜索 CRM 产品，若不存在则创建两个品牌的产品，
    然后遍历每个 product_id，将奔驰替换号与产品自身替换号合并去重后更新。
    """
    products, failure_records = _ensure_products_exist(company, oe_pair)
    if failure_records:
        return failure_records

    if not products:
        msg = f"未搜索到产品且无失败记录: {oe_pair.without_a}"
        logger.warning(f"CRM {msg}")
        return [_make_failure_record(oe_pair.without_a, msg)]

    records = []
    for product in products:
        product_id = product['product_id']
        brand_name = product['brand_name']

        existing = product['display_numbers']
        merged = merge_replace_numbers(existing, replace_numbers)

        status, message = _update_with_retry(company, product_id, merged)

        records.append(UpdateRecord(
            oe=oe_pair.without_a,
            brand_name=brand_name,
            product_id=product_id,
            numbers_before=existing,
            numbers_after=merged,
            status=status,
            message=message,
        ))

        logger.info(
            f"CRM 更新 {oe_pair.without_a} -> {product_id} "
            f"状态={status} 替换号数={len(merged)}"
        )

    return records


def merge_replace_numbers(existing: List[str], new: List[str]) -> List[str]:
    """合并两个替换号列表并去重，保持顺序。"""
    return dedup_numbers(existing + new)


def _update_with_retry(company: str, product_id: str, numbers: List[str]) -> tuple:
    """
    调用 CRM updateNumber，失败时重试一次。

    Returns:
        (status, message)
    """
    last_error = ''
    for attempt in range(MAX_RETRY_TIMES + 1):
        try:
            response = update_product_numbers(company, product_id, numbers)
            if response.get('status') == 200 or response.get('msg') == '操作成功':
                return '成功', ''
            return '失败', response.get('msg', '未知错误')
        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRY_TIMES:
                time.sleep(1)

    return '失败', f'重试后仍失败: {last_error}'


def _extract_display_numbers(display_number) -> List[str]:
    """从 CRM 返回的 display_number 数组中提取替换号。"""
    if not display_number or not isinstance(display_number, list):
        return []
    result = []
    for item in display_number:
        if isinstance(item, dict):
            num = str(item.get('number', '')).strip()
            if num and num not in result:
                result.append(num)
    return result
