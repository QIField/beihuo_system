#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""报价请求体构造器"""


def is_all_part_quote(detail_data):
    """检查是否全是PART_QUOTE"""
    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            if item.get('quoteStatus') != 'PART_QUOTE':
                return False
    return True


def construct_quote_item(quote_info):
    """从 supplierQuoteItemList 转换为报价请求体中的报价项格式"""
    item_pid = quote_info.get('pid', '')
    product_name = quote_info.get('displaceProductName') or quote_info.get('standardItemName', '')

    # 安全转换为 int
    def to_int(val):
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return val

    return {
        "brandId": to_int(quote_info.get('brandId')),
        "brandName": quote_info.get('brandName'),
        "deliveryAging": to_int(quote_info.get('deliveryAging', 1)),
        "prepareGoodTimespan": to_int(quote_info.get('prepareGoodTimespan')),
        "prepareGoodTimespanUnit": quote_info.get('prepareGoodTimespanUnit', ''),
        "itemQuality": to_int(quote_info.get('itemQuality')),
        "itemRemark": quote_info.get('itemRemark', ''),
        "itemSellPrice": to_int(quote_info.get('itemSellPrice')),
        "partsNo": quote_info.get('partsNo') or '',
        "quoteImageList": [],
        "supplierQuoteItemId": quote_info.get('supplierQuoteItemId'),
        "standardName": product_name,
        "supplierQuoteProductId": '',
        "pid": item_pid,
        "pidSrcList": quote_info.get('pidSrcList', []) if quote_info.get('pidSrcList') else ['SUPPLIER_EPC_OE_MATCH'],
        "checkPriceSrc": None,
        "transferDay": '',
        "itemPerhapsReplaceOe": quote_info.get('itemPerhapsReplaceOe'),
        "brandType": quote_info.get('brandTypeEnum') or quote_info.get('brandType'),
        "qualityType": quote_info.get('qualityTypeCode'),
        "qualityTypeDesc": quote_info.get('qualityTypeDesc'),
        "qualityTypeId": to_int(quote_info.get('qualityTypeId')),
        "quoteTaxType": quote_info.get('quoteTaxType') or 'INCLUSIVE',
        "originTire": None,
        "packageAmount": None,
        "packageUnit": '',
        "quoteExtraInfoVo": {"originTire": None},
        "priceCheckSnapshot": quote_info.get('priceCheckSnapshot'),
        "quoteItemSalesAttribute": quote_info.get('quoteItemSalesAttribute') or {
            "categoryId": "/5/",
            "attributeList": [],
            "productionAttribute": ""
        },
        "quoteStatus": quote_info.get('quoteStatus') or 'QUOTED',
        "productList": quote_info.get('productList') or [{
            "adaptStrategyList": ["OE"],
            "productName": product_name,
            "productKey": item_pid,
            "imgList": [],
            "partNoe": "",
            "pid": item_pid,
            "supplierProductId": None,
            "supplierSalesPrice": None
        }]
    }


# 仓库映射
WAREHOUSE_MAP = {
    '8918': 'PDC BJ 北京',
    '8928': 'PDC SH (HZ) 宝湾',
    '8938': '广州PDC',
    '8958': '成都PDC CD',
    '8968': 'PDC KS 昆山',
    '8978': 'PDC JN 济南',
    '8991': '西区危险品库',
    '8992': '南区危险品库',
    '8993': '东区危险品库',
    '8994': '北区危险品库',
}


