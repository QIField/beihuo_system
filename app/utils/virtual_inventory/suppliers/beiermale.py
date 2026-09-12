# -*- coding: utf-8 -*-
"""
贝尔马勒 CRM 数据抓取模块

从 crm.gzbbr.com 获取马勒、贝洱、纳铁福、吉凯恩库存数据，处理差异后保存。
"""

import json
from datetime import datetime, timedelta

import requests
import pandas as pd

from ..brands import process_price_by_brand
from ..database import get_db_connection
from ..persistence import save_to_company_tables
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')


def get_crm_cookies():
    url = "http://113.45.176.129:8001/get_crm_cookies?key=fs"
    payload = {}
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }
    response = requests.request("GET", url, headers=headers, data=payload)
    cookies = json.loads(response.text)['cookie']
    headers = cookies

    return cookies, headers


def get_stock(cookies, headers):
    json_data = {
        'sale_start_time': None,
        'sale_end_time': None,
        'is_sub': None,
        'is_hot': None,
        'is_new': None,
        'product_type_id': None,
        'make_id': None,
        'series_id': None,
        'car_id': None,
        'chassis_id': None,
        'engine_id': None,
        'brand_id': '53,5,98,110',
        'sap_product_division': None,
        'material_type': None,
        'level_id': None,
        'product_grade': None,
        'currency_id': None,
        'language_code': None,
        'vin': None,
        'keyword': None,
        'aikeyword': None,
        'number': None,
        'numberlist': None,
        'is_stock': '1',
        'is_dangerstock': 0,
        'is_nostock': 0,
        'sale_type': 0,
        'is_zaitu': None,
        'customer_id': None,
        'price_exception': '',
        'is_third_party': None,
        'brand_type': None,
        'brand_type_map_id': None,
        'is_unsalable': None,
        'out_purchase_product': None,
        'page': 1,
        'limit': 20,
        'cass_oebrand_name': '',
        'warehouse_id': '',
    }
    page_max = 1
    page = 1

    brand_data = {
        '马勒': {},
        '贝洱': {},
        '纳铁福': {},
        '吉凯恩': {},
    }

    while page <= page_max:
        json_data['page'] = page
        try:
            response = requests.post(
                'https://crm.gzbbr.com/api/Product.Product/list',
                cookies=cookies,
                headers=headers,
                json=json_data,
                timeout=10
            ).json()['data']
        except (requests.RequestException, KeyError) as e:
            logger.exception(f"请求失败")
            return {}, {}, {}, {}

        page_max = response.get('last_page', 1)

        for item in response.get('data', [{}])[0].get('child', []):
            number = item.get('number')
            brand_name = item.get('brand_name')
            price = item.get('price')
            if not price:
                continue
            stock = item.get('stock', 0)

            if brand_name in brand_data:
                brand_data[brand_name][number] = {
                    'price': price,
                    'stock': stock
                }

        logger.info(f'Page {page} / {page_max}')
        page += 1

    return (
        brand_data['马勒'],
        brand_data['贝洱'],
        brand_data['纳铁福'],
        brand_data['吉凯恩']
    )


def chuli_beiermale(male, beier, ntf, jky):
    logger.info(beier)
    logger.info('m')
    logger.info(male)
    data = []

    # 马勒-贝洱对比组：最终只输出马勒品牌
    for number in male:
        if number not in beier:
            # 确保价格是数值类型后再进行计算
            price_value = male[number]['price']
            if isinstance(price_value, str):
                try:
                    price_value = float(price_value)
                except ValueError:
                    logger.warning(f"警告: 无法将价格 '{price_value}' 转换为数值，跳过此项")
                    continue
            adjusted_price = process_price_by_brand(price_value, '马勒')
            data.append([
                number, '马勒', adjusted_price, price_value, male[number]['stock']
            ])

    for number in beier:
        if number not in male:
            # 确保价格是数值类型后再进行计算
            price_value = beier[number]['price']
            if isinstance(price_value, str):
                try:
                    price_value = float(price_value)
                except ValueError:
                    logger.warning(f"警告: 无法将价格 '{price_value}' 转换为数值，跳过此项")
                    continue
            adjusted_price = process_price_by_brand(price_value, '马勒')
            data.append([
                number, '马勒', adjusted_price, price_value, beier[number]['stock']
            ])

    # 纳铁福-吉凯恩对比组
    for number in ntf:
        if number not in jky:
            # 确保价格是数值类型后再进行计算
            price_value = ntf[number]['price']
            if isinstance(price_value, str):
                try:
                    price_value = float(price_value)
                except ValueError:
                    logger.warning(f"警告: 无法将价格 '{price_value}' 转换为数值，跳过此项")
                    continue
            adjusted_price = process_price_by_brand(price_value, '吉凯恩')
            data.append([
                number, '吉凯恩', adjusted_price, price_value, ntf[number]['stock']
            ])

    for number in jky:
        if number not in ntf:
            # 确保价格是数值类型后再进行计算
            price_value = jky[number]['price']
            if isinstance(price_value, str):
                try:
                    price_value = float(price_value)
                except ValueError:
                    logger.warning(f"警告: 无法将价格 '{price_value}' 转换为数值，跳过此项")
                    continue
            adjusted_price = process_price_by_brand(price_value, '纳铁福')
            data.append([
                number, '纳铁福', adjusted_price, price_value, jky[number]['stock']
            ])

    return data


def save_beiermale_to_db(data):
    current_time = datetime.now()
    expiry_date = (current_time + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    fetch_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')

    # 批量保存到数据库
    db_manager = get_db_connection()
    try:
        # 批量插入数据
        batch_size = 1000  # 批量处理大小
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]

            # 准备批量插入数据
            batch_data = []
            for row in batch:
                batch_data.append((
                    '佛山巴博瑞',  # 供应商
                    row[0],       # OE码
                    row[1],       # 品牌
                    row[2],       # 价格
                    expiry_date,  # 失效时间（当前时间+1天）
                    '佛山禅城仓', # 仓库
                    row[3],       # 库存
                    '',           # 备注
                    fetch_time_str  # 拉取时间
                ))

            # 批量插入
            sql = """
                INSERT INTO beiermale_data (supplier, oe_code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            logger.info(f"已批量保存 {min(i + batch_size, len(data))} / {len(data)} 条贝尔马勒数据")

    finally:
        db_manager.close()

    # 将数据保存到各公司整合表
    df = pd.DataFrame(data, columns=['原厂OE码', '品牌', '价格', '原价格', '库存'])
    df['供应商名称'] = '佛山巴博瑞'
    df['失效时间'] = expiry_date
    df['仓库名称'] = '佛山禅城仓'
    df['备注'] = ''

    # 保存到各公司表（贝尔马勒数据不是万拓也不是昌盛）
    save_to_company_tables(df, is_wantuo=False, is_changsheng=False)


def male_bier_start():
    cookies, headers = get_crm_cookies()
    male_data, beier_data, ntf_data, jky_data = get_stock(cookies, headers)
    diff_data = chuli_beiermale(male_data, beier_data, ntf_data, jky_data)
    save_beiermale_to_db(diff_data)
