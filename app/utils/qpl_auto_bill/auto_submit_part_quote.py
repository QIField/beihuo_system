#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""自动提交部分报价订单"""

import sys
import os

# 添加当前目录到路径，支持相对导入
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from datetime import datetime, timedelta
from enquiry_api import query_enquiry_list, get_enquiry_detail
from quote_builder import is_all_part_quote, construct_quote_request
from qpl_config import BASE_URL, get_headers
import requests


def submit_quote(quote_request, company='fsbbr'):
    """
    提交报价
    
    Args:
        quote_request: 报价请求体
        company: 组织代码，默认fsbbr
    
    Returns:
        dict: 提交结果
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryEdit/submitSupplierEnquiry'
    resp = requests.post(url, headers=get_headers(company), json=quote_request, timeout=30)
    return resp.json()


def submit_all_quotes(begin_date=None, end_date=None, company='fsbbr'):
    """
    提交所有符合条件的报价（可复用版本）
    
    Args:
        begin_date: 开始日期，格式 'YYYY-MM-DD'，默认3天前
        end_date: 结束日期，格式 'YYYY-MM-DD'，默认今天
        company: 组织代码，默认fsbbr
    
    Returns:
        list: 报价结果列表，每个元素包含详细信息
    """
    if begin_date is None:
        begin_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"[汽配龙自动报价][{company}] 查询日期: {begin_date} 至 {end_date}")
    
    result = query_enquiry_list(begin_date, end_date, company=company)
    orders = result.get('data', [])
    
    unique_enquiry_nos = {order.get('supplierEnquiryNo') for order in orders if order.get('supplierEnquiryNo')}
    print(f"[汽配龙自动报价][{company}] 找到 {len(unique_enquiry_nos)} 个订单")
    
    results = []
    
    for enquiry_no in unique_enquiry_nos:
        detail = get_enquiry_detail(enquiry_no, company=company)
        detail_data = detail.get('data', {})
        
        if not is_all_part_quote(detail_data):
            print(f"[汽配龙自动报价][{company}] 跳过: {enquiry_no}")
            continue
        
        print(f"[汽配龙自动报价][{company}] 提交: {enquiry_no}")
        quote_request = construct_quote_request(detail_data)
        submit_result = submit_quote(quote_request, company=company)
        message = submit_result.get('message', '')
        print(f"[汽配龙自动报价][{company}] 结果: {message}")
        
        results.append({
            'enquiry_no': enquiry_no,
            'success': submit_result.get('success', False),
            'message': message,
            'detail_data': detail_data,
            'submit_time': datetime.now(),
            'company': company
        })
    
    return results


def main(company='fsbbr'):
    """独立脚本入口"""
    results = submit_all_quotes(company=company)
    print(f"[汽配龙自动报价][{company}] 任务完成，共处理 {len(results)} 个订单")


if __name__ == '__main__':
    # 如果命令行参数指定了组织，则使用指定的组织
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()