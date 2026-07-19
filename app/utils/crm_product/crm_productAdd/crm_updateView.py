"""
CRM UpdateView 接口模块
用于更新产品 brand_code 和 l_name_zh_store（产品名称）
"""

from config import get_auth_headers
from app.utils.crm_updateview_logger import execute_update_view_with_log
from .crm_product_id import get_product_id


def update_brand_code(session, product_id, brand_code, store_code='fsbbr'):
    """
    更新产品的 brand_code
    """
    payload = {
        "product_id": product_id,
        "brand_code": brand_code
    }

    headers = get_auth_headers(session)
    success, msg = execute_update_view_with_log(
        session=session,
        payload=payload,
        source="crm_updateView",
        store_code=store_code,
        headers=headers,
        timeout=30,
    )

    if success:
        return {"status": 200, "msg": msg}
    return None


def update_product_name(session, product_id, product_name, store_code='fsbbr'):
    """
    更新产品的 l_name_zh_store（产品名称）
    """
    payload = {
        "product_id": product_id,
        "l_name_zh_store": product_name
    }

    headers = get_auth_headers(session)
    success, msg = execute_update_view_with_log(
        session=session,
        payload=payload,
        source="crm_updateView",
        store_code=store_code,
        headers=headers,
        timeout=30,
    )

    if success:
        return {"status": 200, "msg": msg}
    return None


def update_brand_code_by_oe(session, oe_number, brand, brand_code):
    """
    根据 OE 号和品牌更新 brand_code
    """
    product_id = get_product_id(session, oe_number, brand)
    if not product_id:
        return None
    
    return update_brand_code(session, product_id, brand_code)


def update_product_name_by_oe(session, oe_number, brand, product_name):
    """
    根据 OE 号和品牌更新产品名称
    """
    product_id = get_product_id(session, oe_number, brand)
    if not product_id:
        return None
    
    return update_product_name(session, product_id, product_name)
