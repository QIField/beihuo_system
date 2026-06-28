#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""自动提交部分报价订单"""

import sys
import os
import json
import io
from contextlib import redirect_stdout

# 关闭 urllib3 HTTPS 证书验证警告（奔驰接口使用 verify=False）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 添加当前目录到路径，支持相对导入
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))

from datetime import datetime, timedelta
from enquiry_api import (
    query_enquiry_list, get_enquiry_detail, get_adapt_product_brand,
    price_check, get_pickup_way_and_distance, extract_pickup_info, cannot_quote
)
from quote_builder import (
    is_all_part_quote,
    construct_quote_request,
    construct_adapter_quote_item,
    select_warehouse_and_days,
    WAREHOUSE_MAP
)
from qpl_config import BASE_URL, get_headers, handle_qpl_response, BMW_PRICE_FORMULA, qpl_log

try:
    from app.services.car_parts_library_service.bmw_crawler import external_data_crawler
    BMW_SERVICE_AVAILABLE = True
except ImportError:
    BMW_SERVICE_AVAILABLE = False
    print("[汽配龙自动报价] 宝马服务模块未找到")
import requests

try:
    from app.services.car_parts_library_service.mercedes_dalfsc_service import by_part_number_get_data
    MERCEDES_SERVICE_AVAILABLE = True
except ImportError:
    MERCEDES_SERVICE_AVAILABLE = False
    print("[汽配龙自动报价] 奔驰服务模块未找到")


def submit_quote(quote_request, company='fsbbr'):
    """
    提交报价

    Args:
        quote_request: 报价请求体
        company: 组织代码，默认fsbbr

    Returns:
        dict: 提交结果
    """
    url = f'{BASE_URL}/qpl-supplier-enquiry/supplierEnquiryEdit/submitSupplierEnquiry'
    resp = requests.post(url, headers=get_headers(company), json=quote_request, timeout=30)
    return handle_qpl_response(resp, company)


def query_mercedes_service_silent(oe_list):
    """
    静默查询奔驰服务（抑制print），第一个成功就返回

    Args:
        oe_list: OE列表

    Returns:
        dict: 奔驰服务返回结果，失败返回None
    """
    for oe in oe_list:
        try:
            # 抑制奔驰服务的冗长输出
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = by_part_number_get_data(oe)
            if result and result.get('part_info'):
                return result
        except Exception:
            continue

    return None


def query_mercedes_service_all(oe_list):
    """
    查询所有OE的价格和库存信息

    Args:
        oe_list: OE列表（去重后）

    Returns:
        dict: {oe: {'wholesale_price': xxx, 'stock_info': [...]}, ...}
    """
    oe_price_map = {}
    for oe in oe_list:
        try:
            # 抑制奔驰服务的冗长输出
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = by_part_number_get_data(oe)
            if result and result.get('part_info'):
                oe_price_map[oe] = {
                    'wholesale_price': result['part_info'].get('wholesale_price', 0),
                    'stock_info': result.get('stock_info', [])
                }
        except Exception:
            continue
    return oe_price_map


# 宝马库房字段到城市名的映射
_BMW_STOCK_FIELDS = [
    '库房-北京',
    '库房-上海',
    '库房-佛山',
    '库房-成都',
    '库房-沈阳',
    '库房-合肥',
    '库房-宁波',
]


def _parse_bmw_net_price(detail_data):
    """从宝马详情中提取经销商净值(Stock)数值"""
    price_str = detail_data.get('经销商净值(Stock)', '')
    if not price_str:
        return 0
    try:
        return float(str(price_str).replace('RMB', '').strip())
    except (ValueError, TypeError):
        return 0


