#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价 · PAGE_QUOTE 提交体构造

差异点（与旧 quote_builder 对比，依据新页面 HAR）：
1. 报价项：quoteStatus=QUOTED、quoteMethod=AUTO_QUOTE、quoteExtraInfoVo={}
   （站内商品场景已实证：41 条历史报价 quoteExtraInfoVo 全为空对象）
2. 移除旧格式专属字段：pidSrcList / checkPriceSrc / productList
3. 顶层：quoteType=PAGE_QUOTE + pickUpWay/pickUpWayStr/deliveryAddress
   （实测接口校验"配送方式为空"，该三字段必须保留，来源见 pipeline 取货方式接口）
"""

from app.services.qpl_auto_quote.constants import QUOTE_TYPE_PAGE_QUOTE

# 旧构造产出中，新格式已移除的字段
_REMOVED_KEYS = ('pidSrcList', 'checkPriceSrc', 'productList')


def normalize_quote_item(quote_item):
    """
    将旧匹配链（construct_crm_quote_item / construct_adapter_quote_item）
    产出的报价项调整为 PAGE_QUOTE 新格式。

    - 已有报价项（来自详情 supplierQuoteItemList）原样透传，仅补缺失兜底
    - 新构造报价项：quoteStatus=QUOTED、quoteMethod=AUTO_QUOTE、quoteExtraInfoVo={}
    """
    item = dict(quote_item)

    # 已有报价项透传（带服务端分配的 supplierQuoteItemId 与完整 quoteExtraInfoVo）
    if item.get('supplierQuoteItemId'):
        return item

    for key in _REMOVED_KEYS:
        item.pop(key, None)

    item['quoteStatus'] = 'QUOTED'
    item['quoteMethod'] = 'AUTO_QUOTE'
    item['quoteExtraInfoVo'] = {}
    if not item.get('quoteTaxType'):
        item['quoteTaxType'] = 'INCLUSIVE'
    return item


def build_submit_request(detail_data, extra_quote_items):
    """
    构造 PAGE_QUOTE 提交请求体。

    规则（与旧版一致）：
    - PART_QUOTE / QUOTED 明细：保留已有报价项
    - extra_quote_items 中的新报价项追加到对应明细

    Args:
        detail_data: 全量详情（get_enquiry_detail_all 返回）
        extra_quote_items: {enquiry_item_id: [quote_item, ...]}

    Returns:
        dict: {channel, supplierEnquiryNo, quoteType, demandList}
    """
    extra_quote_items = extra_quote_items or {}
    demand_list = detail_data.get('supplierEnquiryDemandList', [])
    constructed = []

    for demand in demand_list:
        enquiry_item_list = []
        for item in demand.get('supplierEnquiryItemList', []):
            item_id = item.get('enquiryItemId')
            quote_status = item.get('quoteStatus')
            quote_item_list = []

            if quote_status in ('PART_QUOTE', 'QUOTED'):
                quote_item_list.extend(
                    normalize_quote_item(q) for q in item.get('supplierQuoteItemList') or [])

            if item_id in extra_quote_items:
                quote_item_list.extend(
                    normalize_quote_item(q) for q in extra_quote_items[item_id])

            enquiry_item_list.append({
                "addItemOe": item.get('addItemOe', ''),
                "itemDescription": item.get('itemDescription'),
                "itemOe": item.get('itemOe'),
                "supplierEnquiryItemId": item_id,
                "quoteItemList": quote_item_list,
                "itemName": item.get('itemName'),
                "closeReason": item.get('closeReason') or "",
                "closeRemarks": item.get('closeRemarks') or "",
                "quoteStatus": quote_status,
            })

        constructed.append({
            "supplierDemandId": demand.get('supplerDemandId'),
            "enquiryItemList": enquiry_item_list,
        })

    return {
        "channel": "S_STATION",
        "supplierEnquiryNo": detail_data.get('supplierEnquiryNo'),
        "quoteType": QUOTE_TYPE_PAGE_QUOTE,
        "pickUpWay": detail_data.get('pickUpWay'),
        "pickUpWayStr": detail_data.get('pickUpWayStr'),
        "deliveryAddress": detail_data.get('deliveryAddress'),
        "demandList": constructed,
    }
