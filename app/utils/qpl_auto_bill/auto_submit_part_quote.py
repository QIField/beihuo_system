#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""自动提交部分报价订单"""

import sys
import os
import json
import io
import math
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
    construct_quote_request,
    construct_adapter_quote_item,
    construct_crm_quote_item,
    select_warehouse_and_days,
    MERCEDES_WAREHOUSE_MAP
)
from qpl_config import (
    BASE_URL, get_headers, handle_qpl_response, BMW_PRICE_FORMULA, qpl_log,
    COMPANY_CRM_COOKIES_KEY_MAP
)
from brand_match_config import get_crm_brand_names

try:
    from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
    CRM_SPIDER_AVAILABLE = True
except ImportError:
    CRM_SPIDER_AVAILABLE = False
    print("[汽配龙自动报价] CRM 爬虫模块未找到")

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


# 失败原因常量
FAIL_NO_ORIGINAL_PRODUCT = "适配列表为空，无原厂产品"
FAIL_OE_DATA_MISSING = "零件信息请求失败"
FAIL_NO_VALID_OE_FOR_PRODUCT = "当前产品无可用OE"
FAIL_NO_STOCK = "无可用库存"
FAIL_INVALID_PRICE = "价格无效"
FAIL_PART_NO_MISMATCH = "partNo未匹配"
FAIL_NO_EFFECTIVE_PRICE = "无有效价格"
FAIL_PRICE_CHECK_FAILED = "价格校验失败"
FAIL_PROGRAM_UNPROCESSED = "程序未处理"


# 通用工具函数
def _iter_enquiry_items(order_data):
    """统一遍历订单中的 item（兼容列表接口和详情接口）"""
    for item in order_data.get('supplierEnquiryItemList', []):
        yield item
    for demand in order_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            yield item


def _extract_category_id(item, default="/5/"):
    """从 item 的 saleCategoryPathId 中提取 category_id"""
    sale_category_path = item.get('saleCategoryPathId', default)
    path_parts = sale_category_path.split('/')
    if len(path_parts) >= 2 and path_parts[1]:
        return f"/{path_parts[1]}/"
    return default


def _format_price_check_error(product, error):
    """格式化 priceCheck 失败信息"""
    brand = product.get('brandName', '未知品牌')
    oe = product.get('itemPerhapsReplaceOe') or product.get('oe', '未知OE')
    return f"{brand} {oe}: {error}"