def _filter_processed_orders(order_nos, company, begin_date, end_date):
    """
    查询数据库，过滤掉已处理过的订单

    Returns:
        set: 已存在的订单号集合
    """
    if not order_nos:
        return set()

    from app.utils.database_connection import get_db_connection

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(order_nos))
            sql = f"""
                SELECT DISTINCT supplier_enquiry_no
                FROM qpl_quote_record
                WHERE company = %s
                  AND supplier_enquiry_no IN ({placeholders})
                  AND submit_time >= %s
                  AND submit_time <= %s
            """
            params = [company] + list(order_nos) + [f"{begin_date} 00:00:00", f"{end_date} 23:59:59"]
            cursor.execute(sql, params)
            return set(row[0] for row in cursor.fetchall())
    except Exception as e:
        qpl_log(f"[{company}] 查询已处理订单失败: {e}")
        return set()
    finally:
        if conn:
            conn.close()


def query_bmw_service_all(oe_list):
    """
    查询所有OE的宝马价格和库存信息

    Args:
        oe_list: OE列表（去重后）

    Returns:
        tuple: (oe_price_map, has_request_error, has_price_but_no_stock, has_invalid_price)
            - oe_price_map: {oe: {'net_price': xxx, 'stock_info': [...]}, ...}
            - has_request_error: 是否有OE请求异常
            - has_price_but_no_stock: 是否查到了价格但都没库存
            - has_invalid_price: 是否返回了数据但价格无效
    """
    oe_price_map = {}
    has_request_error = False
    has_price_but_no_stock = False
    has_invalid_price = False

    for oe in oe_list:
        try:
            result = external_data_crawler(oe)
            stock_data = result.get('stock') or {}
            detail_data = result.get('detail') or {}

            # 如果 detail 和 stock 都为空，视为未获取到有效数据
            if not detail_data and not stock_data:
                has_request_error = True
                continue

            net_price = _parse_bmw_net_price(detail_data)
            if net_price <= 0:
                has_invalid_price = True
                continue

            stock_info = []
            for field in _BMW_STOCK_FIELDS:
                qty_str = stock_data.get(field, '0')
                try:
                    qty = int(float(str(qty_str).strip() or '0'))
                except (ValueError, TypeError):
                    qty = 0
                if qty > 0:
                    city = field.replace('库房-', '')
                    stock_info.append({'warehouse': city, 'quantity_available': qty})

            if not stock_info:
                has_price_but_no_stock = True
                continue

            oe_price_map[oe] = {
                'net_price': net_price,
                'stock_info': stock_info
            }
        except Exception:
            has_request_error = True
            continue

    return oe_price_map, has_request_error, has_price_but_no_stock, has_invalid_price


def select_bmw_warehouse_and_days(stock_info):
    """
    选择宝马仓库并确定备货时效
    佛山有货 → 2天
    其他有货城市 → 7天
    """
    available_warehouses = [
        s for s in stock_info
        if s.get('quantity_available', 0) > 0
    ]

    if not available_warehouses:
        return None, None

    foshan = next((s for s in available_warehouses
                   if str(s.get('warehouse', '')) == '佛山'), None)
    if foshan:
        return foshan, 2

    return available_warehouses[0], 7


def _validate_adapt_list(enquiry_item_id, enquiry_no, company):
    """
    步骤1-2：适配列表校验

    Returns:
        tuple: (data, error)
            - data: {'brand': factory_brand, 'products': factory_product_list} 或 None
            - error: 错误信息字符串 或 None
    """
    adapt_result = get_adapt_product_brand(enquiry_item_id, enquiry_no, company)
    brand_list = adapt_result.get('data', {}).get('brandList', [])

    factory_brand = next((b for b in brand_list if b.get('brandTypeDesc') == '原厂'), None)
    if not factory_brand:
        return None, "适配列表为空，无原厂产品"

    factory_product_list = factory_brand.get('productList', [])
    if not factory_product_list:
        return None, "适配列表为空，无原厂产品"

    return {'brand': factory_brand, 'products': factory_product_list}, None


