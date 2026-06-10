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
from app.utils.qpl_auto_bill.auto_submit_part_quote import submit_all_quotes
from app.utils.qpl_auto_bill.qpl_config import get_supported_companies
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
                            item_name, item_description, quote_status, failed_items, **_):
    """无报价的项目：记录失败原因"""
    reason = failed_items.get(enquiry_item_id, '未处理')
    details.append({
        'supplier_demand_id': supplier_demand_id,
        'enquiry_item_id': enquiry_item_id,
        'item_oe': item_oe,
        'item_name': item_name,
        'item_description': item_description,
        'brand_id': None,
        'brand_name': '无报价',
        'item_sell_price': None,
        'delivery_aging': None,
        'item_quality': None,
        'parts_no': None,
        'quote_status': quote_status,
        '_has_quote': False,
        '_failure_reason': reason
    })


def extract_quote_details(detail_data, failed_items=None):
    """
    从详情数据中提取报价明细（包括无报价的失败项目）

    Args:
        detail_data: 询价单详情数据
        failed_items: 失败原因字典 {enquiry_item_id: reason}

    Returns:
        list: 报价明细列表
    """
    failed_items = failed_items or {}
    details = []

    demand_list = detail_data.get('supplierEnquiryDemandList', [])

    for demand in demand_list:
        supplier_demand_id = demand.get('supplerDemandId')

        for item in demand.get('supplierEnquiryItemList', []):
            enquiry_item_id = item.get('enquiryItemId')
            item_oe = item.get('itemOe')
            item_name = item.get('itemName')
            item_description = item.get('itemDescription')
            quote_status = item.get('quoteStatus')

            quote_list = item.get('supplierQuoteItemList', [])

            # 用布尔值作为字典键分发，消除 if/else
            handler = _QUOTE_EXTRACT_HANDLERS[bool(quote_list)]
            handler(
                details=details,
                supplier_demand_id=supplier_demand_id,
                enquiry_item_id=enquiry_item_id,
                item_oe=item_oe,
                item_name=item_name,
                item_description=item_description,
                quote_status=quote_status,
                quote_list=quote_list,
                failed_items=failed_items
            )

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
    """有报价项目：存接口返回结果"""
    return submit_result


@_register_result_builder(False)
def _build_failure_result(detail, submit_result):
    """无报价项目：存失败原因"""
    return detail.get('_failure_reason', '未处理')


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
            quote_status, submit_result, submit_time, company
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        for detail in details:
            # 用布尔值作为字典键分发，消除 if/else
            record_result = _RESULT_BUILDERS[detail['_has_quote']](detail, submit_result)

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
                submit_time,
                company
            ))

        conn.commit()
        print(f"[报价保存][{company}] 成功保存 {len(details)} 条记录，询价单: {enquiry_no}")

    conn.close()


# ============================================================================
# 主流程
# ============================================================================

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
    print(f"\n[报价服务][{company}] 开始处理报价任务 - {datetime.now()}")

    # 调用工具层提交报价
    results = submit_all_quotes(begin_date, end_date, company=company)

    # 分类计数
    category_counts = {'A': 0, 'B': 0}
    success_count = 0
    fail_count = 0

    for result in results:
        # 提取明细并保存（所有结果都保存，不再判断 success）
        failed_items = result.get('failed_items', {})
        details = extract_quote_details(result['detail_data'], failed_items)

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

    print(f"[报价服务][{company}] 任务完成 - 成功: {success_count}, 失败: {fail_count}")
    print(f"[报价服务][{company}] 类别 A (全PART_QUOTE): {category_counts['A']}, 类别 B (奔驰): {category_counts['B']}")

    return {
        'company': company,
        'success_count': success_count,
        'fail_count': fail_count,
        'total': len(results),
        'category_a': category_counts['A'],
        'category_b': category_counts['B']
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
    print(f"\n[报价服务] ====== 开始处理所有组织的报价任务 ====== {datetime.now()}")

    companies = get_supported_companies()
    all_results = []

    for company in companies:
        result = process_and_save_quotes_for_company(company, begin_date, end_date)
        all_results.append(result)

    # 汇总统计
    total_success = sum(r.get('success_count', 0) for r in all_results)
    total_fail = sum(r.get('fail_count', 0) for r in all_results)

    print(f"\n[报价服务] ====== 所有组织报价任务完成 ======")
    print(f"[报价服务] 汇总结果: 成功 {total_success}, 失败 {total_fail}")

    return all_results
