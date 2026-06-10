#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""自动提交部分报价订单"""

import sys
import os
import json
import io
from contextlib import redirect_stdout

# 添加当前目录到路径，支持相对导入
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))

from datetime import datetime, timedelta
from enquiry_api import (
    query_enquiry_list, get_enquiry_detail, get_adapt_product_brand,
    price_check, get_pickup_way_and_distance, extract_pickup_info
)
from quote_builder import (
    is_all_part_quote,
    construct_quote_request,
    construct_mercedes_quote_item,
    select_warehouse_and_days,
    WAREHOUSE_MAP
)
from qpl_config import BASE_URL, get_headers
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
    return resp.json()


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


def process_mercedes_order(detail_data, company='fsbbr'):
    """
    处理奔驰车订单

    Args:
        detail_data: 询价单详情数据
        company: 组织代码

    Returns:
        tuple: (mercedes_quote_items, summary_list, failed_items)
            - mercedes_quote_items: {enquiry_item_id: [quote_item, ...]}
            - summary_list: [{item_oe, item_name, price, days, product_count}, ...]
            - failed_items: {enquiry_item_id: "失败原因字符串"}
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
            if item.get('quoteStatus') == 'WAITING_QUOTE':
                item_oe = item.get('itemOe')
                item_name = item.get('itemName')
                enquiry_item_id = item.get('enquiryItemId')
                # 从 saleCategoryPathId 提取第一个路径段作为 categoryId: "/4/21/332/3612/" -> "/4/"
                sale_category_path = item.get('saleCategoryPathId', '/5/')
                path_parts = sale_category_path.split('/')
                category_id = f"/{path_parts[1]}/" if len(path_parts) >= 2 and path_parts[1] else "/5/"

                # 调用适配列表接口
                try:
                    adapt_result = get_adapt_product_brand(enquiry_item_id, enquiry_no, company)
                    brand_list = adapt_result.get('data', {}).get('brandList', [])

                    # 找到原厂品牌和对应的所有产品
                    factory_brand = None
                    factory_product_list = []
                    product_oe_list = []

                    for brand in brand_list:
                        brand_type_desc = brand.get('brandTypeDesc', '')
                        if brand_type_desc == '原厂':
                            factory_brand = brand
                            factory_product_list = brand.get('productList', [])
                            for product in factory_product_list:
                                product_oe_list.extend(product.get('productOeList', []))
                            break

                    if not factory_brand or not factory_product_list:
                        reason = "适配列表为空，无原厂奔驰产品"
                        print(f"[汽配龙自动报价][跳过] {enquiry_no} - {item_oe}: {reason}")
                        failed_items[enquiry_item_id] = reason
                        continue

                    product_oe_list = list(set(product_oe_list))
                    if not product_oe_list:
                        continue

                    # 查询所有OE的价格和库存
                    oe_price_map = query_mercedes_service_all(product_oe_list)
                    if not oe_price_map:
                        reason = "零件信息请求失败"
                        print(f"[汽配龙自动报价][跳过] {enquiry_no} - {item_oe}: {reason}")
                        failed_items[enquiry_item_id] = reason
                        continue

                    # 为每个产品选择最优价格（该产品的所有OE中价格最低的）
                    print(f"  产品最优价格选择:")
                    product_price_map = {}  # {pid: {'price': xxx, 'stock_info': [...]}}
                    for product in factory_product_list:
                        product_oes = product.get('productOeList', [])
                        product_pid = product.get('pid', '')
                        brand_name = product.get('brandName', factory_brand.get('brandName', ''))
                        product_oe = product.get('itemPerhapsReplaceOe', '未知OE')
                        
                        best_price = None
                        best_stock = None
                        best_oe = None
                        
                        for oe in product_oes:
                            if oe in oe_price_map:
                                price = oe_price_map[oe]['wholesale_price']
                                if best_price is None or price < best_price:
                                    best_price = price
                                    best_stock = oe_price_map[oe]['stock_info']
                                    best_oe = oe
                        
                        if best_price is not None:
                            item_sell_price = round(best_price * 1.09)
                            product_price_map[product_pid] = {
                                'price': item_sell_price,
                                'stock_info': best_stock,
                                'oe': best_oe
                            }
                            print(f"    {brand_name} {product_oe}: 使用OE {best_oe} 的价格 ¥{item_sell_price}")
                        else:
                            print(f"    {brand_name} {product_oe}: 无可用价格")

                    if not product_price_map:
                        reason = "库存为0"
                        print(f"[汽配龙自动报价][跳过] {enquiry_no} - {item_oe}: {reason}")
                        failed_items[enquiry_item_id] = reason
                        continue

                    # ========== 为每个产品单独进行 priceCheck 校验 ==========
                    print(f"  priceCheck:")
                    price_check_map = {}
                    price_check_errors = []
                    
                    for product in factory_product_list:
                        product_pid = product.get('pid', '')
                        if product_pid not in product_price_map:
                            continue
                        
                        product_info = product_price_map[product_pid]
                        item_sell_price = product_info['price']
                        
                        req_item = {
                            "translationOE": product.get('itemPerhapsReplaceOe', ''),
                            "chainType": None,
                            "chainId": None,
                            "pid": product_pid,
                            "price": item_sell_price,
                            "quality": product.get('quality', 1),
                            "productNum": 1,
                            "brandName": product.get('brandName', factory_brand.get('brandName', '')),
                            "queryProductBrandId": factory_brand.get('brandId', ''),
                            "uid": None,
                            "supplierEnquiryItemId": enquiry_item_id,
                            "regionalDistributionType": None,
                            "productName": product.get('displaceProductName', ''),
                            "qualityTypeId": product.get('qualityTypeId', ''),
                            "brandOwnerId": "",
                            "quoteTaxType": "INCLUSIVE"
                        }
                        
                        # 单个产品进行 priceCheck
                        price_check_result = price_check(
                            [req_item], tid, car_brand, enquiry_no, company
                        )
                        
                        brand_name = product.get('brandName', '未知品牌')
                        product_oe = product.get('itemPerhapsReplaceOe', '未知OE')
                        
                        if price_check_result and price_check_result.get('code') == 10000:
                            check_data = price_check_result.get('data', [])
                            if check_data:
                                check_item = check_data[0]
                                check_result_status = check_item.get('checkResult', '')
                                check_message = check_item.get('checkMessage')
                                snapshot = check_item.get('priceCheckSnapshot')
                                
                                if check_result_status == 'SUCCESS' and not check_message:
                                    price_check_map[product_pid] = snapshot
                                    print(f"    ✓ {brand_name} {product_oe} ¥{item_sell_price}")
                                else:
                                    msg = check_message or 'FAIL'
                                    print(f"    ✗ {brand_name} {product_oe} ¥{item_sell_price} - {msg}")
                                    price_check_errors.append(f"{brand_name} {product_oe}: {msg}")
                            else:
                                print(f"    ✗ {brand_name} {product_oe} ¥{item_sell_price} - 无校验结果")
                                price_check_errors.append(f"{brand_name} {product_oe}: 无校验结果")
                        else:
                            api_error = price_check_result.get('message', '未知错误') if price_check_result else '无响应'
                            print(f"    ✗ {brand_name} {product_oe} ¥{item_sell_price} - {api_error}")
                            price_check_errors.append(f"{brand_name} {product_oe}: {api_error}")

                    # ========== 构造报价项 ==========
                    quote_items_for_item = []
                    for product in factory_product_list:
                        product_pid = product.get('pid', '')
                        if product_pid not in price_check_map:
                            continue
                        
                        if product_pid not in product_price_map:
                            continue
                        
                        product_info = product_price_map[product_pid]
                        item_sell_price = product_info['price']
                        stock_info = product_info['stock_info']
                        
                        # 选择仓库和时效
                        selected_warehouse, prepare_good_timespan = select_warehouse_and_days(stock_info)
                        if not selected_warehouse:
                            continue

                        quote_item = construct_mercedes_quote_item(
                            factory_brand, product, factory_product_list,
                            item_sell_price, prepare_good_timespan,
                            price_check_map.get(product_pid),
                            category_id
                        )
                        quote_items_for_item.append(quote_item)

                    if not quote_items_for_item:
                        reason = "价格监测失败: " + "；".join(price_check_errors) if price_check_errors else "价格监测失败"
                        print(f"[汽配龙自动报价][跳过] {enquiry_no} - {item_oe}: {reason}")
                        failed_items[enquiry_item_id] = reason
                        continue

                    mercedes_quote_items[enquiry_item_id] = quote_items_for_item

                    # 收集汇总信息
                    summary_list.append({
                        'item_oe': item_oe,
                        'item_name': item_name,
                        'price': item_sell_price,
                        'days': prepare_good_timespan,
                        'product_count': len(quote_items_for_item)
                    })

                except Exception:
                    continue

    return mercedes_quote_items, summary_list, failed_items


def classify_order(order_data):
    """
    对订单进行分类，返回类别标识

    Returns:
        str: 'A' = 全PART_QUOTE, 'B' = 奔驰+未报价, 'SKIP' = 普通车+未报价
    """
    car_type5 = order_data.get('carType5', '')
    items = []
    # 列表接口：项目可能在顶层 supplierEnquiryItemList
    items.extend(order_data.get('supplierEnquiryItemList', []))
    # 详情接口：项目在 supplierEnquiryDemandList 下
    for demand in order_data.get('supplierEnquiryDemandList', []):
        items.extend(demand.get('supplierEnquiryItemList', []))

    has_waiting = any(item.get('quoteStatus') == 'WAITING_QUOTE' for item in items)
    is_mercedes = car_type5.startswith('奔驰') if car_type5 else False

    category_map = {
        (False, False): 'A',
        (False, True):  'A',
        (True, False):  'SKIP',
        (True, True):   'B',
    }
    return category_map[(has_waiting, is_mercedes)]


ORDER_HANDLERS = {}


def register_handler(category):
    """装饰器：注册类别处理器"""
    def decorator(func):
        ORDER_HANDLERS[category] = func
        return func
    return decorator


@register_handler('A')
def handle_category_a(detail_data, company):
    """处理 A 类订单：全 PART_QUOTE，无需奔驰处理"""
    return {
        'mercedes_quote_items': {},
        'summary_list': [],
        'failed_items': {},
        'category': 'A'
    }


@register_handler('B')
def handle_category_b(detail_data, company):
    """处理 B 类订单：奔驰车 + 有 WAITING_QUOTE"""
    mercedes_quote_items, summary_list, failed_items = process_mercedes_order(detail_data, company)
    return {
        'mercedes_quote_items': mercedes_quote_items,
        'summary_list': summary_list,
        'failed_items': failed_items,
        'category': 'B'
    }


def process_order_by_category(detail_data, company):
    """根据订单类别分发处理"""
    category = classify_order(detail_data)
    handler = ORDER_HANDLERS[category]
    return handler(detail_data, company)


def print_summary_table(detail_data, mercedes_quote_items, summary_list, company='fsbbr'):
    """
    打印报价汇总表格

    Args:
        detail_data: 询价单详情
        mercedes_quote_items: 奔驰报价项字典
        summary_list: 奔驰报价汇总列表
        company: 组织代码
    """
    enquiry_no = detail_data.get('supplierEnquiryNo', '')
    car_type5 = detail_data.get('carType5', '')

    print("\n" + "=" * 80)
    print(f"[汽配龙自动报价][{company}] 订单: {enquiry_no} | {car_type5}")
    print("=" * 80)
    print(f"{'项目OE':<20} {'项目名称':<25} {'报价':<8} {'备货天数':<8} {'报价数'}")
    print("-" * 80)

    # PART_QUOTE 项目（已有报价，按原方式处理）
    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            if item.get('quoteStatus') == 'PART_QUOTE':
                existing_quotes = item.get('supplierQuoteItemList', [])
                if existing_quotes:
                    first_quote = existing_quotes[0]
                    price = first_quote.get('itemSellPrice') or 0
                    days = first_quote.get('prepareGoodTimespan') or 0
                    print(f"{item.get('itemOe', '')[:18]:<20} {item.get('itemName', '')[:23]:<25} ¥{price:<7} {days:<8} {len(existing_quotes)}")

    # WAITING_QUOTE + 奔驰报价项目
    for summary in summary_list:
        print(f"{summary['item_oe'][:18]:<20} {summary['item_name'][:23]:<25} ¥{summary['price']:<7} {summary['days']:<8} {summary['product_count']}")

    # WAITING_QUOTE + 未报价项目
    for demand in detail_data.get('supplierEnquiryDemandList', []):
        for item in demand.get('supplierEnquiryItemList', []):
            enquiry_item_id = item.get('enquiryItemId')
            if item.get('quoteStatus') == 'WAITING_QUOTE' and enquiry_item_id not in mercedes_quote_items:
                print(f"{item.get('itemOe', '')[:18]:<20} {item.get('itemName', '')[:23]:<25} {'--':<8} {'--':<8} {'未报价'}")

    print("=" * 80)


def submit_all_quotes(begin_date=None, end_date=None, company='fsbbr'):
    """
    提交所有符合条件的报价

    处理优先级:
        1. A类: 全PART_QUOTE订单 (最快路径)
        2. B类: 奔驰车+有未报价项目 (需查奔驰接口)
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

    print(f"[汽配龙自动报价][{company}] 查询日期: {begin_date} 至 {end_date}")

    result = query_enquiry_list(begin_date, end_date, company=company)
    orders = result.get('data', [])

    unique_orders = {order.get('supplierEnquiryNo'): order for order in orders if order.get('supplierEnquiryNo')}
    print(f"[汽配龙自动报价][{company}] 找到 {len(unique_orders)} 个订单")

    # 分类并筛选：A/B类保留，SKIP类过滤
    categorized = []
    skipped_count = 0
    for enquiry_no, order in unique_orders.items():
        category = classify_order(order)
        if category == 'SKIP':
            skipped_count += 1
            print(f"[跳过][{company}] {enquiry_no}: 普通车含未报价项目")
            continue
        categorized.append((category, enquiry_no))

    # 按类别排序：A 在前，B 在后
    categorized.sort(key=lambda x: 0 if x[0] == 'A' else 1)

    print(f"[汽配龙自动报价][{company}] 处理 {len(categorized)} 个订单 (跳过 {skipped_count} 个普通车未报价订单)")

    results = []

    for category, enquiry_no in categorized:
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

        mercedes_quote_items = process_result['mercedes_quote_items']
        summary_list = process_result['summary_list']
        failed_items = process_result['failed_items']
        order_category = process_result['category']

        # 打印汇总表格
        print_summary_table(detail_data, mercedes_quote_items, summary_list, company)

        # 构造报价请求体
        quote_request = construct_quote_request(detail_data, mercedes_quote_items)

        # 实际提交
        submit_response = submit_quote(quote_request, company)
        submit_success = submit_response.get('code') == 10000
        submit_message = submit_response.get('message', '未知响应')

        results.append({
            'enquiry_no': enquiry_no,
            'order_category': order_category,
            'success': submit_success,
            'message': submit_message,
            'detail_data': detail_data,
            'quote_request': quote_request,
            'mercedes_quote_items': mercedes_quote_items,
            'summary_list': summary_list,
            'failed_items': failed_items,
            'submit_time': datetime.now(),
            'company': company
        })

    return results


def main(company='fsbbr'):
    """独立脚本入口"""
    results = submit_all_quotes(company=company)
    print(f"\n[汽配龙自动报价][{company}] 任务完成，共处理 {len(results)} 个订单")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