def _get_best_price_info(product, oe_price_map):
    """
    为单个产品获取最优价格信息（含库存检查）

    按价格从低到高遍历，选择第一个有库存的OE。

    Args:
        product: 产品信息
        oe_price_map: OE价格映射

    Returns:
        dict: 包含价格、库存等信息，无可用价格或库存时返回None
    """
    product_oes = product.get('productOeList', [])
    product_pid = product.get('pid', '')

    # 收集有价格的OE并按价格升序排序
    priced_oes = []
    for oe in product_oes:
        if oe in oe_price_map:
            priced_oes.append({
                'price': oe_price_map[oe]['wholesale_price'],
                'stock': oe_price_map[oe]['stock_info'],
                'oe': oe
            })

    if not priced_oes:
        return None

    priced_oes.sort(key=lambda x: x['price'])

    # 按价格从低到高，找第一个有库存的OE
    for candidate in priced_oes:
        selected_warehouse, _ = select_warehouse_and_days(candidate['stock'])
        if selected_warehouse:
            return {
                'pid': product_pid,
                'sell_price': round(candidate['price'] * 1.09),
                'stock_info': candidate['stock'],
                'oe': candidate['oe']
            }

    return None


def _get_best_price_info_bmw(product, oe_price_map):
    """
    为单个宝马产品获取最优价格信息（含库存检查）

    按价格从低到高遍历，选择第一个有库存的OE，库存中优先选择佛山仓库。

    Args:
        product: 产品信息
        oe_price_map: OE价格映射（来自 query_bmw_service_all）

    Returns:
        dict: 包含价格、库存等信息，无可用价格或库存时返回None
    """
    product_oes = product.get('productOeList', [])
    product_pid = product.get('pid', '')

    # 收集有价格的OE并按价格升序排序
    priced_oes = []
    for oe in product_oes:
        if oe in oe_price_map:
            priced_oes.append({
                'price': oe_price_map[oe]['net_price'],
                'stock': oe_price_map[oe]['stock_info'],
                'oe': oe
            })

    if not priced_oes:
        return None

    priced_oes.sort(key=lambda x: x['price'])

    # 按价格从低到高，找第一个有库存的OE
    for candidate in priced_oes:
        selected_warehouse, _ = select_bmw_warehouse_and_days(candidate['stock'])
        if selected_warehouse:
            return {
                'pid': product_pid,
                'sell_price': round(BMW_PRICE_FORMULA(candidate['price'])),
                'stock_info': candidate['stock'],
                'oe': candidate['oe']
            }

    return None


def _run_price_check(product, product_info, tid, car_brand, enquiry_no, enquiry_item_id, company):
    """
    对单个产品执行priceCheck

    Returns:
        tuple: (snapshot, error)
            - snapshot: priceCheck成功时的快照数据
            - error: 错误信息字符串，成功时为None
    """
    req_item = {
        "translationOE": product.get('itemPerhapsReplaceOe', ''),
        "chainType": None,
        "chainId": None,
        "pid": product_info['pid'],
        "price": product_info['sell_price'],
        "quality": product.get('quality', 1),
        "productNum": 1,
        "brandName": product.get('brandName', ''),
        "queryProductBrandId": product.get('brandId', ''),
        "uid": None,
        "supplierEnquiryItemId": enquiry_item_id,
        "regionalDistributionType": None,
        "productName": product.get('displaceProductName', ''),
        "qualityTypeId": product.get('qualityTypeId', ''),
        "brandOwnerId": "",
        "quoteTaxType": "INCLUSIVE"
    }

    result = price_check([req_item], tid, car_brand, enquiry_no, company)

    if not result or result.get('code') != 10000:
        return None, result.get('message', '无响应') if result else '无响应'

    check_data = result.get('data', [])
    if not check_data:
        return None, '无校验结果'

    check_item = check_data[0]
    if check_item.get('checkResult') != 'SUCCESS' or check_item.get('checkMessage'):
        return None, check_item.get('checkMessage', 'FAIL')

    return check_item.get('priceCheckSnapshot'), None


