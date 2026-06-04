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


def submit_quote(quote_request):
    """提交报价"""
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryEdit/submitSupplierEnquiry'
    resp = requests.post(url, headers=get_headers(), json=quote_request, timeout=30)
    return resp.json()


def main():
    """主流程"""
    today = datetime.now()
    begin_date = (today - timedelta(days=2)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    print(f"[汽配龙自动报价] 查询日期: {begin_date} 至 {end_date}")
    
    # 查询订单列表
    result = query_enquiry_list(begin_date, end_date)
    orders = result['data']
    
    # 去重订单号
    unique_enquiry_nos = set()
    for order in orders:
        unique_enquiry_nos.add(order.get('supplierEnquiryNo'))
    
    print(f"[汽配龙自动报价] 找到 {len(unique_enquiry_nos)} 个订单")
    
    # 遍历提交
    for enquiry_no in unique_enquiry_nos:
        detail = get_enquiry_detail(enquiry_no)
        detail_data = detail['data']
        
        # 跳过非全PART_QUOTE订单
        if not is_all_part_quote(detail_data):
            print(f"[汽配龙自动报价] 跳过: {enquiry_no}")
            continue
        
        print(f"[汽配龙自动报价] 提交: {enquiry_no}")
        quote_request = construct_quote_request(detail_data)
        submit_result = submit_quote(quote_request)
        print(f"[汽配龙自动报价] 结果: {submit_result.get('message')}")


if __name__ == '__main__':
    main()
