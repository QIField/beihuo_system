#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汽配龙询价单查询脚本 - 交互式版本
"""

import requests
import json
from datetime import datetime


URL = 'https://qpl-gateway.qipeilong.cn/qpl-supplier-enquiry/supplierEnquiryList/querySupplierEnquiryList'

# 从数据库复制的token（如需更新请替换）
QPL_AUTH_TOKEN = '7bpO8+6hUFlUrbfXPkct6Y7ygu1Fz3kVIxpz1ex87hdnTt6pp443CCfx2JWuUF7egscmbF7CxyB9wlC5U8kQsaXb525ubD733yXjhQuEjAMXlCMMz2q9r0sJLwHbVrBLrBFrhFtBfVpPNBKEe5C9s5dIHHOw8WXc/Zti59H+Qar3t46c78lqJR4Mk9joU4H5VRFUszyapwN0JPkixxk2ajse2nKOTlGFrl2vJZ+LyFBCNbHuUnDYNF70Y+SH1fMfDJxea9mRe1HMebUHQlUFrzJPfJnHaQh2dfoNCY89CE3V5WWcJhVAzH6phQ5KvEJcKgiaBPqsugMN33tdSYntBd4eEEPGa7PsoYX5lES/Hlqt31QkWndEOYmyLkyUjEA0VX8n6OBEIF8KpmnWZuQDjA=='


def get_today_date():
    """获取当天日期字符串"""
    return datetime.now().strftime('%Y-%m-%d')


def query_supplier_enquiry_list(begin_date=None, end_date=None, page_num=1, page_size=100):
    """
    查询汽配龙询价单列表
    """
    # 如果没有提供日期，使用当天日期
    if begin_date is None:
        begin_date = get_today_date()
    if end_date is None:
        end_date = get_today_date()

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


def get_adapt_product_brand(supplier_enquiry_item_id, supplier_enquiry_no):
    """
    获取适配产品品牌列表
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


def get_supplier_enquiry_detail(supplier_enquiry_no):
    """
    获取询价单详情
    """
    url = 'https://qpl-gateway.qipeilong.cn/qpl-supplier-enquiry/supplierDemandDetail/getSupplierEnquiryDetail'

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
        "supplierEnquiryNo": supplier_enquiry_no
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    return response.json()


def submit_supplier_enquiry(quote_request):
    """
    提交供应商询价报价
    """
    url = 'https://qpl-gateway.qipeilong.cn/qpl-supplier-enquiry/supplierEnquiryEdit/submitSupplierEnquiry'

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

    response = requests.post(url, headers=headers, json=quote_request, timeout=30)
    return response.json()


