"""
通用 CRM 产品匹配器

职责：
- 根据 OE 从 CRM 查询产品
- 过滤库存大于 0 的产品并返回
"""

from typing import List, Dict, Any, Optional

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


def fetch_matched_products(company: str, oe: str, brand: str = "") -> List[Dict[str, Any]]:
    """
    调用 CRM 接口并返回库存大于 0 的产品

    流程：
    - 调用 CRM Product.Product/list
    - 提取 data.data[].child[]
    - 过滤 stock > 0 的产品

    Args:
        company: 公司代码
        oe: OE 号
        brand: 品牌名称（保留参数，暂不参与接口过滤）

    Returns:
        库存大于 0 的产品列表
    """
    api_data = search_products_by_numberlist(company, oe)
    products = extract_child_products(api_data)
    return filter_products_by_stock(products)


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
