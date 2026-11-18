#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价 · 新版询价单 API（PAGE_QUOTE 灰度全量流程）

与新页面 HAR 对齐的差异点：
1. 详情接口支持 PAGE 分页（queryType=PAGE, pageNo/pageSize），大批量单自动翻页取全
2. 提交接口顶层新增 quoteType=PAGE_QUOTE（pickUpWay 三字段实测必传，见 submit_enquiry_page）
3. priceCheck 请求项新增 brandOwnerBizType/quoteTaxRate，uid 传时间戳
4. 列表接口对齐网页参数：灰度订单 + 仅含待报价明细（见 list_enquiry_orders）
"""

import time

import requests

from app.utils.qpl_auto_bill.qpl_config import BASE_URL, get_headers, handle_qpl_response
from app.services.qpl_auto_quote.constants import (
    DETAIL_PAGE_SIZE,
    DETAIL_QUERY_TYPE_PAGE,
    QUOTE_TYPE_PAGE_QUOTE,
)

# 翻页安全上限，防止异常响应导致死循环
MAX_DETAIL_PAGES = 50


def get_enquiry_detail_page(supplier_enquiry_no, page_no, page_size=DETAIL_PAGE_SIZE,
                            company='fsbbr'):
    """
    获取询价单详情（单页）。

    Returns:
        dict: API 响应（data.supplierEnquiryDemandList 为本页明细）
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierDemandDetail/getSupplierEnquiryDetail'
    payload = {
        "supplierEnquiryNo": supplier_enquiry_no,
        "queryType": DETAIL_QUERY_TYPE_PAGE,
        "pageNo": page_no,
        "pageSize": page_size,
    }
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def get_enquiry_detail_all(supplier_enquiry_no, company='fsbbr',
                           page_size=DETAIL_PAGE_SIZE):
    """
    获取询价单详情全量（PAGE 分页自动翻页，按 supplierDemandId 合并明细）。

    Returns:
        dict | None: 合并后的详情（顶层取首页字段 + 全量 supplierEnquiryDemandList），
                     接口失败返回 None
    """
    merged = None
    demand_map = {}
    for page_no in range(1, MAX_DETAIL_PAGES + 1):
        result = get_enquiry_detail_page(supplier_enquiry_no, page_no, page_size, company)
        if not result or result.get('code') != 10000:
            return None if merged is None else merged

        data = result.get('data') or {}
        if merged is None:
            merged = dict(data)
            merged['supplierEnquiryDemandList'] = []

        for demand in data.get('supplierEnquiryDemandList') or []:
            demand_id = demand.get('supplerDemandId')
            if demand_id in demand_map:
                demand_map[demand_id]['supplierEnquiryItemList'].extend(
                    demand.get('supplierEnquiryItemList') or [])
            else:
                demand_copy = dict(demand)
                demand_copy['supplierEnquiryItemList'] = list(
                    demand.get('supplierEnquiryItemList') or [])
                demand_map[demand_id] = demand_copy
                merged['supplierEnquiryDemandList'].append(demand_copy)

        total_items = sum(len(d['supplierEnquiryItemList']) for d in demand_map.values())
        if total_items < page_size * page_no:
            break
    return merged


def price_check(price_check_req_list, tid, car_brand, supplier_enquiry_no, company='fsbbr'):
    """
    价格校验（请求外层与新页面一致）。
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryEdit/priceCheck'
    payload = {
        "priceCheckReqList": price_check_req_list,
        "tid": tid,
        "carBrand": car_brand,
        "supplierEnquiryNo": supplier_enquiry_no,
        "channel": "S_STATION",
    }
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def list_enquiry_orders(begin_date, end_date, page_num=1, page_size=100, company='fsbbr'):
    """
    拉取询价单列表（网页版参数，实测验证）。

    与旧 query_enquiry_list 差异（依据网页请求体）：
    - multiQuoteGray=true：只拉灰度新页面订单（1 个月窗口 11 单 vs 100 单）
    - hasWaitingQuoteItem=1（Integer，传 true 会 400）：只拉含待报价明细的订单
      （叠加后 1 个月窗口仅 6 单，全部是真正需要报价的单）
    - supplierEnquiryStatus=0：待报价标签
    - 时间范围不能超过 1 个月
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryList/querySupplierEnquiryList'
    payload = {
        "closeLabel": None, "qplEnquiryNo": None, "supplierEnquiryNo": None,
        "supplierEnquiryStatus": 0, "traderId": None, "vinCode": None,
        "tuhuSupplierId": None, "tuhuSupplierIdList": [],
        "pageNum": page_num, "pageSize": page_size,
        "beginDate": begin_date, "endDate": end_date,
        "acceptStatus": None, "onlyMine": None,
        "hasWaitingQuoteItem": 1, "onlyManualQuote": None,
        "multiQuoteGray": True,
    }
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def submit_enquiry_page(request, supplier_enquiry_no, company='fsbbr'):
    """
    提交报价（PAGE_QUOTE 格式）。

    Args:
        request: build_submit_request 构造的完整提交体
                 （含 quoteType / pickUpWay / pickUpWayStr / deliveryAddress / demandList；
                 实测接口校验"配送方式为空"，顶层配送字段必须透传）
        supplier_enquiry_no: 询价单号
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryEdit/submitSupplierEnquiry'
    payload = {
        "channel": "S_STATION",
        "supplierEnquiryNo": supplier_enquiry_no,
        "quoteType": QUOTE_TYPE_PAGE_QUOTE,
        "pickUpWay": request.get('pickUpWay'),
        "pickUpWayStr": request.get('pickUpWayStr'),
        "deliveryAddress": request.get('deliveryAddress'),
        "demandList": request.get('demandList'),
    }
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def query_quote_product_info(supplier_enquiry_no, company='fsbbr'):
    """
    查询含税配置（轻量接口，返回 quoteTaxType/quoteTaxRate；自动任务可选调用）。
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiry/queryQuoteProductInfo'
    payload = {"supplierEnquiryNo": supplier_enquiry_no, "pid": "", "regionalDistributionType": ""}
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def build_price_check_uid():
    """priceCheck 请求项 uid：时间戳（新页面行为）"""
    return int(time.time() * 1000)
