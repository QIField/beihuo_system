#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
报价明细提取

从询价单详情数据中提取报价明细（含报价项、失败项、状态异常项），
供落库模块与编排模块使用。纯数据加工，不做数据库写入。
"""

from datetime import datetime

from app.utils.qpl_auto_bill.qpl_config import qpl_log
from app.utils.qpl_auto_bill.auto_submit_part_quote import FAIL_PRICE_CHECK_FAILED


# ============================================================================
# 提取处理器（按有无报价分发）
# ============================================================================

_QUOTE_EXTRACT_HANDLERS = {}


def _register_extract_handler(has_quotes):
    """注册报价提取处理器"""
    def decorator(func):
        _QUOTE_EXTRACT_HANDLERS[has_quotes] = func
        return func
    return decorator


@_register_extract_handler(True)
def _extract_with_quotes(details, supplier_demand_id, enquiry_item_id, item_oe,
                         item_name, item_description, quote_status, quote_list, **_):
    """有报价的项目：展开每个报价项"""
    for quote_info in quote_list:
        details.append({
            'supplier_demand_id': supplier_demand_id,
            'enquiry_item_id': enquiry_item_id,
            'item_oe': item_oe,
            'item_name': item_name,
            'item_description': item_description,
            'brand_id': quote_info.get('brandId'),
            'brand_name': quote_info.get('brandName'),
            'item_sell_price': quote_info.get('itemSellPrice'),
            'delivery_aging': quote_info.get('deliveryAging', 1),
            'item_quality': quote_info.get('itemQuality'),
            'parts_no': quote_info.get('partsNo'),
            'quote_status': quote_status,
            '_has_quote': True,
            '_failure_reason': None
        })


@_register_extract_handler(False)
def _extract_without_quotes(details, supplier_demand_id, enquiry_item_id, item_oe,
                            item_name, item_description, quote_status, failed_items,
                            failed_brand_names=None, failed_item_prices=None, enquiry_no=None,
                            failure_categories=None, retry_counts=None, **_):
    """无报价的项目：记录失败原因

    brand_name 展示规则：
        - 若 failed_brand_names 中有实际尝试过的品牌名 → 使用该品牌名
        - 否则（仅 no_original_product / 程序未处理 等场景）→ '无报价'

    价格检测失败时，把当时的尝试价格写入 item_sell_price，方便排查。
    """
    reason = failed_items.get(enquiry_item_id, '未处理')
    failed_brand_names = failed_brand_names or {}
    failed_item_prices = failed_item_prices or {}
    failure_categories = failure_categories or {}
    retry_counts = retry_counts or {}
    brand_name = failed_brand_names.get(enquiry_item_id) or '无报价'
    # 价格检测失败时记录尝试价格
    item_sell_price = failed_item_prices.get(enquiry_item_id) if reason == FAIL_PRICE_CHECK_FAILED else None
    details.append({
        'supplier_demand_id': supplier_demand_id,
        'enquiry_item_id': enquiry_item_id,
        'item_oe': item_oe,
        'item_name': item_name,
        'item_description': item_description,
        'brand_id': None,
        'brand_name': brand_name,
        'item_sell_price': item_sell_price,
        'delivery_aging': None,
        'item_quality': None,
        'parts_no': None,
        'quote_status': quote_status,
        '_has_quote': False,
        '_failure_reason': reason,
        '_failure_category': failure_categories.get(enquiry_item_id),
        '_retry_count': retry_counts.get(enquiry_item_id, 0),
    })


def _extract_auto_quote(details, supplier_demand_id, enquiry_item_id, item_oe,
                        item_name, item_description, quote_status, quote_items):
    """自动报价的项目：从 extra_quote_items 提取信息"""
    for quote_info in quote_items:
        details.append({
            'supplier_demand_id': supplier_demand_id,
            'enquiry_item_id': enquiry_item_id,
            'item_oe': item_oe,
            'item_name': item_name,
            'item_description': item_description,
            'brand_id': quote_info.get('brandId'),
            'brand_name': quote_info.get('brandName'),
            'item_sell_price': quote_info.get('itemSellPrice'),
            'delivery_aging': quote_info.get('prepareGoodTimespan') or quote_info.get('deliveryAging', 1),
            'item_quality': quote_info.get('itemQuality'),
            'parts_no': quote_info.get('partsNo') or quote_info.get('itemPerhapsReplaceOe'),
            'quote_status': quote_status,
            '_has_quote': True,
            '_failure_reason': None
        })


def _parse_created_time(created_time_str):
    """解析汽配龙 createdTime 格式为 datetime"""
    if not created_time_str:
        return None
    try:
        # 2026-06-25T11:56:57.000+0800
        return datetime.strptime(str(created_time_str), '%Y-%m-%dT%H:%M:%S.%f%z')
    except (ValueError, TypeError):
        return None


# ============================================================================
# 明细收集与字段补全
# ============================================================================

def _collect_item_details(demand_list, extra_quote_items, failed_items,
                          failed_brand_names, failed_item_prices,
                          failure_categories, retry_counts,
                          enquiry_no, company):
    """遍历 demand_list 收集所有 item 的 details"""
    details = []
    for demand in demand_list:
        supplier_demand_id = demand.get('supplerDemandId')
        for item in demand.get('supplierEnquiryItemList', []):
            enquiry_item_id = item.get('enquiryItemId')
            item_oe = item.get('itemOe')
            item_name = item.get('itemName')
            item_description = item.get('itemDescription')
            quote_status = item.get('quoteStatus')
            quote_list = item.get('supplierQuoteItemList', [])

            # 自动报价项
            if enquiry_item_id in extra_quote_items:
                _extract_auto_quote(
                    details=details, supplier_demand_id=supplier_demand_id,
                    enquiry_item_id=enquiry_item_id, item_oe=item_oe,
                    item_name=item_name, item_description=item_description,
                    quote_status=quote_status, quote_items=extra_quote_items[enquiry_item_id]
                )

            # 已有报价项
            if quote_list:
                _extract_with_quotes(
                    details=details, supplier_demand_id=supplier_demand_id,
                    enquiry_item_id=enquiry_item_id, item_oe=item_oe,
                    item_name=item_name, item_description=item_description,
                    quote_status=quote_status, quote_list=quote_list
                )
            elif enquiry_item_id in failed_items:
                _extract_without_quotes(
                    details=details, supplier_demand_id=supplier_demand_id,
                    enquiry_item_id=enquiry_item_id, item_oe=item_oe,
                    item_name=item_name, item_description=item_description,
                    quote_status=quote_status, failed_items=failed_items,
                    failed_brand_names=failed_brand_names,
                    failed_item_prices=failed_item_prices,
                    enquiry_no=enquiry_no,
                    failure_categories=failure_categories,
                    retry_counts=retry_counts
                )
            elif str(quote_status).strip() == 'WAITING_QUOTE':
                qpl_log(
                    f"[{company or 'unknown'}] 项目 {enquiry_item_id} 无报价且未进入失败记录 "
                    f"(quote_status={quote_status})，按规则跳过",
                    order_no=enquiry_no
                )
                continue
            else:
                # 状态异常：不中断整单，按业务失败明细落库（下轮按已处理跳过）
                qpl_log(
                    f"[{company or 'unknown'}] 项目 {enquiry_item_id} 状态异常 "
                    f"(quote_status={quote_status}) 无报价记录，按失败明细落库",
                    order_no=enquiry_no
                )
                _extract_without_quotes(
                    details=details, supplier_demand_id=supplier_demand_id,
                    enquiry_item_id=enquiry_item_id, item_oe=item_oe,
                    item_name=item_name, item_description=item_description,
                    quote_status=quote_status,
                    failed_items={enquiry_item_id: f'状态异常({quote_status})'},
                    enquiry_no=enquiry_no
                )
    return details


def _enrich_result_fields(details, order_meta, item_submit_results, order_success):
    """给每个 detail 追加订单级别字段及新表结构化字段"""
    fail_type_map = {
        'business': '业务错误',
        'temporary': '临时错误',
        'retry_exhausted': '重试耗尽',
    }
    for detail in details:
        detail.update(order_meta)
        item_id = detail.get('enquiry_item_id')
        item_result = item_submit_results.get(item_id)
        failure_category = detail.get('_failure_category')
        detail['fail_type'] = fail_type_map.get(
            failure_category, '业务错误' if failure_category else '成功'
        )

        if isinstance(item_result, dict):
            detail['quote_source'] = item_result.get('quote_source', '已有报价')
            detail['is_quoted'] = item_result.get('is_quoted', 1 if detail['_has_quote'] else 0)
            detail['fail_stage'] = item_result.get('fail_stage', '无')
            detail['fail_reason'] = item_result.get('fail_reason') or detail.get('_failure_reason')
            detail['submit_status'] = item_result.get('submit_status', '未提交')
            detail['submit_message'] = item_result.get('submit_message', '')
        else:
            detail['quote_source'] = '已有报价'
            detail['is_quoted'] = 1 if detail['_has_quote'] else 0
            detail['fail_stage'] = '无'
            detail['fail_reason'] = detail.get('_failure_reason')
            detail['submit_status'] = '提交成功' if order_success else '提交失败'
            detail['submit_message'] = ''

        detail['retry_count'] = detail.get('_retry_count', 0)


def extract_quote_details(detail_data, failed_items=None, extra_quote_items=None,
                          item_submit_results=None, order_success=True,
                          failed_brand_names=None, failed_item_prices=None,
                          failure_categories=None, retry_counts=None,
                          company=None):
    """
    从详情数据中提取报价明细（包括无报价的失败项目）

    Args:
        detail_data: 询价单详情数据
        failed_items: 失败原因字典 {enquiry_item_id: reason}
        extra_quote_items: 自动报价项字典 {enquiry_item_id: [quote_item, ...]}
        item_submit_results: 每个项目的 submit_result 字符串 {enquiry_item_id: result}
        order_success: 订单整体是否成功
        failed_brand_names: 失败项实际尝试过的品牌名 {enquiry_item_id: brand_name}
        failed_item_prices: 价格检测失败时的尝试价格 {enquiry_item_id: sell_price}
        failure_categories: 失败分类字典 {enquiry_item_id: category}
        retry_counts: 重试次数字典 {enquiry_item_id: count}
        company: 组织代码，用于日志标识

    Returns:
        list: 报价明细列表
    """
    failed_items = failed_items or {}
    extra_quote_items = extra_quote_items or {}
    item_submit_results = item_submit_results or {}
    failed_brand_names = failed_brand_names or {}
    failed_item_prices = failed_item_prices or {}
    failure_categories = failure_categories or {}
    retry_counts = retry_counts or {}

    demand_list = detail_data.get('supplierEnquiryDemandList', [])
    enquiry_no = detail_data.get('supplierEnquiryNo')

    order_meta = {
        'created_time': _parse_created_time(detail_data.get('createdTime')),
        'vin_code': detail_data.get('vinCode'),
        'car_type': detail_data.get('carType5')
    }

    details = _collect_item_details(
        demand_list, extra_quote_items, failed_items,
        failed_brand_names, failed_item_prices,
        failure_categories, retry_counts,
        enquiry_no, company
    )

    _enrich_result_fields(details, order_meta, item_submit_results, order_success)

    return details
