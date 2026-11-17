#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙报价服务
处理报价提交和结果保存
支持多组织循环运行

原则：
  1. 减少逻辑判断，必要情况下采取字典分发
  2. 异常按层级隔离：条目级记录后跳过、订单级跳过继续、公司级跳过继续，
     不让单点异常中断整轮任务
"""

import logging
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
    FAIL_NO_CANDIDATE,
    FAIL_CRM_API_ERROR,
)
from app.utils.qpl_auto_bill.qpl_config import get_supported_companies, qpl_log
from app.utils.database_connection import get_db_connection

_qpl_logger = logging.getLogger('qpl_auto_bill')


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
    保存报价记录到 qpl_quote_result_v2（含失败项目），幂等写入。

    同一个 (company, supplier_enquiry_no, enquiry_item_id, brand_name) 已存在时更新，
    不存在时插入。brand_name 为 NULL 时也被视为唯一键的一部分。

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
        INSERT INTO qpl_quote_result_v2 (
            supplier_enquiry_no, company, enquiry_item_id, supplier_demand_id,
            item_oe, item_name, item_description, brand_id, brand_name,
            item_sell_price, delivery_aging, item_quality, parts_no,
            quote_source, is_quoted, fail_stage, fail_reason, fail_type,
            retry_count, submit_status, submit_message, order_status,
            created_time, vin_code, submit_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            supplier_demand_id = VALUES(supplier_demand_id),
            item_oe = VALUES(item_oe),
            item_name = VALUES(item_name),
            item_description = VALUES(item_description),
            brand_id = VALUES(brand_id),
            item_sell_price = VALUES(item_sell_price),
            delivery_aging = VALUES(delivery_aging),
            item_quality = VALUES(item_quality),
            parts_no = VALUES(parts_no),
            quote_source = VALUES(quote_source),
            is_quoted = VALUES(is_quoted),
            fail_stage = VALUES(fail_stage),
            fail_reason = VALUES(fail_reason),
            fail_type = VALUES(fail_type),
            retry_count = VALUES(retry_count),
            submit_status = VALUES(submit_status),
            submit_message = VALUES(submit_message),
            order_status = VALUES(order_status),
            created_time = VALUES(created_time),
            vin_code = VALUES(vin_code),
            submit_time = VALUES(submit_time)
        """

        for detail in details:
            cursor.execute(sql, (
                enquiry_no,
                company,
                detail.get('enquiry_item_id'),
                detail.get('supplier_demand_id'),
                detail.get('item_oe'),
                detail.get('item_name'),
                detail.get('item_description'),
                detail.get('brand_id'),
                detail.get('brand_name'),
                detail.get('item_sell_price'),
                detail.get('delivery_aging'),
                detail.get('item_quality'),
                detail.get('parts_no'),
                detail.get('quote_source'),
                detail.get('is_quoted', 0),
                detail.get('fail_stage'),
                detail.get('fail_reason'),
                detail.get('fail_type'),
                detail.get('retry_count', 0),
                detail.get('submit_status'),
                detail.get('submit_message'),
                detail.get('order_status'),
                detail.get('created_time'),
                detail.get('vin_code'),
                submit_time,
            ))

        conn.commit()
        qpl_log(f"[{company}] 保存报价记录到v2表 {len(details)} 条", order_no=enquiry_no)

    conn.close()


