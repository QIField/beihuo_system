"""
修理厂询价单 · CRM 产品开思价查询与修改服务

搜索：复用 search_products_by_numberlist 调 Product.Product/list，
child 自带 store_cass_price（开思价）/ cost_price（成本价），一次请求拿全。
更新：复用 fetch_view_then_update（先 view 取所有原值 → 合并 → updateView →
写 crm_updateview_log 日志），source 记为 cass_inquiry 便于区分来源。
"""

from config import create_crm_session
from app.utils.crm_product.crm_product_matcher import extract_child_products
from app.utils.crm_updateview_logger import fetch_view_then_update
from app.utils.replace_number.crm_api_client import search_products_by_numberlist

# 公司代码（与 CRM 价格同步模块一致，固定 fsbbr 佛山）
COMPANY = 'fsbbr'


def search_products_by_replacement(replacement: str) -> list:
    """
    按商家替换号搜索 CRM 产品（全量返回，不按库存过滤）

    :param replacement: 替换号（OE）
    :return: [{'product_id', 'number', 'brand_name', 'l_name_zh',
               'store_cass_price', 'cost_price'}]，product_id 供前端缓存更新用
    """
    api_data = search_products_by_numberlist(COMPANY, str(replacement).strip())
    products = []
    for child in extract_child_products(api_data):
        if not isinstance(child, dict):
            continue
        products.append({
            'product_id': str(child.get('product_id') or ''),
            'number': child.get('number') or '',
            'brand_name': child.get('brand_name') or '',
            'l_name_zh': child.get('l_name_zh') or '',
            'store_cass_price': child.get('store_cass_price'),
            'cost_price': child.get('cost_price'),
        })
    return products


def _normalize_price(value):
    """价格规范化：须为大于 0 的数字，合法返回 float，否则 None"""
    if value is None:
        return None
    try:
        price = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def update_cass_prices(items: list) -> list:
    """
    批量更新开思价（串行逐行，单行失败不影响其他行）

    :param items: [{'product_id', 'store_cass_price'}]
    :return: [{'product_id', 'success', 'msg'}]，与入参顺序一致
    """
    results = []
    session = create_crm_session(COMPANY)
    try:
        for item in items:
            if not isinstance(item, dict):
                results.append({'product_id': '', 'success': False, 'msg': '参数格式错误'})
                continue

            product_id = str(item.get('product_id') or '').strip()
            if not product_id:
                results.append({'product_id': '', 'success': False, 'msg': '缺少 product_id'})
                continue

            price = _normalize_price(item.get('store_cass_price'))
            if price is None:
                results.append({'product_id': product_id, 'success': False, 'msg': '开思价须为大于0的数字'})
                continue

            success, msg = fetch_view_then_update(
                session=session,
                product_id=product_id,
                new_values={'store_cass_price': price},
                source='cass_inquiry',
                store_code=COMPANY,
                timeout=30,
            )
            results.append({
                'product_id': product_id,
                'success': success,
                'msg': '开思价已更新' if success else (msg or '更新失败'),
            })
    finally:
        session.close()
    return results
