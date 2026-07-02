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
from qpl_config import BASE_URL, get_headers, handle_qpl_response


def query_enquiry_list(begin_date, end_date, page_num=1, page_size=100, company='fsbbr'):
    """
    查询询价单列表
    
    Args:
        begin_date: 开始日期
        end_date: 结束日期
        page_num: 页码，默认1
        page_size: 每页数量，默认100
        company: 组织代码，默认fsbbr
    
    Returns:
        dict: API响应结果
    """
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
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def get_enquiry_detail(supplier_enquiry_no, company='fsbbr'):
    """
    获取询价单详情
    
    Args:
        supplier_enquiry_no: 询价单号
        company: 组织代码，默认fsbbr
    
    Returns:
        dict: API响应结果
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierDemandDetail/getSupplierEnquiryDetail'
    payload = {"supplierEnquiryNo": supplier_enquiry_no}
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def get_adapt_product_brand(supplier_enquiry_item_id, supplier_enquiry_no, company='fsbbr'):
    """
    获取适配品牌列表
    
    Args:
        supplier_enquiry_item_id: 询价项目ID
        supplier_enquiry_no: 询价单号
        company: 组织代码，默认fsbbr
    
    Returns:
        dict: API响应结果
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryBrand/listAdaptProductBrand'
    payload = {
        "supplierEnquiryItemId": supplier_enquiry_item_id,
        "supplierEnquiryNo": supplier_enquiry_no
    }
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def price_check(price_check_req_list, tid, car_brand, supplier_enquiry_no, company='fsbbr'):
    """
    校验报价价格

    Args:
        price_check_req_list: 价格校验请求列表
        tid: 询价单 tid
        car_brand: 车辆品牌
        supplier_enquiry_no: 询价单号
        company: 组织代码，默认fsbbr

    Returns:
        dict: API响应结果
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryEdit/priceCheck'
    payload = {
        "priceCheckReqList": price_check_req_list,
        "tid": tid,
        "carBrand": car_brand,
        "supplierEnquiryNo": supplier_enquiry_no,
        "channel": "S_STATION"
    }
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def get_pickup_way_and_distance(shop_uid, supplier_enquiry_no, tuhu_supplier_id=None, company='fsbbr'):
    """
    获取供应商取货方式和距离

    Args:
        shop_uid: 门店UID (从详情接口 shopUid 获取)
        supplier_enquiry_no: 询价单号
        tuhu_supplier_id: 途虎供应商ID (从详情接口 data.tuhuSupplierId 获取，传入后可获取完整地址)
        company: 组织代码

    Returns:
        dict: API响应结果
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryEdit/getSupplierPickUpWayAndDistance'
    payload = {
        "shopUid": shop_uid,
        "supplierEnquiryNo": supplier_enquiry_no
    }
    if tuhu_supplier_id is not None:
        payload["tuhuSupplierId"] = tuhu_supplier_id
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def cannot_quote(supplier_enquiry_no, item_id_list, close_reason=16, close_remarks='', company='fsbbr'):
    """
    标记询价单项目为无法报价

    Args:
        supplier_enquiry_no: 询价单号
        item_id_list: 询价项目ID列表
        close_reason: 关闭原因，默认16
        close_remarks: 关闭备注，默认空字符串
        company: 组织代码

    Returns:
        dict: API响应结果
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryEdit/cannotQuote'
    payload = {
        "supplierEnquireNo": supplier_enquiry_no,
        "supplierEnquiryItemIdList": item_id_list,
        "closeRemarks": close_remarks,
        "closeReason": close_reason
    }
    resp = requests.post(url, headers=get_headers(company), json=payload, timeout=30)
    return handle_qpl_response(resp, company)


def extract_pickup_info(pickup_api_result):
    """
    从取货方式接口响应中提取报价体需要的字段

    Args:
        pickup_api_result: get_pickup_way_and_distance() 的返回

    Returns:
        dict: {pickUpWay, pickUpWayStr, deliveryAddress}
    """
    if not pickup_api_result or pickup_api_result.get('code') != 10000:
        return {"pickUpWay": None, "pickUpWayStr": None, "deliveryAddress": ""}

    data = pickup_api_result.get('data', {})

    # 取默认取货方式
    pick_up_way = None
    pick_up_way_str = None
    pickup_info = data.get('supplierPropertyPickUpWayInfo', {})
    if pickup_info:
        default_way = pickup_info.get('defaultPickUpWay', {})
        if default_way:
            pick_up_way = default_way.get('pickUpWay')
            pick_up_way_str = default_way.get('pickUpWayStr')

    # 收货地址使用 shopProvinceName + shopCityName 拼接（更可靠）
    province = data.get('shopProvinceName') or ''
    city = data.get('shopCityName') or ''
    delivery_address = f"{province} {city}".strip()

    return {
        "pickUpWay": pick_up_way,
        "pickUpWayStr": pick_up_way_str,
        "deliveryAddress": delivery_address
    }