def process_mercedes_order(detail_data, company='fsbbr'):
    """
    处理奔驰车订单（管道式重构）

    Args:
        detail_data: 询价单详情数据
        company: 组织代码

    Returns:
        tuple: (mercedes_quote_items, summary_list, failed_items)
    """
    if not MERCEDES_SERVICE_AVAILABLE:
        return {}, [], {}

    mercedes_quote_items = {}
    summary_list = []
    failed_items = {}
    enquiry_no = detail_data.get('supplierEnquiryNo', '')
    tid = detail_data.get('tid', '')
    car_brand = detail_data.get('carBrand', '')

    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            enquiry_item_id = item.get('enquiryItemId')
            item_oe = item.get('itemOe')
            item_name = item.get('itemName')
            quote_status = item.get('quoteStatus')

            if str(quote_status).strip() != 'WAITING_QUOTE':
                continue

            # 提取 category_id
            sale_category_path = item.get('saleCategoryPathId', '/5/')
            path_parts = sale_category_path.split('/')
            category_id = f"/{path_parts[1]}/" if len(path_parts) >= 2 and path_parts[1] else "/5/"

            try:
                # 适配列表校验
                adapt_data, error = _validate_adapt_list(enquiry_item_id, enquiry_no, company)
                if error:
                    failed_items[enquiry_item_id] = error
                    continue

                factory_brand = adapt_data['brand']
                factory_product_list = adapt_data['products']

                # 查询价格
                product_oe_list = list(set(
                    oe for p in factory_product_list for oe in p.get('productOeList', [])
                ))
                if not product_oe_list:
                    failed_items[enquiry_item_id] = "适配列表为空，无原厂产品"
                    continue

                oe_price_map = query_mercedes_service_all(product_oe_list)
                if not oe_price_map:
                    failed_items[enquiry_item_id] = "零件信息请求失败"
                    continue

                # 筛选有价格+库存的产品
                valid_products = []
                for product in factory_product_list:
                    info = _get_best_price_info(product, oe_price_map)
                    if info:
                        valid_products.append({'product': product, 'info': info})

                if not valid_products:
                    failed_items[enquiry_item_id] = "无可用价格或库存"
                    continue

                # priceCheck校验
                price_check_errors = []
                passed_products = []

                for vp in valid_products:
                    product = vp['product']
                    product_info = vp['info']

                    snapshot, error = _run_price_check(
                        product, product_info, tid, car_brand,
                        enquiry_no, enquiry_item_id, company
                    )

                    if error:
                        price_check_errors.append(f"{product.get('brandName', '未知品牌')} {product.get('itemPerhapsReplaceOe', '未知OE')}: {error}")
                    else:
                        passed_products.append({
                            'product': product,
                            'info': product_info,
                            'snapshot': snapshot
                        })

                if not passed_products:
                    failed_items[enquiry_item_id] = "；".join(price_check_errors)
                    continue

                # 构造报价项
                quote_items_for_item = []
                for pp in passed_products:
                    _, prepare_good_timespan = select_warehouse_and_days(pp['info']['stock_info'])
                    quote_item = construct_adapter_quote_item(
                        factory_brand, pp['product'], factory_product_list,
                        pp['info']['sell_price'], prepare_good_timespan,
                        pp['snapshot'], category_id
                    )
                    quote_items_for_item.append(quote_item)

                mercedes_quote_items[enquiry_item_id] = quote_items_for_item

                # 收集汇总信息
                last_pp = passed_products[-1]
                summary_list.append({
                    'item_oe': item_oe,
                    'item_name': item_name,
                    'price': last_pp['info']['sell_price'],
                    'days': prepare_good_timespan,
                    'product_count': len(quote_items_for_item)
                })

            except Exception as e:
                failed_items[enquiry_item_id] = f"处理异常: {str(e)}"
                continue

    # 兜底：确保所有 WAITING_QUOTE item 都有处理结果
    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            item_id = item.get('enquiryItemId')
            if (str(item.get('quoteStatus', '')).strip() == 'WAITING_QUOTE' and
                item_id not in mercedes_quote_items and
                item_id not in failed_items):
                failed_items[item_id] = "程序未处理"

    return mercedes_quote_items, summary_list, failed_items