def construct_adapter_quote_item(brand, product, all_products, item_sell_price, prepare_good_timespan, price_check_snapshot=None, category_id="/5/"):
    """
    从适配品牌构造第三方报价项（奔驰/宝马等待报价项目用）

    Args:
        brand: 原厂品牌信息
        product: 当前报价项对应的产品（用于 pid/standardName/itemPerhapsReplaceOe 等自身字段）
        all_products: 该 item 下所有原厂产品列表（用于 productList 填充）
        item_sell_price: 报价价格
        prepare_good_timespan: 备货天数
        price_check_snapshot: priceCheck 校验快照
        category_id: 品类ID
    """
    product_pid = product.get('pid', '')
    product_name = product.get('displaceProductName', '')

    # productList：包含该 item 下所有原厂产品（每个报价项的 productList 都一样）
    product_list = []
    for p in all_products:
        p_pid = p.get('pid', '')
        p_name = p.get('displaceProductName', '')
        p_images = p.get('quoteImageList', [])
        product_list.append({
            "adaptStrategyList": p.get('adaptStrategyList', ['OE']),
            "productName": p_name,
            "productKey": p_pid,
            "partNoe": "",
            "pid": p_pid,
            "supplierProductId": None,
            "supplierSalesPrice": None
        })

    return {
        "brandId": brand.get('brandId'),
        "brandName": brand.get('brandName'),
        "deliveryAging": 2,
        "prepareGoodTimespan": prepare_good_timespan,
        "prepareGoodTimespanUnit": "DAY",
        "itemQuality": product.get('quality'),
        "itemRemark": "",
        "itemSellPrice": item_sell_price,
        "partsNo": "",
        "quoteImageList": [],
        "supplierQuoteItemId": None,
        "standardName": product_name,
        "supplierQuoteProductId": "",
        "pid": product_pid,
        "pidSrcList": product.get('pidSrcList', []),
        "checkPriceSrc": None,
        "transferDay": "",
        "itemPerhapsReplaceOe": product.get('itemPerhapsReplaceOe'),
        "brandType": brand.get('brandType'),
        "qualityType": product.get('qualityTypeCode'),
        "qualityTypeDesc": product.get('qualityTypeDesc'),
        "qualityTypeId": product.get('qualityTypeId'),
        "quoteTaxType": "INCLUSIVE",
        "originTire": product.get('originTire'),
        "packageAmount": None,
        "packageUnit": "",
        "quoteExtraInfoVo": {
            "originTire": product.get('originTire')
        },
        "priceCheckSnapshot": price_check_snapshot,
        "quoteItemSalesAttribute": {
            "categoryId": category_id,
            "attributeList": [],
            "productionAttribute": ""
        },
        "quoteStatus": "WAITING_QUOTE",
        "productList": product_list
    }


def select_warehouse_and_days(stock_info):
    """
    选择仓库并确定备货时效
    优先选广州(8938)有货 → 2天
    其他有货仓库 → 7天
    """
    # 筛选有货的仓库
    available_warehouses = [
        s for s in stock_info 
        if s.get('quantity_available', 0) > 0
    ]
    
    if not available_warehouses:
        return None, 7  # 没货默认7天
    
    # 优先选广州
    guangzhou = next((s for s in available_warehouses 
                     if str(s.get('warehouse', '')) == '8938'), None)
    
    if guangzhou:
        return guangzhou, 2
    
    # 其他有货仓库选第一个
    return available_warehouses[0], 7


def construct_quote_request(detail_data, extra_quote_items=None):
    """
    构造报价请求体
    """
    extra_quote_items = extra_quote_items or {}
    
    demand_list = detail_data.get('supplierEnquiryDemandList', [])
    constructed_demand_list = []
    
    for demand in demand_list:
        suppler_demand_id = demand.get('supplerDemandId')
        item_list = demand.get('supplierEnquiryItemList', [])

        enquiry_item_list = []
        for item in item_list:
            enquiry_item_id = item.get('enquiryItemId')
            quote_item_list = []

            quote_status = item.get('quoteStatus')

            # PART_QUOTE / QUOTED: 使用已有报价
            if quote_status in ('PART_QUOTE', 'QUOTED'):
                for quote_info in item.get('supplierQuoteItemList', []):
                    quote_item = construct_quote_item(quote_info)
                    quote_item_list.append(quote_item)

            # WAITING_QUOTE + 奔驰/宝马车: 从适配列表构造报价（支持一到多个报价项）
            elif quote_status == 'WAITING_QUOTE' and enquiry_item_id in extra_quote_items:
                adapter_quote = extra_quote_items[enquiry_item_id]
                if isinstance(adapter_quote, list):
                    quote_item_list.extend(adapter_quote)
                else:
                    quote_item_list.append(adapter_quote)
            
            enquiry_item = {
                "addItemOe": item.get('addItemOe', ''),
                "itemDescription": item.get('itemDescription'),
                "itemOe": item.get('itemOe'),
                "supplierEnquiryItemId": enquiry_item_id,
                "quoteItemList": quote_item_list,
                "itemName": item.get('itemName'),
                "closeReason": item.get('closeReason') or "",
                "closeRemarks": item.get('closeRemarks') or "",
                "quoteStatus": quote_status
            }
            enquiry_item_list.append(enquiry_item)
        
        constructed_demand_list.append({
            "supplierDemandId": suppler_demand_id,
            "enquiryItemList": enquiry_item_list
        })
    
    return {
        "channel": "S_STATION",
        "demandList": constructed_demand_list,
        "supplierEnquiryNo": detail_data.get('supplierEnquiryNo'),
        "pickUpWay": detail_data.get('pickUpWay'),
        "pickUpWayStr": detail_data.get('pickUpWayStr'),
        "deliveryAddress": detail_data.get('deliveryAddress')
    }
