#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
报价结果落库

负责 qpl_quote_result_v2（报价记录）与 qpl_quote_flow_trace（流程追踪）的持久化，
以及单订单结果的落库编排。明细提取逻辑见 qpl_quote_detail_extract 模块。
"""

from app.utils.database_connection import get_db_connection
from app.utils.qpl_auto_bill.qpl_config import qpl_log
from app.utils.qpl_auto_bill.auto_submit_part_quote import (
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
from app.services.qpl_quote_detail_extract import extract_quote_details


# ============================================================================
# 报价记录保存
# ============================================================================

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


# ============================================================================
# 单订单落库编排
# ============================================================================

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
