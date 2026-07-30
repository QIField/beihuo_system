"""
通用 CRM 产品匹配器

职责：
- 根据 OE 从 CRM 查询产品
- 根据 OE 和品牌匹配 CRM 产品
- 过滤库存大于 0 的产品并返回
"""

import logging
from typing import List, Dict, Any, Optional

from app.utils.replace_number.crm_api_client import search_products_by_numberlist
from app.utils.replace_number.constants import ORIGINAL_BRANDS

logger = logging.getLogger(__name__)


def extract_child_products(api_data: Optional[Dict]) -> List[Dict[str, Any]]:
    """
    从 CRM Product.Product/list 返回数据中提取所有 child 产品

    Args:
        api_data: CRM 接口返回的 data 部分

    Returns:
        child 产品列表
    """
    if not api_data or not isinstance(api_data, dict):
        logger.debug("[提取产品] api_data 为空或类型错误: %s", type(api_data))
        return []

    products = []
    data_list = api_data.get("data", [])
    logger.debug("[提取产品] data.groups 数量: %d", len(data_list))
    
    for group in data_list:
        child_list = group.get("child", [])
        products.extend(child_list)
    
    logger.debug("[提取产品] 总 child 数量: %d", len(products))
    return products


def filter_products_by_stock(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    过滤库存大于 0 的产品

    规则：
    - 只保留 child[].stock > 0 的产品
    - stock 为空或非数值时跳过
    """
    result = []
    for product in products:
        stock = product.get("stock")
        if stock is None or stock == "":
            continue
        try:
            if float(stock) > 0:
                result.append(product)
        except (ValueError, TypeError):
            continue
    return result


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

    logger.info("[产品匹配] OE=%s, 品牌=%s, 命中=%d", oe_clean, brand_clean, len(matched))
    return matched


def fetch_crm_products(company: str, oe: str, ignore_stock: bool = False) -> List[Dict[str, Any]]:
    """
    调用 CRM 接口并返回产品

    职责单一：只负责从 CRM 查询，不涉及 OE/品牌匹配

    Args:
        company: 公司代码
        oe: OE 号
        ignore_stock: 是否忽略库存过滤，默认 False（只返回库存 > 0）

    Returns:
        CRM child 产品列表
    """
    logger.info("[CRM查询] 开始: company=%s, oe=%s, ignore_stock=%s", company, oe, ignore_stock)

    try:
        api_data = search_products_by_numberlist(company, oe)
        logger.debug("[CRM查询] CRM接口返回: type=%s, has_data=%s", type(api_data), api_data is not None)
    except Exception as e:
        logger.error("[CRM查询] CRM接口调用失败: %s", e, exc_info=True)
        return []

    products = extract_child_products(api_data)
    if ignore_stock:
        return products
    return filter_products_by_stock(products)


def fetch_matched_products(company: str, oe: str, brand: str = "", ignore_stock: bool = False) -> List[Dict[str, Any]]:
    """
    调用 CRM 接口并返回按 OE+品牌 匹配后的产品

    流程：
    - 调用 fetch_crm_products 获取 CRM 产品
    - 调用 match_products_by_oe_brand 按 OE 和品牌精确匹配

    Args:
        company: 公司代码
        oe: OE 号
        brand: 品牌名称
        ignore_stock: 是否忽略库存过滤，默认 False（只返回库存 > 0）

    Returns:
        匹配到的产品列表
    """
    logger.info("[产品匹配] 开始: company=%s, oe=%s, brand=%s, ignore_stock=%s", company, oe, brand, ignore_stock)

    products = fetch_crm_products(company, oe, ignore_stock=ignore_stock)
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
        "stock": product.get("stock"),
    }
