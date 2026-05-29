#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汽配龙询价单查询脚本
"""

import requests


URL = 'https://qpl-gateway.qipeilong.cn/qpl-supplier-enquiry/supplierEnquiryList/querySupplierEnquiryList'

# 从数据库复制的token（如需更新请替换）
QPL_AUTH_TOKEN = '7bpO8+6hUFlUrbfXPkct6Y7ygu1Fz3kVIxpz1ex87hdnTt6pp443CCfx2JWuUF7egscmbF7CxyB9wlC5U8kQsaXb525ubD733yXjhQuEjAMXlCMMz2q9r0sJLwHbVrBLrBFrhFtBfVpPNBKEe5C9s5dIHHOw8WXc/Zti59H+Qar3t46c78lqJR4Mk9joU4H5VRFUszyapwN0JPkixxk2ajse2nKOTlGFrl2vJZ+LyFBCNbHuUnDYNF70Y+SH1fMfDJxea9mRe1HMebUHQlUFrzJPfJnHaQh2dfoNCY89CE3V5WWcJhVAzH6phQ5KvEJcKgiaBPqsugMN33tdSYntBd4eEEPGa7PsoYX5lES/Hlqt31QkWndEOYmyLkyUjEA0VX8n6OBEIF8KpmnWZuQDjA=='


def query_supplier_enquiry_list(begin_date="2026-04-22", end_date="2026-05-22", page_num=1, page_size=10):
    """
    查询汽配龙询价单列表
    
    Args:
        begin_date: 开始日期，默认2026-04-22
        end_date: 结束日期，默认2026-05-22
        page_num: 页码，默认1
        page_size: 每页条数，默认10
    
    Returns:
        dict: API响应结果
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': QPL_AUTH_TOKEN,
        'authtype': 'qpl_merchant',
        'origin': 'https://s.qipeilong.cn',
        'referer': 'https://s.qipeilong.cn/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
        'qpl-info': 'QPL/WEB-BIZ',
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'
    }
    
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
    
    response = requests.post(URL, headers=headers, json=payload, timeout=30)
    return response.json()


def process_enquiry_list(result):
    """
    处理询价单列表，提取所需字段
    
    Args:
        result: API响应结果
    
    Returns:
        list: 处理后的数据列表
    """
    processed_data = []
    
    if not result.get('success') or not result.get('data'):
        print(f"请求失败: {result.get('message', '未知错误')}")
        return processed_data
    
    for order in result['data']:
        supplier_enquiry_no = order.get('supplierEnquiryNo')
        item_list = order.get('supplierEnquiryItemList', [])
        
        for item in item_list:
            processed_data.append({
                'supplierEnquiryNo': supplier_enquiry_no,
                'enquiryItemId': item.get('enquiryItemId'),
                'autoQuotationTag': item.get('autoQuotationTag'),
                'quoteStatusStr': item.get('quoteStatusStr')
            })
    
    return processed_data


def get_adapt_product_brand(supplier_enquiry_item_id, supplier_enquiry_no):
    """
    获取适配产品品牌列表
    
    Args:
        supplier_enquiry_item_id: 询价产品ID
        supplier_enquiry_no: 询价单号
    
    Returns:
        dict: API响应结果
    """
    url = 'https://qpl-gateway.qipeilong.cn/qpl-supplier-enquiry/supplierEnquiryBrand/listAdaptProductBrand'
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': QPL_AUTH_TOKEN,
        'authtype': 'qpl_merchant',
        'origin': 'https://s.qipeilong.cn',
        'referer': 'https://s.qipeilong.cn/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
        'qpl-info': 'QPL/WEB-BIZ',
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'
    }
    
    payload = {
        "supplierEnquiryItemId": supplier_enquiry_item_id,
        "supplierEnquiryNo": supplier_enquiry_no
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    return response.json()


if __name__ == '__main__':
    # 手动运行示例
    result = query_supplier_enquiry_list()
    
    # 处理并打印结果
    data = process_enquiry_list(result)
    print(f"\n共获取 {len(data)} 条产品记录:\n")
    for item in data:
        print(f"询价单号: {item['supplierEnquiryNo']}")
        print(f"  产品ID: {item['enquiryItemId']}")
        print(f"  自动报价标签: {item['autoQuotationTag']}")
        print(f"  报价状态: {item['quoteStatusStr']}")
        print("-" * 50)
    
    # 获取第一条产品的适配品牌列表
    if data:
        first_item = data[0]
        print(f"\n\n正在获取第一条产品的适配品牌列表...")
        print(f"询价单号: {first_item['supplierEnquiryNo']}")
        print(f"产品ID: {first_item['enquiryItemId']}")
        
        brand_result = get_adapt_product_brand(
            first_item['enquiryItemId'],
            first_item['supplierEnquiryNo']
        )
        print(f"\n适配品牌列表响应:")
        print(brand_result)