def query_crm_product_list(number_list):
    """
    查询CRM产品列表

    Args:
        number_list: OE号码列表，如 ["11428683206", "11428642289"]

    Returns:
        dict: CRM响应结果
    """
    url = 'https://crm.gzbbr.com/api/Product.Product/list'

    # CRM Cookie（临时使用）
    crm_cookie = 'initCompany_id=2; brand_search=1; bbrToken=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJjbGllbnQueGhhZG1pbiIsImF1ZCI6InNlcnZlci54aGFkbWluIiwiaWF0IjoxNzc4NjYxOTYwLCJleHAiOjE3ODEyNTM5NjAsInVpZCI6IjYzNCIsIm5hbWUiOiJcdTVlYjdcdTRmMWZcdTYyNmMiLCJhZG1pbl9zd2l0Y2hfbG9naW4iOiIifQ.hXJyjGlTLDQHwR-bqpe-y_4JTZDEMF7xMKirDeySOQ8; bbr_name=%E5%BA%B7%E4%BC%9F%E6%89%AC; bbrUser_id=634; initUser_id=634; bbr_company_id=2; company_system=1; is_early_warning=0; is_print_bold=1; is_switch_company=0; is_performance=1; is_supervisor=1; company_is_help=1; unsalable=0; defective_product_return_rate=1; bbr_company_name=%E4%BD%9B%E5%B1%B1%E5%B8%82%E5%B7%B4%E5%8D%9A%E7%91%9E%E6%B1%BD%E8%BD%A6%E9%9B%B6%E9%85%8D%E4%BB%B6%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8; super=1; top_company_name=%E4%BD%9B%E5%B1%B1%E5%B8%82%E5%B7%B4%E5%8D%9A%E7%91%9E%E6%B1%BD%E8%BD%A6%E9%9B%B6%E9%85%8D%E4%BB%B6%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8; category=1; is_fry=0; PHPSESSID=2ebb6ade7b379c6421d2d64ff83630a5'

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Cookie': crm_cookie
    }

    payload = {
        "numberlist": number_list
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    return response.json()


def filter_available_brands_with_crm(adapt_brand_list, detail_data):
    """
    使用CRM接口筛选可用的品牌
    提取规则：从productList层级提取brandName和productOeList，一个品牌+一个OE=一条记录

    Args:
        adapt_brand_list: 适配品牌列表响应
        detail_data: 询价单详情数据

    Returns:
        list: 可用的品牌名称列表（去重）
    """
    # 获取已报价的品牌（部分报价的产品）
    quoted_brands = set()
    demand_list = detail_data.get('supplierEnquiryDemandList', [])
    for demand in demand_list:
        for item in demand.get('supplierEnquiryItemList', []):
            if item.get('quoteStatus') == 'PART_QUOTE':
                for quote in item.get('supplierQuoteItemList', []):
                    brand_name = quote.get('brandName', '')
                    if brand_name:
                        quoted_brands.add(brand_name)

    print(f"\n已报价品牌（排除）: {quoted_brands}")

    # 整理待查询的品牌和OE：从productList层级提取
    brand_oe_pairs = set()  # (brandName, OE) 元组集合，自动去重
    all_oes = set()         # 所有唯一OE

    brand_list = adapt_brand_list.get('data', {}).get('brandList', [])
    for brand in brand_list:
        products = brand.get('productList', [])

        for product in products:
            # 从productList层级提取brandName
            product_brand_name = product.get('brandName', '')

            # 排除已报价的品牌
            if product_brand_name in quoted_brands:
                continue

            # 提取productOeList中的所有OE
            product_oes = product.get('productOeList', [])
            for oe in product_oes:
                if oe:  # 确保OE不为空
                    brand_oe_pairs.add((product_brand_name, oe))
                    all_oes.add(oe)

    if not all_oes:
        print("没有待查询的OE号码")
        return []

    # 按品牌分组显示
    brand_oe_map = {}
    for brand_name, oe in brand_oe_pairs:
        if brand_name not in brand_oe_map:
            brand_oe_map[brand_name] = []
        brand_oe_map[brand_name].append(oe)

    print(f"\n待查询的品牌+OE组合:")
    for brand_name, oe_list in brand_oe_map.items():
        print(f"  {brand_name}: {oe_list}")

    print(f"\n待查询的OE号码（去重）: {all_oes}")

    # 查询CRM接口
    oe_list = list(all_oes)
    print(f"\n正在查询CRM接口，OE数量: {len(oe_list)}")
    crm_result = query_crm_product_list(oe_list)

    if crm_result.get('status') != 200:
        print(f"CRM查询失败: {crm_result.get('msg', '未知错误')}")
        return []

    # 获取CRM返回的品牌
    crm_brands = set()
    crm_data = crm_result.get('data', {}).get('data', [])
    for item in crm_data:
        for child in item.get('child', []):
            brand_name = child.get('brand_name', '')
            if brand_name:
                crm_brands.add(brand_name)

    print(f"\nCRM返回的品牌: {crm_brands}")

    # 匹配品牌：检查brand_oe_pairs中的品牌是否在CRM中
    available_brands = set()
    for brand_name, oe in brand_oe_pairs:
        # 简化匹配：检查brand_name是否包含在crm_brands中
        for crm_brand in crm_brands:
            if brand_name in crm_brand or crm_brand in brand_name:
                available_brands.add(brand_name)
                break

    available_brands = list(available_brands)
    print(f"\n可用的品牌: {available_brands}")
    return available_brands


def construct_quote_item(quote_info):
    """
    构造单个报价项
    """
    quote_extra_info = quote_info.get('quoteExtraInfo', {})

    # 处理价格：转换为整数
    item_sell_price = quote_info.get('itemSellPrice')
    if item_sell_price is not None:
        item_sell_price = int(item_sell_price)

    return {
        "addOeQuoteInfo": None,
        "brandId": str(quote_info.get('brandId')),
        "brandName": quote_info.get('brandName'),
        "deliveryAging": quote_info.get('deliveryAging', 1),
        "prepareGoodTimespan": None,
        "prepareGoodTimespanUnit": "",
        "itemQuality": quote_info.get('itemQuality'),
        "itemRemark": quote_info.get('itemRemark'),
        "itemSellPrice": item_sell_price,
        "partsNo": quote_info.get('partsNo'),
        "quoteImageList": None,
        "quoteMethod": "AUTO_QUOTE",
        "supplierQuoteItemId": quote_info.get('supplierQuoteItemId'),
        "standardName": quote_info.get('standardItemName') or quote_info.get('displaceProductName'),
        "supplierQuoteProductId": "",
        "pid": quote_info.get('pid'),
        "transferDay": "",
        "itemPerhapsReplaceOe": quote_info.get('itemPerhapsReplaceOe'),
        "brandType": quote_info.get('brandTypeEnum'),
        "qualityType": quote_info.get('qualityTypeCode'),
        "qualityTypeDesc": quote_info.get('qualityTypeDesc'),
        "qualityTypeId": str(quote_info.get('qualityTypeId')),
        "quoteTaxType": "INCLUSIVE",
        "packageAmount": None,
        "packageUnit": "",
        "quoteExtraInfoVo": {
            "supplierQualification": quote_extra_info.get('supplierQualification'),
            "supplierQualificationAuthorizedType": quote_extra_info.get('supplierQualificationAuthorizedType'),
            "supplierProductSrc": "ERP_SUPPLIER",
            "supplierProductId": quote_extra_info.get('supplierProductId'),
            "supplierERPOriginalOE": quote_extra_info.get('supplierERPOriginalOE'),
            "regionalDistributionType": None,
            "chainType": None,
            "regionalPriceToShow": None,
            "regionalDistributionSellPriceCode": None,
            "brandOwnerId": None,
            "chainId": None,
            "regionalBrandVersion": None,
            "regionalProductVersion": None,
            "sameProductPrice": None,
            "regionalDistributionSellPrice": None,
            "needApprove": False,
            "addOeQuote": False,
            "supplierOe": None,
            "selectTempProductOe": False,
            "tempProductOe": None,
            "imgList": None,
            "desc": None,
            "limitPrice": None,
            "qualityTypeId": str(quote_info.get('qualityTypeId')),
            "qualityType": None,
            "originTire": None,
            "quoteTaxType": "INCLUSIVE",
            "quoteTaxRate": None
        },
        "priceCheckSnapshot": None,
        "quoteItemSalesAttribute": None,
        "quoteStatus": "QUOTED"
    }


def construct_quote_item_from_brand(brand, product, item_sell_price, prepare_good_timespan):
    """
    从适配品牌构造单个报价项（待报价产品使用）
    """
    return {
        "addOeQuoteInfo": None,
        "brandId": str(brand.get('brandId')),
        "brandName": brand.get('brandName'),
        "deliveryAging": prepare_good_timespan,
        "prepareGoodTimespan": prepare_good_timespan,
        "prepareGoodTimespanUnit": "DAY",
        "itemQuality": product.get('quality'),
        "itemRemark": "",
        "itemSellPrice": item_sell_price,
        "partsNo": product.get('partNo'),
        "quoteImageList": product.get('quoteImageList'),
        "quoteMethod": "AUTO_QUOTE",
        "supplierQuoteItemId": None,
        "standardName": product.get('displaceProductName'),
        "supplierQuoteProductId": "",
        "pid": product.get('pid'),
        "transferDay": "",
        "itemPerhapsReplaceOe": product.get('itemPerhapsReplaceOe'),
        "brandType": brand.get('brandType'),
        "qualityType": product.get('qualityTypeCode'),
        "qualityTypeDesc": product.get('qualityTypeDesc'),
        "qualityTypeId": str(product.get('qualityTypeId')),
        "quoteTaxType": "INCLUSIVE",
        "packageAmount": None,
        "packageUnit": "",
        "quoteExtraInfoVo": {
            "originTire": product.get('originTire')
        },
        "priceCheckSnapshot": None,
        "quoteItemSalesAttribute": None,
        "quoteStatus": "QUOTED"
    }


def process_waiting_quote_item(item, enquiry_no, detail_data):
    """
    处理待报价产品：直接显示适配品牌让用户选择
    """
    enquiry_item_id = item.get('enquiryItemId')
    item_name = item.get('itemName')

    print(f"\n产品 [{item_name}] 待报价，正在获取适配品牌...")

    brand_result = get_adapt_product_brand(enquiry_item_id, enquiry_no)
    if brand_result.get('code') != 10000 or not brand_result.get('data'):
        print(f"  获取适配品牌列表失败")
        return None

    # 获取所有适配品牌（暂时跳过CRM筛选）
    brand_list = brand_result['data'].get('brandList', [])

    if not brand_list:
        print(f"  没有可用的适配品牌")
        return None

    print(f"\n  适配品牌列表:")
    for idx, brand in enumerate(brand_list, 1):
        print(f"    [{idx}] {brand.get('brandName')} (ID: {brand.get('brandId')})")

    # 用户选择品牌
    while True:
        try:
            choice = input(f"\n  请选择品牌序号 (1-{len(brand_list)}): ").strip()
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(brand_list):
                selected_brand = brand_list[choice_idx]
                products = selected_brand.get('productList', [])
                if products:
                    selected_product = products[0]
                    print(f"  已选择品牌: {selected_brand.get('brandName')}")

                    # 用户输入价格
                    while True:
                        try:
                            price_input = input("  请输入销售价格: ").strip()
                            item_sell_price = int(float(price_input))
                            if item_sell_price > 0:
                                break
                            else:
                                print("  价格必须大于0")
                        except ValueError:
                            print("  请输入有效的数字")

                    # 用户输入备货时效
                    while True:
                        try:
                            timespan_input = input("  请输入备货时效(天): ").strip()
                            prepare_good_timespan = int(timespan_input)
                            if prepare_good_timespan > 0:
                                break
                            else:
                                print("  备货时效必须大于0")
                        except ValueError:
                            print("  请输入有效的数字")

                    return construct_quote_item_from_brand(selected_brand, selected_product, item_sell_price, prepare_good_timespan)
                else:
                    print(f"  该品牌下没有产品")
                    return None
            else:
                print(f"  请输入 1 到 {len(brand_list)} 之间的数字")
        except ValueError:
            print("  请输入有效的数字")


def construct_mixed_quote_request(detail_data, enquiry_no):
    """
    构造混合报价请求体（部分报价 + 待报价）
    """
    demand_list = detail_data.get('supplierEnquiryDemandList', [])
    constructed_demand_list = []

    for demand in demand_list:
        suppler_demand_id = demand.get('supplerDemandId')
        item_list = demand.get('supplierEnquiryItemList', [])

        enquiry_item_list = []
        for item in item_list:
            enquiry_item_id = item.get('enquiryItemId')
            item_oe = item.get('itemOe')
            add_item_oe = item.get('addItemOe', '')
            item_description = item.get('itemDescription')
            item_name = item.get('itemName')
            quote_status = item.get('quoteStatus')

            quote_item_list = []

            if quote_status == 'PART_QUOTE':
                # 部分报价：使用已有报价信息（所有品牌）
                print(f"\n产品 [{item_name}] 部分报价，使用已有品牌...")
                supplier_quote_list = item.get('supplierQuoteItemList', [])
                for quote_info in supplier_quote_list:
                    quote_item = construct_quote_item(quote_info)
                    quote_item_list.append(quote_item)
                print(f"  已添加 {len(quote_item_list)} 个品牌")

            elif quote_status == 'WAITING_QUOTE':
                # 待报价：使用CRM筛选可用品牌并让用户选择
                quote_item = process_waiting_quote_item(item, enquiry_no, detail_data)
                if quote_item:
                    quote_item_list.append(quote_item)

            if quote_item_list:
                enquiry_item = {
                    "addItemOe": add_item_oe,
                    "itemDescription": item_description,
                    "itemOe": item_oe,
                    "supplierEnquiryItemId": enquiry_item_id,
                    "quoteItemList": quote_item_list,
                    "itemName": item_name,
                    "closeReason": item.get('closeReason') or "",
                    "closeRemarks": item.get('closeRemarks') or "",
                    "quoteStatus": quote_status
                }
                enquiry_item_list.append(enquiry_item)

        if enquiry_item_list:
            demand_item = {
                "supplierDemandId": suppler_demand_id,
                "enquiryItemList": enquiry_item_list
            }
            constructed_demand_list.append(demand_item)

    if not constructed_demand_list:
        return None

    return {
        "channel": "S_STATION",
        "demandList": constructed_demand_list,
        "supplierEnquiryNo": detail_data.get('supplierEnquiryNo')
    }


def main():
    """交互式主流程"""
    print("=" * 60)
    print("汽配龙询价单报价请求体构造工具")
    print("=" * 60)

    # 步骤1: 获取所有订单
    print("\n【步骤1】正在获取询价单列表...")
    result = query_supplier_enquiry_list()

    if not result.get('success') or not result.get('data'):
        print(f"获取询价单列表失败: {result.get('message', '未知错误')}")
        return

    orders = result['data']
    if not orders:
        print("没有找到任何询价单")
        return

    # 去重并整理订单
    unique_orders = {}
    for order in orders:
        enquiry_no = order.get('supplierEnquiryNo')
        if enquiry_no not in unique_orders:
            unique_orders[enquiry_no] = {
                'enquiry_no': enquiry_no,
                'shop_name': order.get('shopName', '未知店铺'),
                'car_type': order.get('carType5', '未知车型'),
                'item_count': 0,
                'items': []
            }
        unique_orders[enquiry_no]['item_count'] += len(order.get('supplierEnquiryItemList', []))
        unique_orders[enquiry_no]['items'].extend(order.get('supplierEnquiryItemList', []))

    order_list = list(unique_orders.values())

    print(f"\n找到 {len(order_list)} 个询价单:\n")

    for idx, order in enumerate(order_list, 1):
        shop_name = order['shop_name'][:28] if len(order['shop_name']) > 28 else order['shop_name']
        car_type = order['car_type'][:38] if len(order['car_type']) > 38 else order['car_type']

        print(f"【{idx}】 询价单号: {order['enquiry_no']}")
        print(f"    店铺: {shop_name}")
        print(f"    车型: {car_type}")
        print(f"    产品列表 ({order['item_count']}个):")

        for item_idx, item in enumerate(order['items'], 1):
            item_name = item.get('itemName', '未知产品')
            quote_status = item.get('quoteStatusStr', '未知状态')
            auto_tag = item.get('autoQuotationTag', '')
            auto_str = f" [{auto_tag}]" if auto_tag else ""
            print(f"      [{item_idx}] {item_name} - {quote_status}{auto_str}")

        print("-" * 80)

    # 步骤2: 用户选择订单
    print("\n" + "=" * 60)
    while True:
        try:
            choice = input(f"\n请选择要处理的订单序号 (1-{len(order_list)}): ").strip()
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(order_list):
                selected_order = order_list[choice_idx]
                break
            else:
                print(f"请输入 1 到 {len(order_list)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")

    enquiry_no = selected_order['enquiry_no']
    print(f"\n已选择订单: {enquiry_no}")
    print(f"店铺: {selected_order['shop_name']}")
    print(f"车型: {selected_order['car_type']}")

    # 步骤3: 获取订单详情
    print("\n【步骤2】正在获取订单详情...")
    detail_result = get_supplier_enquiry_detail(enquiry_no)

    if not detail_result.get('success') or not detail_result.get('data'):
        print(f"获取订单详情失败: {detail_result.get('message', '未知错误')}")
        return

    detail_data = detail_result['data']

    # 步骤4: 构造混合报价请求体
    print("\n【步骤3】构造报价请求体...")
    quote_request = construct_mixed_quote_request(detail_data, enquiry_no)

    # 步骤5: 展示选择的品牌并确认
    if quote_request:
        print("\n" + "=" * 60)
        print("【报价预览】")
        print("=" * 60)

        # 展示每个产品的报价品牌
        for demand in quote_request.get('demandList', []):
            for item in demand.get('enquiryItemList', []):
                item_name = item.get('itemName', '未知产品')
                quote_status = item.get('quoteStatus', '')
                print(f"\n产品: {item_name} ({quote_status})")
                print("  报价品牌:")
                for idx, quote in enumerate(item.get('quoteItemList', []), 1):
                    brand_name = quote.get('brandName', '未知品牌')
                    price = quote.get('itemSellPrice', '未设置')
                    print(f"    [{idx}] {brand_name} - 价格: {price}")

        # 检查是否包含WAITING_QUOTE产品
        has_waiting_quote = False
        for demand in quote_request.get('demandList', []):
            for item in demand.get('enquiryItemList', []):
                if item.get('quoteStatus') == 'WAITING_QUOTE':
                    has_waiting_quote = True
                    break
            if has_waiting_quote:
                break

        # 展示完整请求体
        print("\n" + "=" * 60)
        print("【完整请求体预览】")
        print("=" * 60)
        print(json.dumps(quote_request, ensure_ascii=False, indent=2))

        print("\n" + "=" * 60)
        print("请求体已生成，请查看上方JSON")
        print("=" * 60)
    else:
        print("报价请求体构造失败")

    print("\n" + "=" * 60)
    print("处理完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
