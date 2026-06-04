#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""询价单API"""

import sys
import os

# 添加当前目录到路径，支持相对导入
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import requests
from qpl_config import BASE_URL, get_headers


def query_enquiry_list(begin_date, end_date, page_num=1, page_size=100):
    """查询询价单列表"""
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryList/querySupplierEnquiryList'
    payload = {
        "closeLabel": None,
        "qplEnquiryNo": None,
        "supplierEnquiryNo": None,
        "supplierEnquiryStatus": 0,
        "traderId": None,
        "vinCode": None,
        "tuhuSupplierId": None,
        "tuhuSupplierIdList": [],
        "pageNum": page_num,
        "pageSize": page_size,
        "beginDate": begin_date,
        "endDate": end_date
    }
    resp = requests.post(url, headers=get_headers(), json=payload, timeout=30)
    return resp.json()


def get_enquiry_detail(supplier_enquiry_no):
    """获取询价单详情"""
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierDemandDetail/getSupplierEnquiryDetail'
    payload = {"supplierEnquiryNo": supplier_enquiry_no}
    resp = requests.post(url, headers=get_headers(), json=payload, timeout=30)
    return resp.json()
