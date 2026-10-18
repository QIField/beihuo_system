"""
CRM UpdateView 接口模块
用于更新产品 brand_code 和 l_name_zh_store（产品名称）
"""

from config import get_auth_headers
from app.utils.crm_updateview_logger import execute_update_view_with_log, fetch_view_then_update, fetch_view_then_update_brand_code_if_changed
from .crm_product_id import get_product_id


def update_brand_code(session, product_id, brand_code, store_code='fsbbr'):
    """
    更新产品的 brand_code（先查view再回传完整字段）
    """
    headers = get_auth_headers(session)
    success, msg = fetch_view_then_update(
        session=session,
        product_id=str(product_id),
        new_values={"brand_code": brand_code},
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
    更新产品的 l_name_zh_store（产品名称）（先查view再回传完整字段）
    """
    headers = get_auth_headers(session)
    success, msg = fetch_view_then_update(
        session=session,
        product_id=str(product_id),
        new_values={"l_name_zh_store": product_name},
        source="crm_updateView",
        store_code=store_code,
        headers=headers,
        timeout=30,
    )

    if success:
        return {"status": 200, "msg": msg}
    return None


def update_brand_code_if_changed(session, product_id, brand_code, store_code='fsbbr'):
    """
    对比系统当前 brand_code 与新值，不同才更新（统一先 view 取所有原值再 updateView）

    Returns:
        (result, msg)，result 为 'updated' / 'unchanged' / 'failed'
    """
    return fetch_view_then_update_brand_code_if_changed(
        session=session,
        product_id=str(product_id),
        brand_code=brand_code,
        source="crm_updateView",
        store_code=store_code,
        headers=get_auth_headers(session),
        timeout=30,
    )


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