def process_bmw_order(detail_data, company='fsbbr'):
    """
    处理宝马车订单（管道式重构）

    Args:
        detail_data: 询价单详情数据
        company: 组织代码

    Returns:
        tuple: (bmw_quote_items, summary_list, failed_items)
    """
    if not BMW_SERVICE_AVAILABLE:
        return {}, [], {}

    bmw_quote_items = {}
    summary_list = []
    failed_items = {}
    enquiry_no = detail_data.get('supplierEnquiryNo', '')
    tid = detail_data.get('tid', '')
    car_brand = detail_data.get('carBrand', '')

    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            enquiry_item_id = item.get('enquiryItemId')
            item_oe = item.get('itemOe')
            item_name = item.get('itemName')
            quote_status = item.get('quoteStatus')

            if str(quote_status).strip() != 'WAITING_QUOTE':
                continue

            # 提取 category_id
            sale_category_path = item.get('saleCategoryPathId', '/5/')
            path_parts = sale_category_path.split('/')
            category_id = f"/{path_parts[1]}/" if len(path_parts) >= 2 and path_parts[1] else "/5/"

            try:
                # 适配列表校验
                adapt_data, error = _validate_adapt_list(enquiry_item_id, enquiry_no, company)
                if error:
                    failed_items[enquiry_item_id] = error
                    continue

                factory_brand = adapt_data['brand']
                factory_product_list = adapt_data['products']

                # 查询价格
                product_oe_list = list(set(
                    oe for p in factory_product_list for oe in p.get('productOeList', [])
                ))
                if not product_oe_list:
                    failed_items[enquiry_item_id] = "适配列表为空，无原厂产品"
                    continue

                oe_price_map, has_request_error, has_price_but_no_stock, has_invalid_price = query_bmw_service_all(product_oe_list)
                if not oe_price_map:
                    if has_request_error:
                        failed_items[enquiry_item_id] = "零件信息请求失败"
                    elif has_price_but_no_stock:
                        failed_items[enquiry_item_id] = "无可用库存"
                    elif has_invalid_price:
                        failed_items[enquiry_item_id] = "价格无效"
                    else:
                        failed_items[enquiry_item_id] = "未知错误"
                    continue

                # 筛选有价格+库存的产品
                valid_products = []
                for product in factory_product_list:
                    info = _get_best_price_info_bmw(product, oe_price_map)
                    if info:
                        valid_products.append({'product': product, 'info': info})

                if not valid_products:
                    failed_items[enquiry_item_id] = "无可用价格或库存"
                    continue

                # priceCheck校验
                price_check_errors = []
                passed_products = []

                for vp in valid_products:
                    product = vp['product']
                    product_info = vp['info']

                    snapshot, error = _run_price_check(
                        product, product_info, tid, car_brand,
                        enquiry_no, enquiry_item_id, company
                    )

                    if error:
                        price_check_errors.append(f"{product.get('brandName', '未知品牌')} {product.get('itemPerhapsReplaceOe', '未知OE')}: {error}")
                    else:
                        passed_products.append({
                            'product': product,
                            'info': product_info,
                            'snapshot': snapshot
                        })

                if not passed_products:
                    failed_items[enquiry_item_id] = "；".join(price_check_errors)
                    continue

                # 构造报价项
                quote_items_for_item = []
                for pp in passed_products:
                    _, prepare_good_timespan = select_bmw_warehouse_and_days(pp['info']['stock_info'])
                    quote_item = construct_adapter_quote_item(
                        factory_brand, pp['product'], factory_product_list,
                        pp['info']['sell_price'], prepare_good_timespan,
                        pp['snapshot'], category_id
                    )
                    quote_items_for_item.append(quote_item)

                bmw_quote_items[enquiry_item_id] = quote_items_for_item

                # 收集汇总信息
                last_pp = passed_products[-1]
                summary_list.append({
                    'item_oe': item_oe,
                    'item_name': item_name,
                    'price': last_pp['info']['sell_price'],
                    'days': prepare_good_timespan,
                    'product_count': len(quote_items_for_item)
                })

            except Exception as e:
                failed_items[enquiry_item_id] = f"处理异常: {str(e)}"
                continue

    # 兜底：确保所有 WAITING_QUOTE item 都有处理结果
    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            item_id = item.get('enquiryItemId')
            if (str(item.get('quoteStatus', '')).strip() == 'WAITING_QUOTE' and
                item_id not in bmw_quote_items and
                item_id not in failed_items):
                failed_items[item_id] = "程序未处理"

    return bmw_quote_items, summary_list, failed_items


