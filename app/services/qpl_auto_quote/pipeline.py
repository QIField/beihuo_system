#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价 · 单订单流水线（P1-P6）

P1 详情分页拉明细 → P2 过滤（本地终态/冷却中） → P3 匹配（复用旧匹配链）
→ P4 priceCheck（匹配链内含） → P5 构造 PAGE_QUOTE 提交体 → P6 提交 + 三层落库

状态同步规则：
- 详情中 quoteStatus=QUOTED 的明细 → 本地同步为 quoted（已有报价）
- 本地产出报价项的明细 → quoted
- 匹配失败 → failed_biz（确定性，不重试）
- 提交失败 → failed_temp（冷却重试，耗尽转终态）
- 宝马(C类)订单匹配前先补齐本地 OE 库（见 bmw_oe.py）
- 车辆品牌无法识别 → 本轮跳过，明细保持 pending
"""

from datetime import datetime

from app.utils.qpl_auto_bill.qpl_config import qpl_log
from app.services.qpl_auto_quote.constants import (
    ACTION_FETCH_DETAIL,
    ACTION_MATCH,
    ACTION_SUBMIT,
    RESULT_FAIL,
    RESULT_SKIP,
    RESULT_SUCCESS,
    SOURCE_CRM,
    STATUS_QUOTED,
    TARGET_REMOTE_STATUSES,
)
from app.services.qpl_auto_quote.bmw_oe import ensure_bmw_oes_for_order
from app.services.qpl_auto_quote.enquiry_api import get_enquiry_detail_all, submit_enquiry_page
from app.services.qpl_auto_quote.matcher import match_order_by_brand, extract_quote_summary
from app.services.qpl_auto_quote.quote_builder import build_submit_request
from app.services.qpl_auto_quote.persistence import (
    fetch_item_statuses,
    mark_item_failed,
    mark_item_quoted,
    record_attempt,
    update_order_progress,
    upsert_items,
    upsert_order,
)

TERMINAL_STATUSES = (STATUS_QUOTED, 'failed_biz')


def process_order(company, enquiry_no, round_id):
    """
    处理单个订单的完整流水线。

    Returns:
        bool: 本轮该订单是否有报价提交动作（供轮次统计）
    """
    # P1 详情全量
    detail = get_enquiry_detail_all(enquiry_no, company)
    if not detail:
        record_attempt(company, enquiry_no, 0, round_id,
                       ACTION_FETCH_DETAIL, RESULT_FAIL,
                       fail_stage='详情接口', fail_reason='详情接口失败')
        qpl_log(f"[{company}] {enquiry_no} 详情接口失败，跳过该单")
        return False

    # P1 落库：订单 + 明细（重复入库不重置状态机字段）
    upsert_order(company, _extract_order_fields(detail))
    upsert_items(company, enquiry_no, _extract_items(detail, company))
    _sync_quoted_from_detail(company, enquiry_no, detail)

    # 配送方式（实测提交接口校验"配送方式为空"，必须先调取货方式接口）
    _fill_pickup_info(detail, company)

    # P2 过滤：本地终态/冷却中的明细本轮跳过
    target_candidate_ids = _collect_target_item_ids(detail)
    skip_ids = _get_skip_item_ids(company, target_candidate_ids)
    target_ids = target_candidate_ids - skip_ids

    if not target_ids:
        update_order_progress(company, enquiry_no)
        return True

    # 宝马订单前置：补齐本地 OE 库（非宝马订单直接返回空统计）
    ensure_bmw_oes_for_order(detail, company, skip_item_ids=skip_ids)

    # P3-P4 匹配（含 priceCheck）
    match = match_order_by_brand(detail, company, skip_item_ids=skip_ids)
    if match is None:
        for item_id in target_ids:
            record_attempt(company, enquiry_no, item_id, round_id,
                           ACTION_MATCH, RESULT_SKIP,
                           fail_stage='品牌识别', fail_reason='车辆品牌无法识别')
        qpl_log(f"[{company}] {enquiry_no} 车辆品牌无法识别，跳过（{len(target_ids)} 条明细保持待处理）")
        return False

    # P5 构造提交体
    extra = {k: v for k, v in (match['extra_quote_items'] or {}).items() if v}
    request = build_submit_request(detail, extra)

    # P6 提交
    resp = submit_enquiry_page(request, enquiry_no, company)
    submitted = bool(resp and resp.get('code') == 10000)

    _persist_round_result(company, enquiry_no, round_id, match, extra,
                          request, resp, submitted)
    update_order_progress(company, enquiry_no)
    return submitted


# ============================================================================
# 详情提取
# ============================================================================

def _fill_pickup_info(detail, company):
    """调取货方式接口，把 pickUpWay/pickUpWayStr/deliveryAddress 合入详情（平移旧逻辑）"""
    from app.utils.qpl_auto_bill.enquiry_api import get_pickup_way_and_distance, extract_pickup_info
    shop_uid = detail.get('shopUid')
    if not shop_uid:
        return
    try:
        pickup_result = get_pickup_way_and_distance(
            shop_uid, detail.get('supplierEnquiryNo'), detail.get('tuhuSupplierId'), company)
        detail.update(extract_pickup_info(pickup_result))
    except Exception as e:
        qpl_log(f"[{company}] {detail.get('supplierEnquiryNo')} 取货方式接口异常: {e}")


def _extract_order_fields(detail):
    """从详情提取 qpl_order 字段"""
    return {
        'supplier_enquiry_no': detail.get('supplierEnquiryNo'),
        'qpl_enquiry_no': detail.get('qplEnquiryNo'),
        'tid': detail.get('tid'),
        'car_brand': detail.get('carBrand'),
        'car_type5': detail.get('carType5'),
        'vin_code': detail.get('vinCode'),
        'shop_name': detail.get('shopName'),
        'trader_name': detail.get('traderName'),
        'user_name': detail.get('userName'),
        'user_phone': detail.get('userPhone'),
        'demand_status': detail.get('demandStatus'),
        'accept_status': detail.get('acceptStatus'),
        'multi_quote_gray': 1 if detail.get('multiQuoteGray') else 0,
        'enquiry_time': detail.get('latestEnquiryTime'),
        'first_handle_time': datetime.now(),
        'last_handle_time': datetime.now(),
    }


def _extract_items(detail, company):
    """从详情扁平化明细列表（含订单冗余字段）"""
    car_brand = detail.get('carBrand')
    items = []
    for demand, item in _iter_demand_items(detail):
        items.append({
            'supplier_demand_id': demand.get('supplerDemandId'),
            'enquiry_item_id': item.get('enquiryItemId'),
            'item_name': item.get('itemName'),
            'item_nick_names': _join_names(item.get('itemNickNames')),
            'item_oe': item.get('itemOe'),
            'item_amount': item.get('itemAmount', 1),
            'assembly_quantity': item.get('assemblyQuantity', 1),
            'item_quality_list': _join_names(item.get('itemQualityList')),
            'sale_category_name': item.get('saleCategoryName'),
            'car_brand': car_brand,
        })
    return items


def _iter_demand_items(detail):
    """统一迭代 supplierEnquiryDemandList → supplierEnquiryItemList（防御性空列表兜底）"""
    for demand in detail.get('supplierEnquiryDemandList') or []:
        for item in demand.get('supplierEnquiryItemList') or []:
            yield demand, item


def _join_names(names):
    """列表/字符串统一转逗号串"""
    if isinstance(names, list):
        return ','.join(str(n) for n in names)
    return names


def _collect_target_item_ids(detail):
    """
    收集详情中本轮需要处理的明细 ID。

    范围与旧 CRM 现货流程一致（process_crm_spot_quote）：
    - WAITING_QUOTE：从未报价，走完整匹配链（CRM/奔驰/宝马）
    - PART_QUOTE：部分报价，仍有未报完需求，走 CRM 现货补报
      （旧流程实测：全 PART_QUOTE 订单正是 A 类 CRM 现货的主战场，
      新页面"待报价"tab 的存量单大多处于该状态）
    - QUOTED 不入 target：已全部报价，P1 同步为本地 quoted 终态
    """
    return {
        item['enquiryItemId']
        for _, item in _iter_demand_items(detail)
        if item.get('quoteStatus') in TARGET_REMOTE_STATUSES and item.get('enquiryItemId')
    }


def _sync_quoted_from_detail(company, enquiry_no, detail):
    """详情中已 QUOTED 的明细同步本地为 quoted（已有报价）"""
    for _, item in _iter_demand_items(detail):
        if item.get('quoteStatus') == 'QUOTED' and item.get('enquiryItemId'):
            mark_item_quoted(company, item['enquiryItemId'],
                             quote_source='已有报价')


def _get_skip_item_ids(company, waiting_ids):
    """本地终态或冷却未到期的明细集合（本轮跳过）"""
    if not waiting_ids:
        return set()
    statuses = fetch_item_statuses(company, waiting_ids)
    skip = set()
    for item_id, row in statuses.items():
        if row['status'] in TERMINAL_STATUSES:
            skip.add(item_id)
        elif row['status'] == 'failed_temp' and row['next_retry_time'] and \
                row['next_retry_time'] > datetime.now():
            skip.add(item_id)
    return skip


# ============================================================================
# 结果落库
# ============================================================================

def _persist_round_result(company, enquiry_no, round_id, match, extra,
                          request, resp, submitted):
    """P6 后落库：报价成功/匹配失败/提交失败三类，全部写 attempt 流水"""
    if submitted:
        _mark_quoted_items(company, enquiry_no, round_id, extra)
    else:
        message = (resp or {}).get('message', '无响应') if resp else '无响应'
        _mark_submit_failed(company, enquiry_no, round_id, request, resp, message)

    for item_id, reason in (match['failed_items'] or {}).items():
        if item_id in extra:
            continue  # 该明细已有报价项，失败原因不影响结果
        mark_item_failed(company, item_id,
                         fail_stage='品牌匹配', fail_reason=reason, is_temp=False)
        record_attempt(company, enquiry_no, item_id, round_id,
                       ACTION_MATCH, RESULT_FAIL,
                       fail_stage='品牌匹配', fail_reason=reason)


def _mark_quoted_items(company, enquiry_no, round_id, extra):
    """报价项明细落终态 quoted + attempt 成功流水"""
    for item_id, quote_items in extra.items():
        if not quote_items:
            continue
        summary = extract_quote_summary(quote_items[0])
        mark_item_quoted(company, item_id, quote_source=SOURCE_CRM, **summary)
        record_attempt(company, enquiry_no, item_id, round_id,
                       ACTION_SUBMIT, RESULT_SUCCESS,
                       quote_source=SOURCE_CRM,
                       request_snapshot={'quoteItems': quote_items},
                       response_snapshot=summary)


def _mark_submit_failed(company, enquiry_no, round_id, request, resp, message):
    """提交失败：本次构造了报价项或待处理明细全部进入冷却重试"""
    request_snapshot = {
        'demandList': request.get('demandList'),
        'quoteType': request.get('quoteType'),
    }
    target_ids = _collect_request_item_ids(request)
    for item_id in target_ids:
        mark_item_failed(company, item_id,
                         fail_stage='接口请求', fail_reason=f'提交失败: {message}',
                         is_temp=True)
        record_attempt(company, enquiry_no, item_id, round_id,
                       ACTION_SUBMIT, RESULT_FAIL,
                       fail_stage='接口请求', fail_reason=message,
                       request_snapshot=request_snapshot,
                       response_snapshot=resp)


def _collect_request_item_ids(request):
    """从提交体收集涉及的明细 ID（报价项所在明细 + WAITING 明细）"""
    item_ids = set()
    for demand in request.get('demandList') or []:
        for item in demand.get('enquiryItemList') or []:
            item_id = item.get('supplierEnquiryItemId')
            if item.get('quoteItemList') or item.get('quoteStatus') == 'WAITING_QUOTE':
                if item_id:
                    item_ids.add(item_id)
    return item_ids
