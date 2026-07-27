"""
通用 CRM 产品匹配器

职责：
- 根据 OE 从 CRM 查询产品
- 过滤库存大于 0 的产品并返回
"""

import logging
from typing import List, Dict, Any, Optional

from app.utils.replace_number.crm_api_client import search_products_by_numberlist

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
    skipped = 0
    
    for product in products:
        stock = product.get("stock")
        product_number = product.get("number", "unknown")
        
        if stock is None or stock == "":
            logger.debug("[过滤库存] 跳过 (stock为空): number=%s", product_number)
            skipped += 1
            continue
        
        try:
            stock_num = float(stock)
            if stock_num > 0:
                result.append(product)
                logger.debug("[过滤库存] 保留: number=%s, stock=%s", product_number, stock)
            else:
                logger.debug("[过滤库存] 跳过 (stock<=0): number=%s, stock=%s", product_number, stock)
                skipped += 1
        except (ValueError, TypeError):
            logger.debug("[过滤库存] 跳过 (stock非数值): number=%s, stock=%s", product_number, stock)
            skipped += 1
    
    logger.info("[过滤库存] 结果: 保留=%d, 跳过=%d", len(result), skipped)
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
    logger.info("[产品匹配] 开始: company=%s, oe=%s, brand=%s", company, oe, brand)
    
    try:
        api_data = search_products_by_numberlist(company, oe)
        logger.debug("[产品匹配] CRM接口返回: type=%s, has_data=%s", type(api_data), api_data is not None)
    except Exception as e:
        logger.error("[产品匹配] CRM接口调用失败: %s", e, exc_info=True)
        return []
    
    products = extract_child_products(api_data)
    
    if not products:
        logger.warning("[产品匹配] 无 child 产品: oe=%s", oe)
    
    filtered_products = filter_products_by_stock(products)
    
    logger.info("[产品匹配] 完成: oe=%s, 返回产品数=%d", oe, len(filtered_products))
    return filtered_products


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
