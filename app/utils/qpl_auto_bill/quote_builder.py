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
    """构造单个报价项"""
    quote_extra = quote_info.get('quoteExtraInfo', {})
    
    return {
        "addOeQuoteInfo": None,
        "brandId": str(quote_info.get('brandId')),
        "brandName": quote_info.get('brandName'),
        "deliveryAging": quote_info.get('deliveryAging', 1),
        "prepareGoodTimespan": quote_info.get('prepareGoodTimespan'),
        "prepareGoodTimespanUnit": quote_info.get('prepareGoodTimespanUnit', ''),
        "itemQuality": quote_info.get('itemQuality'),
        "itemRemark": quote_info.get('itemRemark', ''),
        "itemSellPrice": int(quote_info.get('itemSellPrice')) if quote_info.get('itemSellPrice') else None,
        "partsNo": quote_info.get('partsNo'),
        "quoteImageList": quote_info.get('quoteImageList'),
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
            "supplierQualification": quote_extra.get('supplierQualification'),
            "supplierQualificationAuthorizedType": quote_extra.get('supplierQualificationAuthorizedType'),
            "supplierProductSrc": "ERP_SUPPLIER",
            "supplierProductId": quote_extra.get('supplierProductId'),
            "supplierERPOriginalOE": quote_extra.get('supplierERPOriginalOE'),
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
            "needApprove": quote_extra.get('needApprove', False),
            "addOeQuote": quote_extra.get('addOeQuote', False),
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


def construct_quote_request(detail_data):
    """构造报价请求体"""
    demand_list = detail_data.get('supplierEnquiryDemandList', [])
    constructed_demand_list = []
    
    for demand in demand_list:
        suppler_demand_id = demand.get('supplerDemandId')
        item_list = demand.get('supplierEnquiryItemList', [])
        
        enquiry_item_list = []
        for item in item_list:
            enquiry_item_id = item.get('enquiryItemId')
            quote_item_list = []
            
            # PART_QUOTE: 使用已有报价
            for quote_info in item.get('supplierQuoteItemList', []):
                quote_item = construct_quote_item(quote_info)
                quote_item_list.append(quote_item)
            
            enquiry_item = {
                "addItemOe": item.get('addItemOe', ''),
                "itemDescription": item.get('itemDescription'),
                "itemOe": item.get('itemOe'),
                "supplierEnquiryItemId": enquiry_item_id,
                "quoteItemList": quote_item_list,
                "itemName": item.get('itemName'),
                "closeReason": item.get('closeReason') or "",
                "closeRemarks": item.get('closeRemarks') or "",
                "quoteStatus": item.get('quoteStatus')
            }
            enquiry_item_list.append(enquiry_item)
        
        constructed_demand_list.append({
            "supplierDemandId": suppler_demand_id,
            "enquiryItemList": enquiry_item_list
        })
    
    return {
        "channel": "S_STATION",
        "demandList": constructed_demand_list,
        "supplierEnquiryNo": detail_data.get('supplierEnquiryNo')
    }
