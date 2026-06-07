#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙报价服务
处理报价提交和结果保存
支持多组织循环运行
"""

from datetime import datetime
from app.utils.qpl_auto_bill.auto_submit_part_quote import submit_all_quotes
from app.utils.qpl_auto_bill.qpl_config import get_supported_companies
from app.utils.database_connection import get_db_connection


def extract_quote_details(detail_data):
    """
    从详情数据中提取报价明细

    Args:
        detail_data: 询价单详情数据

    Returns:
        list: 报价明细列表
    """
    details = []

    # 提取询价单级别的字段
    created_time = detail_data.get('createdTime')
    vin_code = detail_data.get('vinCode')
    car_type = detail_data.get('carType5')

    demand_list = detail_data.get('supplierEnquiryDemandList', [])
    for demand in demand_list:
        supplier_demand_id = demand.get('supplerDemandId')

        for item in demand.get('supplierEnquiryItemList', []):
            enquiry_item_id = item.get('enquiryItemId')

            for quote_info in item.get('supplierQuoteItemList', []):
                details.append({
                    'supplier_demand_id': supplier_demand_id,
                    'enquiry_item_id': enquiry_item_id,
                    'item_oe': item.get('itemOe'),
                    'item_name': item.get('itemName'),
                    'item_description': item.get('itemDescription'),
                    'brand_id': quote_info.get('brandId'),
                    'brand_name': quote_info.get('brandName'),
                    'item_sell_price': quote_info.get('itemSellPrice'),
                    'delivery_aging': quote_info.get('deliveryAging', 1),
                    'item_quality': quote_info.get('itemQuality'),
                    'parts_no': quote_info.get('partsNo'),
                    'quote_status': item.get('quoteStatus'),
                    'created_time': created_time,
                    'vin_code': vin_code,
                    'car_type': car_type
                })

    return details


def save_quote_records(enquiry_no, details, submit_result, submit_time, company='fsbbr'):
    """
    保存报价记录到数据库

    Args:
        enquiry_no: 询价单号
        details: 报价明细列表
        submit_result: 提交结果
        submit_time: 提交时间
        company: 组织代码，默认 fsbbr
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
            INSERT INTO qpl_quote_record (
                supplier_enquiry_no, supplier_demand_id, enquiry_item_id,
                item_oe, item_name, item_description, brand_id, brand_name,
                item_sell_price, delivery_aging, item_quality, parts_no,
                quote_status, submit_result, submit_time, company,
                created_time, vin_code, car_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            for detail in details:
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
                    submit_result,
                    submit_time,
                    company,
                    detail.get('created_time'),
                    detail.get('vin_code'),
                    detail.get('car_type')
                ))

            conn.commit()
            print(f"[报价保存][{company}] 成功保存 {len(details)} 条记录，询价单: {enquiry_no}")
    except Exception as e:
        print(f"[报价保存][{company}] 保存失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def process_and_save_quotes_for_company(company, begin_date=None, end_date=None):
    """
    处理指定组织的报价并保存结果
    
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
    
    success_count = 0
    fail_count = 0
    
    # 处理每个报价结果
    for result in results:
        if result['success']:
            # 提取明细并保存
            details = extract_quote_details(result['detail_data'])
            if details:
                save_quote_records(
                    enquiry_no=result['enquiry_no'],
                    details=details,
                    submit_result=result['message'],
                    submit_time=result['submit_time'],
                    company=company
                )
            success_count += 1
        else:
            fail_count += 1
    
    print(f"[报价服务][{company}] 任务完成 - 成功: {success_count}, 失败: {fail_count}")
    
    return {
        'company': company,
        'success_count': success_count,
        'fail_count': fail_count,
        'total': len(results)
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
        try:
            result = process_and_save_quotes_for_company(company, begin_date, end_date)
            all_results.append(result)
        except Exception as e:
            print(f"[报价服务][{company}] 处理失败: {e}")
            all_results.append({
                'company': company,
                'success_count': 0,
                'fail_count': 0,
                'total': 0,
                'error': str(e)
            })
    
    # 汇总统计
    total_success = sum(r.get('success_count', 0) for r in all_results)
    total_fail = sum(r.get('fail_count', 0) for r in all_results)
    
    print(f"\n[报价服务] ====== 所有组织报价任务完成 ======")
    print(f"[报价服务] 汇总结果: 成功 {total_success}, 失败 {total_fail}")
    
    return all_results
