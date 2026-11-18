#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价 · 匹配适配层

匹配逻辑（CRM现货/奔驰/宝马的选品、价格计算、priceCheck）从旧模块
app/utils/qpl_auto_bill/auto_submit_part_quote.py 平移复用（import 调用，零改动），
本层只做"旧函数返回结构 → 新流水线统一结构"的转换。

宝马(C类)订单的本地 OE 库补齐前置逻辑见 bmw_oe.py，由 pipeline 在匹配前调用。
"""

from app.utils.qpl_auto_bill.auto_submit_part_quote import (
    handle_category_a,
    handle_category_b,
    handle_category_c,
)

CAR_BENZ = '奔驰'
CAR_BMW = '宝马'


def match_order_by_brand(detail_data, company, skip_item_ids=None):
    """
    按车辆品牌分流到对应匹配链（复用旧处理器，返回统一结构）。

    Args:
        detail_data: 全量详情
        skip_item_ids: 本地终态/冷却中的 item 集合（传入旧处理器做过滤）

    Returns:
        dict | None: 统一匹配结果
            {
                'extra_quote_items': {item_id: [quote_item, ...]},
                'failed_items': {item_id: reason},
                'failed_brand_names': {item_id: brand_name},
                'quote_item_ids': set,      # 本次产出报价项的明细
                'category': 'A'/'B'/'C',
            }
            车辆品牌无法识别时返回 None
    """
    car_brand = (detail_data.get('carBrand') or '').strip()
    processed = skip_item_ids or set()

    if car_brand == CAR_BENZ:
        raw = handle_category_b(detail_data, company, processed_item_ids=processed)
    elif car_brand == CAR_BMW:
        raw = handle_category_c(detail_data, company, processed_item_ids=processed)
    else:
        raw = handle_category_a(detail_data, company, processed_item_ids=processed)

    return {
        'extra_quote_items': raw.get('extra_quote_items') or {},
        'failed_items': _normalize_failed_items(raw.get('failed_items')),
        'failed_brand_names': raw.get('failed_brand_names') or {},
        'quote_item_ids': (
            set(raw.get('crm_quote_item_ids') or set()) |
            set(raw.get('bc_quote_item_ids') or set())
        ),
        'category': raw.get('category'),
    }


def _normalize_failed_items(failed_items):
    """
    归一化失败原因为纯字符串。

    旧处理器差异：A 类 crm_failed_items 的值是 (reason, has_original) 二元组
    （旧消费方 _merge_failed_items 解包），B/C 类经 _merge_failed_items 后是纯字符串。
    新流水线统一按字符串消费。
    """
    normalized = {}
    for item_id, reason in (failed_items or {}).items():
        normalized[item_id] = reason[0] if isinstance(reason, tuple) else reason
    return normalized


def extract_quote_summary(quote_item):
    """
    从报价项提取落库冗余字段（qpl_order_item 的结果列）。

    Returns:
        dict: {matched_brand, item_sell_price, delivery_aging, parts_no, item_quality}
    """
    return {
        'matched_brand': quote_item.get('brandName'),
        'item_sell_price': quote_item.get('itemSellPrice'),
        'delivery_aging': quote_item.get('deliveryAging'),
        'parts_no': quote_item.get('partsNo'),
        'item_quality': quote_item.get('itemQuality'),
    }