def _ensure_waiting_items_covered(detail_data, quote_items, failed_items):
    """兜底：确保所有 WAITING_QUOTE item 都有处理结果"""
    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            item_id = item.get('enquiryItemId')
            if (str(item.get('quoteStatus', '')).strip() == 'WAITING_QUOTE' and
                item_id not in quote_items and
                item_id not in failed_items):
                failed_items[item_id] = FAIL_PROGRAM_UNPROCESSED


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
    查询所有OE的宝马价格和库存信息（改为只读本地库）

    Args:
        oe_list: OE列表（去重后）

    Returns:
        tuple: (oe_price_map, has_request_error, has_price_but_no_stock, has_invalid_price)
            - oe_price_map: {oe: {'net_price': xxx, 'stock_info': [...]}, ...}
            - has_request_error: 是否有OE缺失于本地库
            - has_price_but_no_stock: 是否查到了价格但都没库存
            - has_invalid_price: 是否返回了数据但价格无效
    """
    from app.utils.qpl_auto_bill.bmw_quote_local_db import check_bmw_oes_in_local_db

    oe_price_map, status = check_bmw_oes_in_local_db(list(set(oe_list)))
    has_request_error = len(status.get('missing', [])) > 0
    has_price_but_no_stock = len(status.get('no_stock', [])) > 0
    has_invalid_price = len(status.get('invalid_price', [])) > 0
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
        return None, FAIL_NO_ORIGINAL_PRODUCT

    factory_product_list = factory_brand.get('productList', [])
    if not factory_product_list:
        return None, FAIL_NO_ORIGINAL_PRODUCT

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


def _get_crm_spider(company='fsbbr'):
    """
    根据组织代码获取 CRM 爬虫实例

    Returns:
        CrmGzbbrSpider: CRM 爬虫实例
    """
    cookies_key = COMPANY_CRM_COOKIES_KEY_MAP.get(company, 'fs')
    return CrmGzbbrSpider(cookies_key=cookies_key)


def process_crm_spot_quote(detail_data, company='fsbbr'):
    """
    CRM 现货优先报价流程

    针对每个 WAITING_QUOTE 项目：
    1. 从适配列表获取所有品牌下的候选产品（pid 未在询价详情中出现）
    2. 调用 CRM 接口查询库存和价格（is_stock=1）
    3. 按品牌 + partNo 匹配，命中且 qpl_price 有效则向上取整
    4. 调 priceCheck 校验
    5. 构造现货报价项

    Args:
        detail_data: 询价单详情数据
        company: 组织代码

    Returns:
        tuple: (crm_quote_items, original_quoted_ids, crm_failed_items)
            - crm_quote_items: {enquiry_item_id: [quote_item, ...]}
            - original_quoted_ids: CRM 报上原厂品牌的 enquiry_item_id 集合
            - crm_failed_items: {enquiry_item_id: reason}
    """
    if not CRM_SPIDER_AVAILABLE:
        return {}, set(), {}

    crm_quote_items = {}
    original_quoted_ids = set()
    crm_failed_items = {}

    enquiry_no = detail_data.get('supplierEnquiryNo', '')
    tid = detail_data.get('tid', '')
    car_brand = detail_data.get('carBrand', '')

    # 收集询价详情中已有的 pid
    existing_pids = set()
    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            for quote in item.get('supplierQuoteItemList', []):
                pid = quote.get('pid')
                if pid:
                    existing_pids.add(pid)

    spider = _get_crm_spider(company)

    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            enquiry_item_id = item.get('enquiryItemId')
            item_oe = item.get('itemOe')
            quote_status = item.get('quoteStatus')

            if str(quote_status).strip() != 'WAITING_QUOTE':
                continue

            try:
                adapt_result = get_adapt_product_brand(enquiry_item_id, enquiry_no, company)
                brand_list = adapt_result.get('data', {}).get('brandList', [])

                if not brand_list:
                    continue

                # 构建候选产品：遍历适配列表所有品牌
                candidates = []
                for brand in brand_list:
                    brand_name = brand.get('brandName', '')
                    brand_type_desc = brand.get('brandTypeDesc', '')
                    for product in brand.get('productList', []):
                        pid = product.get('pid')
                        if not pid or pid in existing_pids:
                            continue
                        candidates.append({
                            'brand': brand,
                            'brand_name': brand_name,
                            'brand_type_desc': brand_type_desc,
                            'product': product,
                            'pid': pid,
                            'part_no': product.get('partNo') or '',
                        })

                if not candidates:
                    continue

                # 该 item 是否包含原厂品牌候选
                item_has_original_candidate = any(
                    c['brand_type_desc'] == '原厂' for c in candidates
                )

                # 调用 CRM 接口
                response = spider.get_product_product_list(numberlist=item_oe, is_stock="1")
                if response.status_code != 200:
                    continue

                crm_data = response.json()
                if crm_data.get('status') != 200:
                    continue

                crm_products = []
                for group in crm_data.get('data', {}).get('data', []):
                    crm_products.extend(group.get('child', []))

                if not crm_products:
                    continue

                category_id = _extract_category_id(item)

                quoted_for_item = []
                has_original = False
                max_failure_stage = 0  # 0=品牌, 1=partNo, 2=价格, 3=价格校验

                for candidate in candidates:
                    brand = candidate['brand']
                    product = candidate['product']
                    brand_name = candidate['brand_name']
                    brand_type_desc = candidate['brand_type_desc']
                    part_no = candidate['part_no']

                    crm_brand_names = get_crm_brand_names(brand_name, brand_type_desc)

                    brand_matched_products = []
                    for crm_product in crm_products:
                        crm_brand_name = str(crm_product.get('brand_name', '')).strip()
                        if crm_brand_name in crm_brand_names:
                            brand_matched_products.append(crm_product)

                    if not brand_matched_products:
                        continue

                    # 有品牌匹配
                    if part_no:
                        max_failure_stage = max(max_failure_stage, 1)
                    else:
                        max_failure_stage = max(max_failure_stage, 2)

                    # 再按 partNo 严格匹配
                    if part_no:
                        matched_crm_products = []
                        for crm_product in brand_matched_products:
                            crm_brand_code = str(crm_product.get('brand_code', '') or '').strip()
                            crm_frey_no = str(crm_product.get('frey_no', '') or '').strip()
                            if part_no == crm_brand_code or part_no == crm_frey_no:
                                matched_crm_products.append(crm_product)
                    else:
                        matched_crm_products = brand_matched_products

                    if not matched_crm_products:
                        continue

                    # partNo 匹配（或无 partNo 要求）
                    max_failure_stage = max(max_failure_stage, 2)

                    crm_product = matched_crm_products[0]
                    qpl_price_str = crm_product.get('qpl_price', '')
                    if not qpl_price_str:
                        continue

                    try:
                        qpl_price = float(str(qpl_price_str).strip())
                    except (ValueError, TypeError):
                        continue

                    if qpl_price <= 0:
                        continue

                    # 有有效价格
                    max_failure_stage = max(max_failure_stage, 3)
                    sell_price = math.ceil(qpl_price)

                    product_info = {
                        'pid': candidate['pid'],
                        'sell_price': sell_price,
                        'stock_info': [],
                        'oe': item_oe
                    }
                    snapshot, error = _run_price_check(
                        product, product_info, tid, car_brand,
                        enquiry_no, enquiry_item_id, company
                    )

                    if error:
                        continue

                    all_brand_products = brand.get('productList', [])
                    quote_item = construct_crm_quote_item(
                        brand, product, all_brand_products,
                        sell_price, snapshot, category_id
                    )
                    quoted_for_item.append(quote_item)

                    if brand_type_desc == '原厂':
                        has_original = True

                if quoted_for_item:
                    crm_quote_items[enquiry_item_id] = quoted_for_item
                    if has_original:
                        original_quoted_ids.add(enquiry_item_id)
                elif max_failure_stage > 0:
                    # 品牌已匹配但后续失败才记录；品牌未匹配（stage=0）不记录
                    reason_map = {
                        1: "partNo未匹配",
                        2: "无有效价格",
                        3: "价格校验失败",
                    }
                    reason = reason_map.get(max_failure_stage, "CRM未匹配")
                    crm_failed_items[enquiry_item_id] = (reason, item_has_original_candidate)

            except Exception as e:
                qpl_log(f"[{company}] CRM现货流程处理异常: {e}", order_no=enquiry_no)
                continue

    return crm_quote_items, original_quoted_ids, crm_failed_items


def process_mercedes_order(detail_data, company='fsbbr', skip_item_ids=None):
    """
    处理奔驰车订单（管道式重构）

    Args:
        detail_data: 询价单详情数据
        company: 组织代码
        skip_item_ids: 需要跳过的 enquiry_item_id 集合（CRM 已报原厂品牌）

    Returns:
        tuple: (mercedes_quote_items, summary_list, failed_items)
    """
    if not MERCEDES_SERVICE_AVAILABLE:
        return {}, [], {}

    skip_item_ids = skip_item_ids or set()
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

            if str(quote_status).strip() != 'WAITING_QUOTE' or enquiry_item_id in skip_item_ids:
                continue

            category_id = _extract_category_id(item)

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
                    failed_items[enquiry_item_id] = FAIL_NO_ORIGINAL_PRODUCT
                    continue

                oe_price_map = query_mercedes_service_all(product_oe_list)
                if not oe_price_map:
                    failed_items[enquiry_item_id] = FAIL_OE_DATA_MISSING
                    continue

                # 筛选有价格+库存的产品
                valid_products = []
                for product in factory_product_list:
                    info = _get_best_price_info(product, oe_price_map)
                    if info:
                        valid_products.append({'product': product, 'info': info})

                if not valid_products:
                    failed_items[enquiry_item_id] = FAIL_NO_VALID_OE_FOR_PRODUCT
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
                        price_check_errors.append(_format_price_check_error(product, error))
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

    _ensure_waiting_items_covered(detail_data, mercedes_quote_items, failed_items)

    return mercedes_quote_items, summary_list, failed_items


def process_bmw_order(detail_data, company='fsbbr', skip_item_ids=None):
    """
    处理宝马车订单（管道式重构）

    Args:
        detail_data: 询价单详情数据
        company: 组织代码
        skip_item_ids: 需要跳过的 enquiry_item_id 集合（CRM 已报原厂品牌）

    Returns:
        tuple: (bmw_quote_items, summary_list, failed_items)
    """
    if not BMW_SERVICE_AVAILABLE:
        return {}, [], {}

    skip_item_ids = skip_item_ids or set()
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

            if str(quote_status).strip() != 'WAITING_QUOTE' or enquiry_item_id in skip_item_ids:
                continue

            category_id = _extract_category_id(item)

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
                    failed_items[enquiry_item_id] = FAIL_NO_ORIGINAL_PRODUCT
                    continue

                oe_price_map, has_request_error, has_price_but_no_stock, has_invalid_price = query_bmw_service_all(product_oe_list)
                if not oe_price_map:
                    if has_request_error:
                        failed_items[enquiry_item_id] = FAIL_OE_DATA_MISSING
                    elif has_price_but_no_stock:
                        failed_items[enquiry_item_id] = FAIL_NO_STOCK
                    elif has_invalid_price:
                        failed_items[enquiry_item_id] = FAIL_INVALID_PRICE
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
                    failed_items[enquiry_item_id] = FAIL_NO_VALID_OE_FOR_PRODUCT
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
                        price_check_errors.append(_format_price_check_error(product, error))
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

    _ensure_waiting_items_covered(detail_data, bmw_quote_items, failed_items)

    return bmw_quote_items, summary_list, failed_items


def classify_order(order_data):
    """
    对订单进行分类，返回类别标识

    Returns:
        str: 'A' = 全PART_QUOTE, 'B' = 奔驰+未报价, 'C' = 宝马+未报价, 'SKIP' = 普通车+未报价
    """
    car_type5 = order_data.get('carType5', '')
    items = list(_iter_enquiry_items(order_data))

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


def _merge_failed_items(crm_failed_items, bc_quote_items, bc_failed_items):
    """
    合并 CRM 和 B/C 的失败原因

    Args:
        crm_failed_items: {item_id: (reason, is_original)}
        bc_quote_items: {item_id: [quote_item, ...]}
        bc_failed_items: {item_id: reason}

    Returns:
        dict: 合并后的失败原因
    """
    failed_items = dict(bc_failed_items)
    for item_id, (reason, _) in crm_failed_items.items():
        if item_id not in bc_quote_items:
            if item_id in failed_items:
                failed_items[item_id] = f"{reason}; {failed_items[item_id]}"
            else:
                failed_items[item_id] = reason
    return failed_items


def _handle_bc_category(detail_data, company, bc_process_func, category):
    """
    处理 B/C 类订单的通用逻辑（奔驰/宝马）

    Args:
        detail_data: 询价单详情
        company: 组织代码
        bc_process_func: process_mercedes_order 或 process_bmw_order
        category: 'B' 或 'C'

    Returns:
        dict: handler 结果
    """
    crm_quote_items, original_quoted_ids, crm_failed_items = process_crm_spot_quote(detail_data, company)
    bc_quote_items, summary_list, bc_failed_items = bc_process_func(
        detail_data, company, skip_item_ids=original_quoted_ids
    )

    failed_items = _merge_failed_items(crm_failed_items, bc_quote_items, bc_failed_items)

    # CRM 报上的项优先
    merged_quote_items = {**bc_quote_items, **crm_quote_items}
    return {
        'extra_quote_items': merged_quote_items,
        'summary_list': summary_list,
        'failed_items': failed_items,
        'category': category,
        'crm_quote_item_ids': set(crm_quote_items.keys()),
        'crm_failed_items': crm_failed_items,
        'original_quoted_ids': original_quoted_ids,
        'bc_quote_item_ids': set(bc_quote_items.keys()),
        'bc_failed_items': bc_failed_items
    }


@register_handler('A')
def handle_category_a(detail_data, company):
    """处理 A 类订单：全 PART_QUOTE，先走 CRM 现货流程"""
    crm_quote_items, _, crm_failed_items = process_crm_spot_quote(detail_data, company)
    return {
        'extra_quote_items': crm_quote_items,
        'summary_list': [],
        'failed_items': crm_failed_items,
        'category': 'A',
        'crm_quote_item_ids': set(crm_quote_items.keys()),
        'crm_failed_items': crm_failed_items,
        'original_quoted_ids': set(),
        'bc_quote_item_ids': set(),
        'bc_failed_items': {}
    }


@register_handler('B')
def handle_category_b(detail_data, company):
    """处理 B 类订单：奔驰车 + 有 WAITING_QUOTE，CRM 现货优先"""
    return _handle_bc_category(detail_data, company, process_mercedes_order, 'B')


@register_handler('C')
def handle_category_c(detail_data, company):
    """处理 C 类订单：宝马车 + 有 WAITING_QUOTE，CRM 现货优先"""
    return _handle_bc_category(detail_data, company, process_bmw_order, 'C')


def _get_process_meta(process_result):
    """
    从 handler 结果中提取需要透传到保存阶段的元数据

    Returns:
        dict: CRM/B/C 相关 ID 集合和失败原因
    """
    return {
        'crm_quote_item_ids': process_result.get('crm_quote_item_ids', set()),
        'crm_failed_items': process_result.get('crm_failed_items', {}),
        'original_quoted_ids': process_result.get('original_quoted_ids', set()),
        'bc_quote_item_ids': process_result.get('bc_quote_item_ids', set()),
        'bc_failed_items': process_result.get('bc_failed_items', {})
    }


def process_order_by_category(detail_data, company):
    """根据订单类别分发处理"""
    category = classify_order(detail_data)
    if category == 'SKIP':
        return {
            'extra_quote_items': {},
            'summary_list': [],
            'failed_items': {},
            'category': 'SKIP',
            'crm_quote_item_ids': set(),
            'crm_failed_items': {},
            'original_quoted_ids': set(),
            'bc_quote_item_ids': set(),
            'bc_failed_items': {}
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


def _collect_bmw_original_oes(orders, company):
    """
    收集 C 类（宝马）订单中适配列表含原厂品牌的 item 对应的原厂 OE。
    兼容列表接口（顶层 supplierEnquiryItemList）和详情接口（supplierEnquiryDemandList 下）两种结构。

    Returns:
        set: 去重后的 OE 集合
    """
    oe_set = set()
    for order in orders:
        if classify_order(order) != 'C':
            continue
        enquiry_no = order.get('supplierEnquiryNo')
        if not enquiry_no:
            qpl_log(f"[{company}] C 类订单缺少 enquiryNo，跳过")
            continue
        qpl_log(f"[{company}] 开始收集 C 类订单 OE: {enquiry_no}")

        items = list(_iter_enquiry_items(order))

        qpl_log(f"[{company}] [OE收集] 订单 {enquiry_no} 共 {len(items)} 个 item")
        for item in items:
            item_status = str(item.get('quoteStatus', '')).strip()
            enquiry_item_id = item.get('enquiryItemId')
            item_oe = item.get('itemOe', '未知')
            qpl_log(
                f"[{company}] [OE收集] item_id={enquiry_item_id} oe={item_oe} status={item_status}",
                order_no=enquiry_no
            )
            if item_status != 'WAITING_QUOTE':
                continue
            try:
                adapt_result = get_adapt_product_brand(enquiry_item_id, enquiry_no, company)
                brand_list = adapt_result.get('data', {}).get('brandList', [])
                qpl_log(
                    f"[{company}] [OE收集] item_id={enquiry_item_id} 适配品牌数={len(brand_list)}",
                    order_no=enquiry_no
                )
                factory_brand = next((b for b in brand_list if b.get('brandTypeDesc') == '原厂'), None)
                if not factory_brand:
                    qpl_log(
                        f"[{company}] [OE收集] item_id={enquiry_item_id} 无原厂品牌",
                        order_no=enquiry_no
                    )
                    continue
                product_list = factory_brand.get('productList', [])
                qpl_log(
                    f"[{company}] [OE收集] item_id={enquiry_item_id} 原厂产品数={len(product_list)}",
                    order_no=enquiry_no
                )
                for product in product_list:
                    for oe in product.get('productOeList', []):
                        if oe:
                            oe_set.add(str(oe).strip())
            except Exception as e:
                qpl_log(
                    f"[{company}] [OE收集] item_id={enquiry_item_id} 获取适配列表失败: {e}",
                    order_no=enquiry_no
                )
                continue
    return oe_set


def _ensure_bmw_oes_in_local_db(missing_oes, company, max_per_round=20):
    """
    调用 data_upsert 补齐缺失的 BMW OE，每个 OE 间隔 40-80 秒。
    data_upsert 内部已包含宝马接口、兆配云兜底和入库逻辑。

    :param missing_oes:  缺失 OE 列表
    :param company:      组织代码
    :param max_per_round: 每轮最多补齐数量
    :return:             处理数量统计
    """
    from app.services.car_parts_library_service.bmw_crawler import data_upsert
    from app.services.car_parts_library_service.bmw_config_service import get_bmw_config
    import random
    import time
    import traceback

    if not missing_oes:
        return {'total': 0, 'success': 0, 'failed': 0}

    config = get_bmw_config()
    cookie = config.get('cookie') if isinstance(config, dict) else None
    if not cookie:
        qpl_log(f"[{company}] 未配置 BMW cookie，跳过 OE 补齐")
        return {'total': 0, 'success': 0, 'failed': 0}

    to_process = missing_oes[:max_per_round]
    success_count = 0
    failed_count = 0
    failed_oes = set()

    for oe in to_process:
        try:
            qpl_log(f"[{company}] 开始补齐 BMW OE: {oe}")
            upsert_result = data_upsert(oe, cookie)
            qpl_log(
                f"[{company}] BMW OE 补齐结果: {oe} | "
                f"status={upsert_result.get('status')} "
                f"detail_updated={upsert_result.get('detail_updated')} "
                f"stock_updated={upsert_result.get('stock_updated')} "
                f"msg={upsert_result.get('msg')}"
            )
            success_count += 1
        except Exception as e:
            failed_count += 1
            failed_oes.add(oe)
            qpl_log(f"[{company}] BMW OE 补齐失败: {oe}, {e}")
            qpl_log(f"[{company}] BMW OE 补齐失败详情: {traceback.format_exc()}")
        time.sleep(random.randint(40, 80))

    qpl_log(
        f"[{company}] BMW OE 补齐完成 | 总计={len(to_process)} 成功={success_count} 失败={failed_count}"
    )
    return {'total': len(to_process), 'success': success_count, 'failed': failed_count}


def _process_single_order(enquiry_no, category, company, idx, total, results):
    """
    处理单个订单并追加结果。
    """
    detail = get_enquiry_detail(enquiry_no, company=company)
    detail_data = detail.get('data', {})

    shop_uid = detail_data.get('shopUid')
    tuhu_supplier_id = detail_data.get('tuhuSupplierId')
    if shop_uid and enquiry_no:
        pickup_result = get_pickup_way_and_distance(shop_uid, enquiry_no, tuhu_supplier_id, company)
        pickup_info = extract_pickup_info(pickup_result)
        detail_data.update(pickup_info)

    handler = ORDER_HANDLERS[category]
    process_result = handler(detail_data, company)

    extra_quote_items = process_result['extra_quote_items']
    summary_list = process_result['summary_list']
    failed_items = process_result['failed_items']
    order_category = process_result['category']

    order_prefix = f"[{company}] [{idx}/{total}] [{order_category}类]"

    item_info_map = {}
    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            item_info_map[item.get('enquiryItemId')] = {
                'oe': item.get('itemOe') or 'None',
                'status': item.get('quoteStatus')
            }

    has_any_quote = _has_any_quote(detail_data, extra_quote_items)
    if order_category in ('B', 'C') and failed_items:
        failed_desc = "; ".join(
            f"oe={item_info_map.get(item_id, {}).get('oe', '未知')} "
            f"status={item_info_map.get(item_id, {}).get('status', '未知')} 原因={reason}"
            for item_id, reason in failed_items.items()
        )
        qpl_log(f"{order_prefix}: 未报价 {failed_desc}", order_no=enquiry_no)

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
                        'company': company,
                        **_get_process_meta(process_result)
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
                        'company': company,
                        **_get_process_meta(process_result)
                    })
            except Exception as e:
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
                    'company': company,
                    **_get_process_meta(process_result)
                })
            return
        elif not has_any_quote:
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
                'company': company,
                **_get_process_meta(process_result)
            })
            return

    quote_request = construct_quote_request(detail_data, extra_quote_items)
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
        'company': company,
        **_get_process_meta(process_result)
    })


def submit_all_quotes(begin_date=None, end_date=None, company='fsbbr'):
    """
    提交所有符合条件的报价

    处理优先级:
        1. A类: 全PART_QUOTE订单 (最快路径)
        2. B类: 奔驰车+有未报价项目 (需查奔驰接口)
        3. C类: 宝马车+有未报价项目 (需查宝马接口，先补齐本地库)
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

    # 先处理 A/B 类订单
    ab_orders = [(c, no) for c, no in categorized if c in ('A', 'B')]
    for idx, (category, enquiry_no) in enumerate(ab_orders, start=1):
        _process_single_order(enquiry_no, category, company, idx, len(ab_orders), results)

    # 收集 C 类订单原厂 OE 并补齐本地库
    c_order_nos = {no for c, no in categorized if c == 'C'}
    qpl_log(f"[{company}] C 类订单白名单: {c_order_nos}")
    if c_order_nos:
        c_orders = [unique_orders[no] for no in c_order_nos]
        bmw_oe_set = _collect_bmw_original_oes(c_orders, company)
        qpl_log(f"[{company}] 收集到 BMW 原厂 OE: {bmw_oe_set}")
        if bmw_oe_set:
            from app.utils.qpl_auto_bill.bmw_quote_local_db import check_bmw_oes_in_local_db
            _, status = check_bmw_oes_in_local_db(list(bmw_oe_set))
            qpl_log(f"[{company}] 本地库缺失 BMW OE: {status}")
            missing_oes = status.get('missing', [])
            if missing_oes:
                qpl_log(f"[{company}] 发现 {len(missing_oes)} 个 BMW OE 需要补齐本地库")
                _ensure_bmw_oes_in_local_db(missing_oes, company)

    # 重新拉取订单，只处理白名单内的 C 类订单
    if c_order_nos:
        fresh_result = query_enquiry_list(begin_date, end_date, company=company)
        fresh_orders = fresh_result.get('data') or []
        fresh_unique_orders = {o.get('supplierEnquiryNo'): o for o in fresh_orders if o.get('supplierEnquiryNo')}

        c_count = 0
        for idx, (category, enquiry_no) in enumerate(categorized, start=1):
            if category != 'C':
                continue
            if enquiry_no not in fresh_unique_orders:
                continue
            c_count += 1
            _process_single_order(enquiry_no, 'C', company, c_count, len(c_order_nos), results)

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