def save_flow_trace_records(flow_trace_list, company='fsbbr'):
    """
    保存流程追踪记录到 qpl_quote_flow_trace。

    Args:
        flow_trace_list: 流程追踪列表，每个元素为 dict
        company: 组织代码
    """
    if not flow_trace_list:
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
            INSERT INTO qpl_quote_flow_trace (
                supplier_enquiry_no, company, enquiry_item_id, item_oe, item_name,
                flow_name, flow_status, fail_stage, fail_reason, stage_detail
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            for trace in flow_trace_list:
                cursor.execute(sql, (
                    trace.get('supplier_enquiry_no'),
                    company,
                    trace.get('enquiry_item_id'),
                    trace.get('item_oe'),
                    trace.get('item_name'),
                    trace.get('flow_name'),
                    trace.get('flow_status'),
                    trace.get('fail_stage'),
                    trace.get('fail_reason'),
                    trace.get('stage_detail'),
                ))
        conn.commit()
        qpl_log(f"[{company}] 保存流程追踪记录 {len(flow_trace_list)} 条")
    finally:
        conn.close()


# ============================================================================
# 主流程
# ============================================================================

# ============================================================================
# 新表字段映射（中文枚举）
# ============================================================================

_CRM_FAIL_STAGE_MAP = {
    FAIL_PART_NO_MISMATCH: 'partNo匹配',
    FAIL_NO_EFFECTIVE_PRICE: '价格校验',
    FAIL_PRICE_CHECK_FAILED: 'priceCheck',
    FAIL_NO_CANDIDATE: '品牌匹配',
    FAIL_CRM_API_ERROR: '接口请求',
    FAIL_ADAPT_LIST_EMPTY: '品牌匹配',
    FAIL_NO_STOCK: '库存检查',
}

_BC_FAIL_STAGE_MAP = {
    FAIL_ADAPT_LIST_EMPTY: '无',
    FAIL_ORIGINAL_PRODUCT_NO_OE: '无',
    FAIL_OE_DATA_MISSING: '库存检查',
    FAIL_NO_STOCK: '库存检查',
    FAIL_INVALID_PRICE: '价格校验',
    FAIL_PRICE_CHECK_FAILED: 'priceCheck',
}

_BC_SOURCE_NAME = {
    'B': '奔驰接口',
    'C': '宝马接口',
}


def _map_crm_fail_stage(reason):
    """CRM失败原因映射到失败环节"""
    return _CRM_FAIL_STAGE_MAP.get(reason, '品牌匹配')


def _map_bc_fail_stage(reason):
    """B/C失败原因映射到失败环节"""
    return _BC_FAIL_STAGE_MAP.get(reason, '无')


def _map_quote_source(item_id, category, crm_quote_item_ids, bc_quote_item_ids,
                      crm_failed_items, bc_failed_items):
    """判定报价来源（中文）"""
    if item_id in crm_quote_item_ids:
        return 'CRM现货'
    if item_id in bc_quote_item_ids:
        return _BC_SOURCE_NAME.get(category, '未知')
    if item_id in crm_failed_items:
        return 'CRM现货'
    if item_id in bc_failed_items:
        return _BC_SOURCE_NAME.get(category, '未知')
    return '已有报价'


def _build_item_submit_results(order_success, crm_quote_item_ids, crm_failed_items,
                               original_quoted_ids, bc_quote_item_ids, bc_failed_items,
                               category, submit_message=''):
    """
    按项目构造新表字段

    Returns:
        dict: {item_id: {'quote_source', 'is_quoted', 'fail_stage', 'fail_reason',
                         'fail_type', 'submit_status', 'submit_message'}}
    """
    item_results = {}
    all_item_ids = (
        set(crm_quote_item_ids) |
        set(crm_failed_items.keys()) |
        set(bc_quote_item_ids) |
        set(bc_failed_items.keys())
    )

    for item_id in all_item_ids:
        # 判定是否报价成功
        is_quoted = 1 if (item_id in crm_quote_item_ids or item_id in bc_quote_item_ids) else 0

        # 判定失败环节和原因
        fail_stage = '无'
        fail_reason = None
        if is_quoted == 0:
            if item_id in crm_failed_items:
                fail_stage = _map_crm_fail_stage(crm_failed_items[item_id][0])
                fail_reason = crm_failed_items[item_id][0]
            elif item_id in bc_failed_items:
                fail_stage = _map_bc_fail_stage(bc_failed_items[item_id])
                fail_reason = bc_failed_items[item_id]

        # 提交状态（订单级统一）
        if order_success:
            submit_status = '提交成功'
        else:
            submit_status = '提交失败'

        item_results[item_id] = {
            'quote_source': _map_quote_source(
                item_id, category, crm_quote_item_ids, bc_quote_item_ids,
                crm_failed_items, bc_failed_items
            ),
            'is_quoted': is_quoted,
            'fail_stage': fail_stage,
            'fail_reason': fail_reason,
            'submit_status': submit_status,
            'submit_message': submit_message,
        }

    return item_results


def _persist_order_result(result, company):
    """保存单个订单的报价结果与流程追踪（明细提取 + 落库）"""
    # 判定提交状态
    message = result.get('message', '')
    is_cannot_quote = message.startswith('cannotQuote')
    if is_cannot_quote:
        submit_status = 'cannot_quote成功' if result.get('success') else 'cannot_quote失败'
    elif result.get('success'):
        submit_status = '提交成功'
    else:
        submit_status = '提交失败'

    # 构造每个项目的新表字段
    item_submit_results = _build_item_submit_results(
        result.get('success', False),
        result.get('crm_quote_item_ids', set()),
        result.get('crm_failed_items', {}),
        result.get('original_quoted_ids', set()),
        result.get('bc_quote_item_ids', set()),
        result.get('bc_failed_items', {}),
        result.get('order_category', 'A'),
        submit_message=message
    )

    # 覆盖提交状态（根据订单级别统一）
    for item_id in item_submit_results:
        item_submit_results[item_id]['submit_status'] = submit_status

    # 提取明细并保存（所有结果都保存，不再判断 success）
    failed_items = result.get('failed_items', {})
    extra_quote_items = result.get('extra_quote_items', {})
    failed_brand_names = result.get('failed_brand_names', {})
    failed_item_prices = result.get('failed_item_prices', {})
    failure_categories = result.get('failure_categories', {})
    retry_counts = result.get('retry_counts', {})
    details = extract_quote_details(
        result['detail_data'], failed_items, extra_quote_items,
        item_submit_results, result.get('success', False),
        failed_brand_names=failed_brand_names,
        failed_item_prices=failed_item_prices,
        failure_categories=failure_categories,
        retry_counts=retry_counts,
        company=company
    )

    if details:
        save_quote_records(
            enquiry_no=result['enquiry_no'],
            details=details,
            submit_result=message,
            submit_time=result['submit_time'],
            company=company
        )

    # 保存流程追踪记录
    flow_trace_list = result.get('flow_trace_list', [])
    if flow_trace_list:
        save_flow_trace_records(flow_trace_list, company=company)


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
        try:
            _persist_order_result(result, company)
        except Exception as save_error:
            # 落库级异常隔离：单个订单保存失败不影响其余订单
            _qpl_logger.exception(
                f"[{company}] 报价结果落库失败: {result.get('enquiry_no')}: {save_error}"
            )

        # 统计（无论保存是否成功，该订单本轮均已处理）
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
        try:
            result = process_and_save_quotes_for_company(company, begin_date, end_date)
        except Exception:
            # 公司级异常隔离：单个公司失败不影响其他公司
            _qpl_logger.exception(f"[汽配龙报价] 组织 {company} 本轮处理异常，跳过该公司继续")
            result = {
                'company': company,
                'success_count': 0,
                'fail_count': 0,
                'total': 0,
                'category_a': 0,
                'category_b': 0,
                'category_c': 0
            }
        all_results.append(result)

    # 汇总统计
    total_success = sum(r.get('success_count', 0) for r in all_results)
    total_fail = sum(r.get('fail_count', 0) for r in all_results)

    qpl_log(f"所有组织报价任务完成 | 成功={total_success} 失败={total_fail}")

    return all_results
