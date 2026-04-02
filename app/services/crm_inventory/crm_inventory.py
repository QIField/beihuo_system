"""
CRM库存接口
https://crm.gzbbr.com/api/crm.Product/getProductList
"""
from app.utils.session_manager import SessionManager
from app.utils.database_connection import get_db_connection

API_URL = "https://crm.gzbbr.com/api/crm.Product/getProductList"
LIMIT = 500
COMPANY = 'fsbbr'


def get_inventory_list(page=1, limit=500, product_type="1"):
    """
    获取库存列表

    Args:
        page: 页码，默认1
        limit: 每页数量，默认500
        product_type: 类型，默认"1"

    Returns:
        dict: API响应数据
    """
    session = SessionManager.get_session()

    payload = {
        "page": page,
        "limit": limit,
        "type": product_type
    }

    resp = session.post(API_URL, json=payload, timeout=30)
    return resp.json()


def _parse_product(item):
    """解析单条产品数据"""
    return {
        'product_id': item.get('product_id'),
        'product_name': item.get('product_name', ''),
        'l_name_zh_default': item.get('l_name_zh_default', ''),
        'frey_no': item.get('frey_no', ''),
        'brand_name': item.get('brand_name', ''),
        'cass_oebrand_name': item.get('cass_oebrand_name', ''),
        'number': item.get('number', ''),
        'cost_price': float(item.get('cost_price', 0)) if item.get('cost_price') else 0.0,
        'cost_price_total': float(item.get('cost_price_total', 0)) if item.get('cost_price_total') else 0.0,
        'kw_nos': item.get('kw_nos', ''),
        'link_brand_code': item.get('link_brand_code', ''),
        'stock_quantity': int(item.get('stock_quantity', 0)) if item.get('stock_quantity') else 0,
        'vehicle_model': item.get('vehicle_model', ''),
        'warehouse_name': item.get('warehouse_name', ''),
        'company': COMPANY
    }


def _batch_save(products):
    """批量保存到数据库"""
    if not products:
        return 0

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO crmapp_inventory_detail
                (product_id, product_name, l_name_zh_default, frey_no, brand_name,
                 cass_oebrand_name, number, cost_price, cost_price_total, kw_nos,
                 link_brand_code, stock_quantity, vehicle_model, warehouse_name, company)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = []
            for p in products:
                values.append((
                    p['product_id'], p['product_name'], p['l_name_zh_default'],
                    p['frey_no'], p['brand_name'], p['cass_oebrand_name'],
                    p['number'], p['cost_price'], p['cost_price_total'],
                    p['kw_nos'], p['link_brand_code'], p['stock_quantity'],
                    p['vehicle_model'], p['warehouse_name'], p['company']
                ))
            cursor.executemany(sql, values)
            conn.commit()
            return len(values)
    except Exception as e:
        conn.rollback()
        print(f"批量保存失败: {e}")
        return 0
    finally:
        conn.close()


def crawl_all_inventory():
    """
    全量爬取库存数据
    1. 清空表
    2. 循环爬取所有页（每4页批量插入一次）
    """
    print("=" * 70)
    print("开始全量爬取库存数据")
    print("=" * 70)

    # 1. 清空表
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE crmapp_inventory_detail")
            print("[1/3] 已清空表")
    except Exception as e:
        print(f"清空表失败: {e}")
        return
    finally:
        conn.close()

    # 2. 获取第1页，得到总页数
    result = get_inventory_list(page=1, limit=LIMIT)
    if result.get('status') != 200 and result.get('msg') != '操作成功':
        print(f"获取第1页失败: {result.get('msg')}")
        return

    data = result.get('data', {})
    total = data.get('total', 0)
    last_page = data.get('last_page', 0)

    print(f"[2/3] 总记录数: {total}, 总页数: {last_page}, 每页: {LIMIT}")

    # 3. 循环爬取所有页
    all_products = []
    total_saved = 0

    for page in range(1, last_page + 1):
        result = get_inventory_list(page=page, limit=LIMIT)

        if result.get('status') != 200 and result.get('msg') != '操作成功':
            print(f"[第{page}页] 获取失败: {result.get('msg')}")
            continue

        items = result.get('data', {}).get('data', [])
        for item in items:
            all_products.append(_parse_product(item))

        # 每4页或最后一页时批量插入
        if page % 4 == 0 or page == last_page:
            saved = _batch_save(all_products)
            total_saved += saved
            print(f"[第{page}/{last_page}页] 已保存 {saved} 条")
            all_products = []

    print(f"[3/3] 全量爬取完成，共保存 {total_saved} 条")
    print("=" * 70)