def classify_order(order_data):
    """
    对订单进行分类，返回类别标识

    Returns:
        str: 'A' = 全PART_QUOTE, 'B' = 奔驰+未报价, 'C' = 宝马+未报价, 'SKIP' = 普通车+未报价
    """
    car_type5 = order_data.get('carType5', '')
    items = []
    # 列表接口：项目可能在顶层 supplierEnquiryItemList
    items.extend(order_data.get('supplierEnquiryItemList', []))
    # 详情接口：项目在 supplierEnquiryDemandList 下
    for demand in order_data.get('supplierEnquiryDemandList', []):
        items.extend(demand.get('supplierEnquiryItemList', []))

    has_waiting = any(str(item.get('quoteStatus', '')).strip() == 'WAITING_QUOTE' for item in items)
    if not has_waiting:
        return 'A'

    is_mercedes = car_type5.startswith('奔驰') if car_type5 else False
    if is_mercedes:
        return 'B'

    is_bmw = car_type5.startswith('宝马') if car_type5 else False
    if is_bmw:
        return 'C'

    return 'SKIP'


ORDER_HANDLERS = {}


def register_handler(category):
    """装饰器：注册类别处理器"""
    def decorator(func):
        ORDER_HANDLERS[category] = func
        return func
    return decorator


@register_handler('A')
def handle_category_a(detail_data, company):
    """处理 A 类订单：全 PART_QUOTE，无需第三方处理"""
    return {
        'extra_quote_items': {},
        'summary_list': [],
        'failed_items': {},
        'category': 'A'
    }


@register_handler('B')
def handle_category_b(detail_data, company):
    """处理 B 类订单：奔驰车 + 有 WAITING_QUOTE"""
    mercedes_quote_items, summary_list, failed_items = process_mercedes_order(detail_data, company)
    return {
        'extra_quote_items': mercedes_quote_items,
        'summary_list': summary_list,
        'failed_items': failed_items,
        'category': 'B'
    }


@register_handler('C')
def handle_category_c(detail_data, company):
    """处理 C 类订单：宝马车 + 有 WAITING_QUOTE"""
    bmw_quote_items, summary_list, failed_items = process_bmw_order(detail_data, company)
    return {
        'extra_quote_items': bmw_quote_items,
        'summary_list': summary_list,
        'failed_items': failed_items,
        'category': 'C'
    }


def process_order_by_category(detail_data, company):
    """根据订单类别分发处理"""
    category = classify_order(detail_data)
    if category == 'SKIP':
        return {
            'extra_quote_items': {},
            'summary_list': [],
            'failed_items': {},
            'category': 'SKIP'
        }
    handler = ORDER_HANDLERS[category]
    return handler(detail_data, company)


def _has_any_quote(detail_data, extra_quote_items):
    """判断订单中是否已有任何报价（包括已有报价和自动构造的报价）"""
    if extra_quote_items:
        return True
    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            if item.get('supplierQuoteItemList'):
                return True
    return False


