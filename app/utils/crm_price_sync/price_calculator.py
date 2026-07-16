# -*- coding: utf-8 -*-
"""
CRM 产品价格同步：价格计算

根据佛山 store_cass_price 和品牌倍率，计算珠海更新所需价格。
"""

import math


# 品牌倍率配置
BRAND_RATE_MAP = {
    "菲尔": 1.08,
}
OEM_BRANDS = {"原厂", "原厂国内4s件"}
DEFAULT_RATE = 1.06


def _to_float(value):
    """将字符串或数字转为 float，失败返回 None。"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def is_valid_fs_price(value):
    """
    判断佛山 store_cass_price 是否有效（必须大于 0）。

    :param value: 价格值
    :return: bool
    """
    price = _to_float(value)
    return price is not None and price > 0


def get_brand_rate(brand_name):
    """
    根据品牌名称获取倍率。

    :param brand_name: 品牌名称
    :return: float 倍率
    """
    if brand_name in BRAND_RATE_MAP:
        return BRAND_RATE_MAP[brand_name]
    if brand_name in OEM_BRANDS:
        return 1.05
    return DEFAULT_RATE


def calculate_update_payload(fs_store_cass_price, brand_name, view_data):
    """
    根据佛山 cass 价、品牌和 view 接口数据，生成 updateView payload。

    :param fs_store_cass_price: 佛山 store_cass_price
    :param brand_name: 品牌名称
    :param view_data: view 接口返回的 data 字段
    :return: dict 可直接用于 updateView 的 payload；佛山无价格时返回 None
    """
    base_price = _to_float(fs_store_cass_price)
    if base_price is None:
        return None

    rate = get_brand_rate(brand_name)
    multiplied = base_price * rate

    new_price = math.ceil(multiplied)

    return {
        "product_id": str(view_data.get("product_id", "")),
        "brand_code": view_data.get("brand_code") or "",
        "cass_desc": view_data.get("cass_desc") or "",
        "l_name_zh_store": view_data.get("l_name_zh_store") or "",
        "cost_price": view_data.get("cost_price") or "",
        "manufacturer_price": view_data.get("manufacturer_price"),
        "store_cass_price": str(new_price),
        "qpl_price": str(new_price),
    }
