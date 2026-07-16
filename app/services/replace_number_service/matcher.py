"""
替换号搜索匹配逻辑
"""

from typing import List, Dict
from .models import MatchedProduct
from app.utils.replace_number.constants import ORIGINAL_BRANDS


def extract_display_numbers(display_number) -> List[str]:
    """
    从 CRM 返回的 display_number 数组中提取通用号

    Args:
        display_number: 接口返回的 display_number 字段

    Returns:
        替换号列表，保持原始内容，仅去重
    """
    if not display_number or not isinstance(display_number, list):
        return []

    result = []
    for item in display_number:
        if isinstance(item, dict):
            num = str(item.get("number", "")).strip()
            if num and num not in result:
                result.append(num)
    return result


def extract_brand_codes(api_data: Dict) -> List[str]:
    """
    遍历 data 下所有 child 的 brand_code，整合后去重

    值可能包含逗号，如 "123,456"，需要拆分后逐个对比

    Args:
        api_data: CRM 接口返回的 data 部分

    Returns:
        brand_code 列表
    """
    codes = []
    for group in api_data.get("data", []):
        for child in group.get("child", []):
            brand_code_raw = child.get("brand_code")
            if not brand_code_raw:
                continue
            brand_code_str = str(brand_code_raw).strip()
            if not brand_code_str:
                continue
            for part in brand_code_str.replace("，", ",").split(","):
                code = part.strip()
                if code and code not in codes:
                    codes.append(code)
    return codes


def match_products(api_data: Dict, oe: str, brand: str) -> List[MatchedProduct]:
    """
    根据 OE 和品牌匹配产品

    匹配规则：
    - 原厂/原厂国内4S件：child.number 必须等于 oe，且 child.brand_name 必须等于 brand
    - 其他品牌：child.brand_name 等于 brand 即可

    匹配后会从 display_number 中过滤掉与 brand_code 相同的值

    Args:
        api_data: CRM 接口返回的 data 部分
        oe: 输入的 OE 号
        brand: 输入的品牌

    Returns:
        匹配到的产品列表
    """
    results = []
    is_original = brand in ORIGINAL_BRANDS
    brand_codes = extract_brand_codes(api_data)

    for group in api_data.get("data", []):
        for child in group.get("child", []):
            child_number = str(child.get("number", "")).strip()
            child_brand = str(child.get("brand_name", "")).strip()

            if is_original:
                if child_number != oe or child_brand != brand:
                    continue
            else:
                if child_brand != brand:
                    continue

            display_numbers = extract_display_numbers(child.get("display_number"))
            if brand_codes:
                display_numbers = [n for n in display_numbers if n not in brand_codes]

            results.append(MatchedProduct(
                product_id=str(child.get("product_id", "")),
                number=child_number,
                brand_name=child_brand,
                display_numbers=display_numbers
            ))

    return results
