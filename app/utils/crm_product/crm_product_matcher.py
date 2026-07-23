"""
通用 CRM 产品匹配器

职责：
- 根据 OE + 品牌从 CRM 查询产品
- 按统一规则过滤匹配结果
"""

from typing import List, Dict, Any, Optional

from app.utils.replace_number.constants import ORIGINAL_BRANDS
from app.utils.replace_number.crm_api_client import search_products_by_numberlist


def extract_child_products(api_data: Optional[Dict]) -> List[Dict[str, Any]]:
    """
    从 CRM Product.Product/list 返回数据中提取所有 child 产品

    Args:
        api_data: CRM 接口返回的 data 部分

    Returns:
        child 产品列表
    """
    if not api_data or not isinstance(api_data, dict):
        return []

    products = []
    for group in api_data.get("data", []):
        for child in group.get("child", []):
            products.append(child)
    return products


def match_products_by_oe_brand(oe: str, brand: str, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据 OE 和品牌匹配 CRM 产品

    规则：
    - 原厂 / 原厂国内4S件：必须同时精确匹配 number 和 brand_name
    - 其他品牌：只需精确匹配 brand_name

    Args:
        oe: OE 号
        brand: 品牌名称
        products: CRM child 产品列表

    Returns:
        匹配到的产品列表（可能多条）
    """
    oe_clean = str(oe or "").strip()
    brand_clean = str(brand or "").strip()

    matched = []
    for product in products:
        product_number = str(product.get("number", "") or "").strip()
        product_brand = str(product.get("brand_name", "") or "").strip()

        if brand_clean in ORIGINAL_BRANDS:
            if product_number == oe_clean and product_brand == brand_clean:
                matched.append(product)
        else:
            if product_brand == brand_clean:
                matched.append(product)

    return matched


def fetch_matched_products(company: str, oe: str, brand: str) -> List[Dict[str, Any]]:
    """
    调用 CRM 接口并匹配产品

    Args:
        company: 公司代码
        oe: OE 号
        brand: 品牌名称

    Returns:
        匹配到的产品列表
    """
    api_data = search_products_by_numberlist(company, oe)
    products = extract_child_products(api_data)
    return match_products_by_oe_brand(oe, brand, products)


def pick_product_fields(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    从产品字典中提取需要的字段

    Args:
        product: CRM child 产品

    Returns:
        精简后的产品字段
    """
    return {
        "product_id": product.get("product_id"),
        "number": product.get("number"),
        "brand_name": product.get("brand_name"),
        "frey_no": product.get("frey_no"),
        "store_cass_price": product.get("store_cass_price"),
        "cost_price": product.get("cost_price"),
    }
