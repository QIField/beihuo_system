"""
CRM 替换号相关接口封装
"""

import time
from config import create_crm_session
from .constants import CRM_PRODUCT_LIST_URL, UPDATE_NUMBER_URL, RETRY_TIMES, SEARCH_LIMIT


def search_products_by_numberlist(company: str, numberlist: str):
    """
    调用 Product.Product/list 搜索产品

    Args:
        company: 公司代码
        numberlist: OE 号

    Returns:
        response.data 部分
    """
    session = create_crm_session(company)
    session.verify = False
    payload = {
        "numberlist": numberlist,
        "page": 1,
        "limit": SEARCH_LIMIT
    }

    last_error = None
    for attempt in range(RETRY_TIMES + 1):
        try:
            response = session.post(CRM_PRODUCT_LIST_URL, json=payload, timeout=30)
            data = response.json()
            if data.get("status") == 200:
                return data.get("data")
            last_error = RuntimeError(f"CRM 搜索失败: {data}")
        except Exception as e:
            last_error = e
            if attempt < RETRY_TIMES:
                time.sleep(1)

    raise last_error


def update_product_numbers(company: str, product_id: str, numbers: list):
    """
    调用 Product.Product/updateNumber 更新替换号

    Args:
        company: 公司代码
        product_id: 产品 ID
        numbers: 替换号列表

    Returns:
        CRM 接口原始响应字典
    """
    session = create_crm_session(company)
    session.verify = False
    payload = {
        "product_id": str(product_id),
        "numbers": numbers
    }

    last_error = None
    for attempt in range(RETRY_TIMES + 1):
        try:
            response = session.post(UPDATE_NUMBER_URL, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            last_error = e
            if attempt < RETRY_TIMES:
                time.sleep(1)

    raise last_error
