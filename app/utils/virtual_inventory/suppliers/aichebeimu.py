# -*- coding: utf-8 -*-
"""
爱车贝母数据抓取模块

从 gylqp.com 获取佛山、东莞、中山库存数据并保存。
"""

from datetime import datetime, timedelta
import time

import requests
import pandas as pd
import urllib3

from ..brands import process_price_by_brand
from ..database import get_db_connection
from ..persistence import save_to_company_tables
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def gylqp_start():
    cookies = {
        'ASP.NET_SessionId': '2xjnyp1lnkpnqn53rl2ced4y',
        'b2bgylqp': 'ztname=KH020215&ztpwd=337704&ztper=&ztdpm=A&ztdpmname=%e5%b9%bf%e5%b7%9e%e6%80%bb%e9%83%a8',
    }

    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'http://www.gylqp.com',
        'Referer': 'http://www.gylqp.com/New/index.aspx?mname=%E9%9B%B6%E4%BB%B6%E8%AF%A2%E4%BB%B7%E6%9C%8D%E5%8A%A1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0',
    }

    data = {
        'action': 'Getisto',
        'modulename': 'Getisto',
        'PageIndex': '1',
        'wdcp': 'false',
        'data': '{"Where":"","Nno":"","tabindex":"0"}',
    }
    page = 1
    d_ = []
    while True:
        data['PageIndex'] = str(page)
        for c in range(3):
            try:
                response = requests.post('http://www.gylqp.com/Handler/KHHandler.ashx', cookies=cookies, headers=headers, data=data,
                                         verify=False).json()
                c = len(response)
                break
            except:
                time.sleep(2)
        if page == 1:
            logger.info(response[0])
            logger.info('')
        if c > 0:
            for item in response:
                d_.append([
                    item['v_nno'].strip(), item['na1'].strip(), item['ty'].strip(), item['fa'].strip(), item['oprc'],
                    item['kcamount'], item['areaname'].strip(), item['qq'].strip(), item['posi'].strip(),
                    item['sxnote'].strip(), item['hhm'].strip()
                ])
            logger.info(f'\r以获取第{page}页，共{c}条数据')
            page += 1
        else:
            break

    current_time = datetime.now()
    fetch_time = current_time.strftime("%Y-%m-%d %H:%M:%S")

    # 分类数据
    foshan_data = []
    dongguan_data = []
    zhongshan_data = []

    for i in d_:
        if '佛山' in i[6]:
            bm = i[0].replace(' ','')
            bm = bm.split('-')[0].replace('AM','')
            gys = '爱车贝母'
            pp = '巴博瑞'
            # 根据品牌处理价格
            original_price = i[4]
            price = process_price_by_brand(original_price, pp)
            kc = i[5]
            next_day_later = (current_time + timedelta(days=1)).strftime(
                "%Y-%m-%d %H:%M:%S")
            ck = '佛山禅城仓'
            foshan_data.append([
                gys, bm, pp, price, original_price, next_day_later, ck, kc, '', fetch_time
            ])
        if '东莞' in i[6]:
            bm = i[0].replace(' ','')
            bm = bm.split('-')[0].replace('AM','')
            gys = '爱车贝母'
            pp = '巴博瑞'
            # 根据品牌处理价格
            original_price = i[4]
            price = process_price_by_brand(original_price, pp)
            kc = i[5]
            next_day_later = (current_time + timedelta(days=1)).strftime(
                "%Y-%m-%d %H:%M:%S")
            ck = '东莞寮步仓'
            dongguan_data.append([
                gys, bm, pp, price, original_price, next_day_later, ck, kc, '', fetch_time
            ])
        if '中山' in i[6]:
            bm = i[0].replace(' ','')
            bm = bm.split('-')[0].replace('AM','')
            gys = '爱车贝母'
            pp = '巴博瑞'
            # 根据品牌处理价格
            original_price = i[4]
            price = process_price_by_brand(original_price, pp)
            kc = i[5]
            next_day_later = (current_time + timedelta(days=1)).strftime(
                "%Y-%m-%d %H:%M:%S")
            ck = '中山西区街道仓'
            zhongshan_data.append([
                gys, bm, pp, price, original_price, next_day_later, ck, kc, '', fetch_time
            ])

    # 批量保存到数据库
    db_manager = get_db_connection()
    try:
        # 保存佛山数据
        batch_size = 1000
        for i in range(0, len(foshan_data), batch_size):
            batch = foshan_data[i:i + batch_size]

            # 准备批量插入数据（跳过 original_price 字段）
            batch_data = []
            for row in batch:
                batch_data.append((row[0], row[1], row[2], row[3], row[5], row[6], row[7], row[8], row[9]))

            # 批量插入
            sql = """
                INSERT INTO aichebeimu_foshan_data (supplier, oe_code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            logger.info(f"已批量保存 {min(i + batch_size, len(foshan_data))} / {len(foshan_data)} 条爱车贝母佛山数据")

        # 保存东莞数据
        for i in range(0, len(dongguan_data), batch_size):
            batch = dongguan_data[i:i + batch_size]

            # 准备批量插入数据（跳过 original_price 字段）
            batch_data = []
            for row in batch:
                batch_data.append((row[0], row[1], row[2], row[3], row[5], row[6], row[7], row[8], row[9]))

            # 批量插入
            sql = """
                INSERT INTO aichebeimu_dongguan_data (supplier, oe_code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            logger.info(f"已批量保存 {min(i + batch_size, len(dongguan_data))} / {len(dongguan_data)} 条爱车贝母东莞数据")

        # 保存中山数据
        for i in range(0, len(zhongshan_data), batch_size):
            batch = zhongshan_data[i:i + batch_size]

            # 准备批量插入数据（跳过 original_price 字段）
            batch_data = []
            for row in batch:
                batch_data.append((row[0], row[1], row[2], row[3], row[5], row[6], row[7], row[8], row[9]))

            # 批量插入
            sql = """
                INSERT INTO aichebeimu_zhongshan_data (supplier, oe_code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            logger.info(f"已批量保存 {min(i + batch_size, len(zhongshan_data))} / {len(zhongshan_data)} 条爱车贝母中山数据")

    finally:
        db_manager.close()

    # 将数据保存到各公司整合表
    all_data = foshan_data + dongguan_data + zhongshan_data
    df = pd.DataFrame(all_data, columns=['供应商名称', '原厂OE码', '品牌', '价格', '原价格', '失效时间', '仓库名称', '库存', '备注', 'fetch_time'])

    # 保存到各公司表（爱车贝母数据不是万拓也不是昌盛）
    save_to_company_tables(df, is_wantuo=False, is_changsheng=False)