def submit_all_quotes(begin_date=None, end_date=None, company='fsbbr'):
    """
    提交所有符合条件的报价

    处理优先级:
        1. A类: 全PART_QUOTE订单 (最快路径)
        2. B类: 奔驰车+有未报价项目 (需查奔驰接口)
        3. C类: 宝马车+有未报价项目 (需查宝马接口)
        跳过: 普通车+有未报价项目

    Args:
        begin_date: 开始日期，格式 'YYYY-MM-DD'，默认2天前
        end_date: 结束日期，格式 'YYYY-MM-DD'，默认今天
        company: 组织代码，默认fsbbr

    Returns:
        list: 报价结果列表
    """
    if begin_date is None:
        begin_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    result = query_enquiry_list(begin_date, end_date, company=company)
    orders = result.get('data') or []

    unique_orders = {order.get('supplierEnquiryNo'): order for order in orders if order.get('supplierEnquiryNo')}
    total_orders = len(unique_orders)

    # 过滤已处理订单
    processed_nos = _filter_processed_orders(list(unique_orders.keys()), company, begin_date, end_date)
    if processed_nos:
        for order_no in processed_nos:
            unique_orders.pop(order_no, None)

    # 分类并统计
    category_counts = {'A': 0, 'B': 0, 'C': 0, 'SKIP': 0}
    categorized = []
    for enquiry_no, order in unique_orders.items():
        category = classify_order(order)
        category_counts[category] += 1
        if category == 'SKIP':
            continue
        categorized.append((category, enquiry_no))

    # 按类别排序：A 在前，B/C 在后
    category_order = {'A': 0, 'B': 1, 'C': 1}
    categorized.sort(key=lambda x: category_order.get(x[0], 2))

    qpl_log(
        f"[{company}] 任务开始 | 找到{total_orders}个订单 已处理{len(processed_nos)}个 "
        f"跳过{category_counts['SKIP']}个 待处理{len(categorized)}个 "
        f"类别=A:{category_counts['A']} B:{category_counts['B']} C:{category_counts['C']}"
    )

    results = []

    for idx, (category, enquiry_no) in enumerate(categorized, start=1):
        detail = get_enquiry_detail(enquiry_no, company=company)
        detail_data = detail.get('data', {})

        # 获取取货方式（传入 tuhuSupplierId）
        shop_uid = detail_data.get('shopUid')
        tuhu_supplier_id = detail_data.get('tuhuSupplierId')
        if shop_uid and enquiry_no:
            pickup_result = get_pickup_way_and_distance(shop_uid, enquiry_no, tuhu_supplier_id, company)
            pickup_info = extract_pickup_info(pickup_result)
            detail_data.update(pickup_info)

        # 按类别处理订单（字典分发，直接使用已知 category）
        handler = ORDER_HANDLERS[category]
        process_result = handler(detail_data, company)

        extra_quote_items = process_result['extra_quote_items']
        summary_list = process_result['summary_list']
        failed_items = process_result['failed_items']
        order_category = process_result['category']

        # 订单日志前缀
        order_prefix = f"[{company}] [{idx}/{len(categorized)}] [{order_category}类]"

        # 构建 item_id -> (oe, status) 映射
        item_info_map = {}
        for demand in detail_data.get('supplierEnquiryDemandList', []):
            for item in demand.get('supplierEnquiryItemList', []):
                item_info_map[item.get('enquiryItemId')] = {
                    'oe': item.get('itemOe') or 'None',
                    'status': item.get('quoteStatus')
                }

        # B/C 类订单：存在未报价成功的 item 时
        has_any_quote = _has_any_quote(detail_data, extra_quote_items)
        if order_category in ('B', 'C') and failed_items:
            # 打印未报价项信息
            failed_desc = "; ".join(
                f"oe={item_info_map.get(item_id, {}).get('oe', '未知')} "
                f"status={item_info_map.get(item_id, {}).get('status', '未知')} 原因={reason}"
                for item_id, reason in failed_items.items()
            )
            qpl_log(f"{order_prefix}: 未报价 {failed_desc}", order_no=enquiry_no)

            # 没有任何报价项，且所有失败原因都是"适配列表为空，无原厂产品"，则调用 cannotQuote
            if not has_any_quote and all(
                reason == '适配列表为空，无原厂产品' for reason in failed_items.values()
            ):
                try:
                    cannot_quote_resp = cannot_quote(
                        enquiry_no,
                        list(failed_items.keys()),
                        close_reason=16,
                        close_remarks='',
                        company=company
                    )
                    resp_code = cannot_quote_resp.get('code')
                    resp_msg = cannot_quote_resp.get('message', '')

                    if resp_code == 10000:
                        qpl_log(
                            f"{order_prefix}: cannotQuote 调用成功: {resp_msg}",
                            order_no=enquiry_no
                        )
                        results.append({
                            'enquiry_no': enquiry_no,
                            'order_category': order_category,
                            'success': True,
                            'message': f"cannotQuote成功: {resp_msg}",
                            'detail_data': detail_data,
                            'quote_request': None,
                            'extra_quote_items': extra_quote_items,
                            'summary_list': summary_list,
                            'failed_items': failed_items,
                            'submit_time': datetime.now(),
                            'company': company
                        })
                    else:
                        resp_text = json.dumps(cannot_quote_resp, ensure_ascii=False)
                        qpl_log(
                            f"{order_prefix}: cannotQuote 调用失败: code={resp_code} 响应={resp_text}",
                            order_no=enquiry_no
                        )
                        results.append({
                            'enquiry_no': enquiry_no,
                            'order_category': order_category,
                            'success': False,
                            'message': f"cannotQuote失败: {resp_text}",
                            'detail_data': detail_data,
                            'quote_request': None,
                            'extra_quote_items': extra_quote_items,
                            'summary_list': summary_list,
                            'failed_items': failed_items,
                            'submit_time': datetime.now(),
                            'company': company
                        })
                except Exception as e:
                    # 失败时打印完整异常
                    qpl_log(
                        f"{order_prefix}: cannotQuote 调用失败: {str(e)}",
                        order_no=enquiry_no
                    )
                    results.append({
                        'enquiry_no': enquiry_no,
                        'order_category': order_category,
                        'success': False,
                        'message': f"cannotQuote失败: {str(e)}",
                        'detail_data': detail_data,
                        'quote_request': None,
                        'extra_quote_items': extra_quote_items,
                        'summary_list': summary_list,
                        'failed_items': failed_items,
                        'submit_time': datetime.now(),
                        'company': company
                    })
                continue
            elif not has_any_quote:
                # 没有任何报价项，但失败原因不全是适配列表为空，跳过
                qpl_log(f"{order_prefix}: 跳过，存在未报价项", order_no=enquiry_no)
                results.append({
                    'enquiry_no': enquiry_no,
                    'order_category': order_category,
                    'success': False,
                    'message': f"存在未报价项: {list(failed_items.keys())}",
                    'detail_data': detail_data,
                    'quote_request': None,
                    'extra_quote_items': extra_quote_items,
                    'summary_list': summary_list,
                    'failed_items': failed_items,
                    'submit_time': datetime.now(),
                    'company': company
                })
                continue
            # else: 有报价项，继续正常提交（已有报价 + 自动报价）

        # 构造报价请求体
        quote_request = construct_quote_request(detail_data, extra_quote_items)

        # 实际提交
        submit_response = submit_quote(quote_request, company)
        submit_success = submit_response.get('code') == 10000
        submit_message = submit_response.get('message', '未知响应')

        qpl_log(f"{order_prefix}: 提交{'成功' if submit_success else '失败'} - {submit_message}", order_no=enquiry_no)

        results.append({
            'enquiry_no': enquiry_no,
            'order_category': order_category,
            'success': submit_success,
            'message': submit_message,
            'detail_data': detail_data,
            'quote_request': quote_request,
            'extra_quote_items': extra_quote_items,
            'summary_list': summary_list,
            'failed_items': failed_items,
            'submit_time': datetime.now(),
            'company': company
        })

    # 任务完成统计
    processed_category_counts = {'A': 0, 'B': 0, 'C': 0}
    for result in results:
        processed_category_counts[result['order_category']] += 1
    qpl_log(
        f"[{company}] 任务完成 | 找到{total_orders}个订单 已处理{len(processed_nos)}个 "
        f"跳过{category_counts['SKIP']}个 待处理{len(results)}个 "
        f"类别=A:{processed_category_counts['A']} B:{processed_category_counts['B']} C:{processed_category_counts['C']}"
    )

    return results


def main(company='fsbbr'):
    """独立脚本入口"""
    submit_all_quotes(company=company)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
