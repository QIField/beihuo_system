#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙报价服务
处理报价提交和结果保存
支持多组织循环运行

原则：
  1. 减少逻辑判断，必要情况下采取字典分发
  2. 问题直接暴露，不写错误处理语句
"""

from datetime import datetime
from app.utils.qpl_auto_bill.auto_submit_part_quote import (
    submit_all_quotes,
    FAIL_ADAPT_LIST_EMPTY,
    FAIL_ORIGINAL_PRODUCT_NO_OE,
    FAIL_OE_DATA_MISSING,
    FAIL_NO_STOCK,
    FAIL_INVALID_PRICE,
    FAIL_PART_NO_MISMATCH,
    FAIL_NO_EFFECTIVE_PRICE,
    FAIL_PRICE_CHECK_FAILED,
)
from app.utils.qpl_auto_bill.qpl_config import get_supported_companies, qpl_log
from app.utils.database_connection import get_db_connection


# ============================================================================
# 报价明细提取（含失败项目）
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
                            failed_brand_names=None, failed_item_prices=None, enquiry_no=None, **_):
    """无报价的项目：记录失败原因

    brand_name 展示规则：
        - 若 failed_brand_names 中有实际尝试过的品牌名 → 使用该品牌名
        - 否则（仅 no_original_product / 程序未处理 等场景）→ '无报价'

    价格检测失败时，把当时的尝试价格写入 item_sell_price，方便排查。
    """
    reason = failed_items.get(enquiry_item_id, '未处理')
    failed_brand_names = failed_brand_names or {}
    failed_item_prices = failed_item_prices or {}
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
        '_failure_reason': reason
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


def extract_quote_details(detail_data, failed_items=None, extra_quote_items=None,
                          item_submit_results=None, order_success=True,
                          failed_brand_names=None, failed_item_prices=None):
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

    Returns:
        list: 报价明细列表
    """
    failed_items = failed_items or {}
    extra_quote_items = extra_quote_items or {}
    item_submit_results = item_submit_results or {}
    failed_brand_names = failed_brand_names or {}
    failed_item_prices = failed_item_prices or {}
    details = []

    demand_list = detail_data.get('supplierEnquiryDemandList', [])
    enquiry_no = detail_data.get('supplierEnquiryNo')

    # 订单级别字段
    order_meta = {
        'created_time': _parse_created_time(detail_data.get('createdTime')),
        'vin_code': detail_data.get('vinCode'),
        'car_type': detail_data.get('carType5')
    }

    # 默认 submit_result：未走 CRM/B/C 流程的已有报价项
    order_part = '操作成功' if order_success else '操作失败'
    default_submit_result = f"[{order_part}][][]"

    for demand in demand_list:
        supplier_demand_id = demand.get('supplerDemandId')

        for item in demand.get('supplierEnquiryItemList', []):
            enquiry_item_id = item.get('enquiryItemId')
            item_oe = item.get('itemOe')
            item_name = item.get('itemName')
            item_description = item.get('itemDescription')
            quote_status = item.get('quoteStatus')

            quote_list = item.get('supplierQuoteItemList', [])

            # 优先判断是否为自动报价项
            if enquiry_item_id in extra_quote_items:
                _extract_auto_quote(
                    details=details,
                    supplier_demand_id=supplier_demand_id,
                    enquiry_item_id=enquiry_item_id,
                    item_oe=item_oe,
                    item_name=item_name,
                    item_description=item_description,
                    quote_status=quote_status,
                    quote_items=extra_quote_items[enquiry_item_id]
                )
            elif quote_list:
                _extract_with_quotes(
                    details=details,
                    supplier_demand_id=supplier_demand_id,
                    enquiry_item_id=enquiry_item_id,
                    item_oe=item_oe,
                    item_name=item_name,
                    item_description=item_description,
                    quote_status=quote_status,
                    quote_list=quote_list
                )
            elif enquiry_item_id in failed_items:
                _extract_without_quotes(
                    details=details,
                    supplier_demand_id=supplier_demand_id,
                    enquiry_item_id=enquiry_item_id,
                    item_oe=item_oe,
                    item_name=item_name,
                    item_description=item_description,
                    quote_status=quote_status,
                    failed_items=failed_items,
                    failed_brand_names=failed_brand_names,
                    failed_item_prices=failed_item_prices,
                    enquiry_no=enquiry_no
                )
            elif str(quote_status).strip() == 'WAITING_QUOTE':
                # CRM 未匹配 / 无原厂 等明确不记录场景：跳过
                qpl_log(
                    f"[{company}] 项目 {enquiry_item_id} 无报价且未进入失败记录 "
                    f"(quote_status={quote_status})，按规则跳过",
                    order_no=enquiry_no
                )
                continue
            else:
                # 非 WAITING_QUOTE 且无报价：属于数据异常，记录并暴露
                qpl_log(
                    f"[{company}] 项目 {enquiry_item_id} 状态异常 "
                    f"(quote_status={quote_status}) 无报价记录",
                    order_no=enquiry_no
                )
                raise RuntimeError(
                    f"订单 {enquiry_no} 项目 {enquiry_item_id} 状态异常，"
                    f"quote_status={quote_status}，无报价记录"
                )

    # 给每个明细追加订单级别字段、submit_result 和 result_source
    for detail in details:
        detail.update(order_meta)
        item_id = detail.get('enquiry_item_id')
        item_result = item_submit_results.get(item_id)
        if isinstance(item_result, dict):
            detail['_submit_result'] = item_result.get('submit_result', default_submit_result)
            detail['_result_source'] = item_result.get('result_source', 'unknown')
        elif item_result:
            # 兼容旧格式字符串
            detail['_submit_result'] = item_result
            detail['_result_source'] = 'unknown'
        else:
            # 未走 CRM/B/C 流程的已有报价项
            detail['_submit_result'] = default_submit_result
            detail['_result_source'] = 'existing_quote'

    return details


