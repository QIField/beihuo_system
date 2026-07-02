#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价 - CRM 品牌匹配配置

匹配规则：
1. 适配列表 brandTypeDesc == '原厂' 时，用 ORIGINAL_FACTORY_BRANDS 列表匹配 CRM brand_name
2. 非原厂时，用 BRAND_NAME_MAP 映射适配列表 brandName → CRM brandName
3. 映射找不到时，默认用适配列表 brandName 直接匹配
"""

# 原厂相关 CRM brand_name 列表
ORIGINAL_FACTORY_BRANDS = [
    "原厂国内4s件",
]

# 非原厂品牌名称映射：适配列表 brandName → CRM brandName
# 注意：key 是适配列表中的完整 brandName 字符串
BRAND_NAME_MAP = {
    "INA": "依纳",
    "菲尔/FREY": "菲尔",
    "卡玛伦/COMOOL": "卡玛伦",
    "欧斯卡/OSSCA": "OSSCA",
    "曼克马利/MANKEMALI": "曼克马利",
    "路爵士": "路爵士",
    "爱车贝母/ACBM": "ACBM",
    "海拉/HELLA": "海拉",
    "马勒/MAHLE": "马勒",
    "德纳/DANA": "德纳",
    "斯凯孚/SKF": "SKF",
    "德国马牌/Continental": "马牌",
    "布雷博/Brembo": "布雷博",
    "盖茨/GATES": "盖茨",
    "法雷奥/VALEO": "法雷奥",
    "科帝克/CORTECO": "科帝克",
    "WAHLER": "瓦勒",
}


def get_crm_brand_names(adapt_brand_name, adapt_brand_type_desc):
    """
    根据适配列表品牌信息，获取可匹配的 CRM brand_name 列表

    Args:
        adapt_brand_name: 适配列表品牌名称
        adapt_brand_type_desc: 适配列表品牌类型描述

    Returns:
        list: 可匹配的 CRM brand_name 列表
    """
    if adapt_brand_type_desc == "原厂":
        return ORIGINAL_FACTORY_BRANDS

    mapped = BRAND_NAME_MAP.get(adapt_brand_name)
    if mapped:
        return [mapped]

    return [adapt_brand_name]
