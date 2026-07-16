# -*- coding: utf-8 -*-
"""
CRM 产品价格同步：产品匹配与过滤

对佛山、珠海两店库存产品进行提取、匹配、分离。
"""


def extract_stock_items(products):
    """
    从 list 接口返回的 child 列表中提取关键字段。

    :param products: list[dict] child 产品列表
    :return: list[dict] 包含 brand_name, number, product_id 的字典
    """
    items = []
    for product in products:
        items.append({
            "brand_name": product.get("brand_name", ""),
            "number": product.get("number", ""),
            "product_id": product.get("product_id"),
            "store_cass_price": product.get("store_cass_price"),
        })
    return items


def match_stock_items(fs_items, zh_items):
    """
    匹配佛山和珠海的库存产品。

    :param fs_items: 佛山产品列表
    :param zh_items: 珠海产品列表
    :return: dict {
        "both": list[dict],        # 两店都有，含佛山 store_cass_price
        "only_zhuhai": list[dict], # 只有珠海有
        "only_foshan": list[dict]  # 只有佛山有
    }
    """
    fs_map = {
        (item["brand_name"], item["number"]): item
        for item in fs_items
        if item["brand_name"] and item["number"]
    }
    zh_map = {
        (item["brand_name"], item["number"]): item
        for item in zh_items
        if item["brand_name"] and item["number"]
    }

    both = []
    only_zhuhai = []
    only_foshan = []

    for key, zh_item in zh_map.items():
        fs_item = fs_map.get(key)
        if fs_item:
            both.append({
                "brand_name": zh_item["brand_name"],
                "number": zh_item["number"],
                "product_id": zh_item["product_id"],
                "fs_store_cass_price": fs_item.get("store_cass_price"),
            })
        else:
            only_zhuhai.append(zh_item)

    for key, fs_item in fs_map.items():
        if key not in zh_map:
            only_foshan.append(fs_item)

    return {
        "both": both,
        "only_zhuhai": only_zhuhai,
        "only_foshan": only_foshan,
    }