# ============================================================================
# 报价记录保存
# ============================================================================

_RESULT_BUILDERS = {}


def _register_result_builder(has_quote):
    """注册结果构建器"""
    def decorator(func):
        _RESULT_BUILDERS[has_quote] = func
        return func
    return decorator


@_register_result_builder(True)
def _build_success_result(detail, submit_result):
    """有报价项目：使用按项目构造的 submit_result"""
    return detail.get('_submit_result', submit_result)


@_register_result_builder(False)
def _build_failure_result(detail, submit_result):
    """无报价项目：使用按项目构造的 submit_result"""
    return detail.get('_submit_result', detail.get('_failure_reason', '未处理'))


def save_quote_records(enquiry_no, details, submit_result, submit_time, company='fsbbr'):
    """
    保存报价记录到数据库（含失败项目）

    Args:
        enquiry_no: 询价单号
        details: 报价明细列表
        submit_result: 提交结果
        submit_time: 提交时间
        company: 组织代码，默认 fsbbr
    """
    conn = get_db_connection()

    with conn.cursor() as cursor:
        sql = """
        INSERT INTO qpl_quote_record (
            supplier_enquiry_no, supplier_demand_id, enquiry_item_id,
            item_oe, item_name, item_description, brand_id, brand_name,
            item_sell_price, delivery_aging, item_quality, parts_no,
            quote_status, submit_result, result_source, submit_time, company,
            created_time, vin_code, car_type
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        for detail in details:
            # 用布尔值作为字典键分发，消除 if/else
            record_result = _RESULT_BUILDERS[detail['_has_quote']](detail, submit_result)
            result_source = detail.get('_result_source', 'unknown')

            cursor.execute(sql, (
                enquiry_no,
                detail.get('supplier_demand_id'),
                detail.get('enquiry_item_id'),
                detail.get('item_oe'),
                detail.get('item_name'),
                detail.get('item_description'),
                detail.get('brand_id'),
                detail.get('brand_name'),
                detail.get('item_sell_price'),
                detail.get('delivery_aging'),
                detail.get('item_quality'),
                detail.get('parts_no'),
                detail.get('quote_status'),
                record_result,
                result_source,
                submit_time,
                company,
                detail.get('created_time'),
                detail.get('vin_code'),
                detail.get('car_type')
            ))

        conn.commit()
        qpl_log(f"[{company}] 保存报价记录 {len(details)} 条", order_no=enquiry_no)

    conn.close()


# ============================================================================
# 主流程
# ============================================================================

_CRM_FAIL_REASON_MAP = {
    FAIL_PART_NO_MISMATCH: 'crm_part_no_mismatch',
    FAIL_NO_EFFECTIVE_PRICE: 'crm_no_price',
    FAIL_PRICE_CHECK_FAILED: 'crm_price_check_failed',
}


_BC_FAIL_REASON_MAP = {
    FAIL_ADAPT_LIST_EMPTY: 'adapt_list_empty',
    FAIL_ORIGINAL_PRODUCT_NO_OE: 'original_product_no_oe',
    FAIL_OE_DATA_MISSING: 'oe_data_missing',
    FAIL_NO_STOCK: 'no_stock',
    FAIL_INVALID_PRICE: 'invalid_price',
    FAIL_PRICE_CHECK_FAILED: 'price_check_failed',
}


def _map_crm_fail_reason(reason):
    return _CRM_FAIL_REASON_MAP.get(reason, 'crm_failed')


def _map_bc_fail_reason(reason, category):
    if reason in _BC_FAIL_REASON_MAP:
        return _BC_FAIL_REASON_MAP[reason]
    return 'mercedes_failed' if category == 'B' else 'bmw_failed'


def _build_item_submit_results(order_success, crm_quote_item_ids, crm_failed_items,
                               original_quoted_ids, bc_quote_item_ids, bc_failed_items,
                               category):
    """
    按项目构造 submit_result 字符串和 result_source

    submit_result 格式：[操作成功/失败][crm流程][奔驰宝马接口]
    result_source 格式：前端展示/筛选用的结构化标签
    """
    item_results = {}
    all_item_ids = (
        set(crm_quote_item_ids) |
        set(crm_failed_items.keys()) |
        set(bc_quote_item_ids) |
        set(bc_failed_items.keys())
    )

    order_part = '操作成功' if order_success else '操作失败'

    for item_id in all_item_ids:
        # CRM 段
        crm_part = ''
        if item_id in crm_quote_item_ids:
            crm_part = 'crm报价成功'
        elif item_id in crm_failed_items:
            crm_part = crm_failed_items[item_id][0]

        # 是否显示 B/C 段
        show_bc = True
        if item_id in original_quoted_ids:
            # CRM 已报原厂，B/C 被跳过
            show_bc = False
        elif item_id in crm_failed_items:
            _, is_original = crm_failed_items[item_id]
            if not is_original:
                # CRM 处理的是非原厂且失败，不写 B/C 段
                show_bc = False

        # B/C 段
        bc_part = ''
        if show_bc:
            if item_id in bc_quote_item_ids:
                bc_part = '接口报价成功'
            elif item_id in bc_failed_items:
                bc_part = bc_failed_items[item_id]

        submit_result = f"[{order_part}][{crm_part}][{bc_part}]"

        # result_source 用于前端展示和筛选
        if item_id in crm_quote_item_ids:
            result_source = 'crm'
        elif item_id in bc_quote_item_ids:
            if category == 'B':
                result_source = 'mercedes'
            elif category == 'C':
                result_source = 'bmw'
            else:
                result_source = 'bc'
        elif item_id in crm_failed_items:
            result_source = _map_crm_fail_reason(crm_failed_items[item_id][0])
        elif item_id in bc_failed_items:
            result_source = _map_bc_fail_reason(bc_failed_items[item_id], category)
        else:
            result_source = 'unknown'

        item_results[item_id] = {
            'submit_result': submit_result,
            'result_source': result_source,
        }

    return item_results


def process_and_save_quotes_for_company(company, begin_date=None, end_date=None):
    """
    处理指定组织的报价并保存结果

    所有经过处理的订单（无论提交成功或失败）都会保存到数据库

    Args:
        company: 组织代码（必填）
        begin_date: 开始日期
        end_date: 结束日期

    Returns:
        dict: 处理结果统计
    """
    # 调用工具层提交报价
    results = submit_all_quotes(begin_date, end_date, company=company)

    # 分类计数
    category_counts = {'A': 0, 'B': 0, 'C': 0}
    success_count = 0
    fail_count = 0

    for result in results:
        # 构造每个项目的 submit_result 和 result_source
        item_submit_results = _build_item_submit_results(
            result.get('success', False),
            result.get('crm_quote_item_ids', set()),
            result.get('crm_failed_items', {}),
            result.get('original_quoted_ids', set()),
            result.get('bc_quote_item_ids', set()),
            result.get('bc_failed_items', {}),
            result.get('order_category', 'A')
        )

        # 提取明细并保存（所有结果都保存，不再判断 success）
        failed_items = result.get('failed_items', {})
        extra_quote_items = result.get('extra_quote_items', {})
        failed_brand_names = result.get('failed_brand_names', {})
        failed_item_prices = result.get('failed_item_prices', {})
        details = extract_quote_details(
            result['detail_data'], failed_items, extra_quote_items,
            item_submit_results, result.get('success', False),
            failed_brand_names=failed_brand_names,
            failed_item_prices=failed_item_prices
        )

        if details:
            save_quote_records(
                enquiry_no=result['enquiry_no'],
                details=details,
                submit_result=result['message'],
                submit_time=result['submit_time'],
                company=company
            )

        # 统计
        category_counts[result['order_category']] += 1
        if result['success']:
            success_count += 1
        else:
            fail_count += 1

    return {
        'company': company,
        'success_count': success_count,
        'fail_count': fail_count,
        'total': len(results),
        'category_a': category_counts['A'],
        'category_b': category_counts['B'],
        'category_c': category_counts['C']
    }


def process_and_save_quotes_for_all_companies(begin_date=None, end_date=None):
    """
    循环处理所有支持的组织的报价并保存结果

    Args:
        begin_date: 开始日期
        end_date: 结束日期

    Returns:
        list: 各组织处理结果统计列表
    """
    companies = get_supported_companies()
    all_results = []

    for company in companies:
        result = process_and_save_quotes_for_company(company, begin_date, end_date)
        all_results.append(result)

    # 汇总统计
    total_success = sum(r.get('success_count', 0) for r in all_results)
    total_fail = sum(r.get('fail_count', 0) for r in all_results)

    qpl_log(f"所有组织报价任务完成 | 成功={total_success} 失败={total_fail}")

    return all_results
