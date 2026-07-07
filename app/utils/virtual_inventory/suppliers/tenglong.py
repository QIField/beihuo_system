# -*- coding: utf-8 -*-
"""
腾隆、宝翼隆、沐博 SQL Server 数据抓取模块

从 159.75.116.155 的 SQL Server 获取库存数据，处理后保存到各公司虚拟库存表。
"""

import pyodbc
from datetime import datetime, timedelta

import pandas as pd

from ..brands import process_price_by_brand, load_brands_from_json
from ..database import get_db_connection
from ..persistence import save_to_company_tables
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')


def remove_trailing_numbers(code):
    """
    如果编码最后两位是特定序号（01-09），则去除这些序号
    仅对 12 位或 13 位的编码执行此清理
    """
    if not code or len(code) not in (12, 13):
        return code

    # 定义9个特定序号
    suffixes = ['01', '02', '03', '04', '05', '06', '07', '08', '09']

    # 检查编码末尾是否匹配这些序号
    for suffix in suffixes:
        if code.endswith(suffix):
            return code[:-2]

    return code


def process_supplier_data(all_data, valid_brands=None):
    """
    处理多家供应商数据：
    1. 去除编码末尾的特定序号
    2. 保留各自供应商名称（腾隆、宝翼隆、沐博分开显示）
    3. 只保留brands.json中存在的品牌
    4. 除了腾隆外，其他供应商只有库存大于等于2的才保留
    """
    logger.info("处理供应商数据")

    # 如果提供了有效的品牌列表，则过滤数据
    if valid_brands is not None:
        filtered_data = []
        for item in all_data:
            if item['brand'] in valid_brands:
                filtered_data.append(item)
        all_data = filtered_data
        logger.info(f"品牌过滤后剩余 {len(all_data)} 条数据")

    # 去除编码末尾序号
    processed_data = []
    for item in all_data:
        item['code'] = remove_trailing_numbers(item['code'])
        processed_data.append(item)
    all_data = processed_data

    # 按供应商、编码、品牌分组，取价格中位数和库存总和
    grouped = {}
    for item in all_data:
        key = (item['supplier'], item['code'], item['brand'])
        if key not in grouped:
            grouped[key] = {
                'prices': [],
                'stocks': [],
                'expiry_date': item['expiry_date'],
                'warehouse': item['warehouse'],
                'remark': item['remark'],
                'fetch_time': item['fetch_time']
            }
        grouped[key]['prices'].append(item['price'])
        grouped[key]['stocks'].append(item['stock'])

    # 计算中位数价格和总库存
    final_data = []
    for key, value in grouped.items():
        supplier, code, brand = key
        prices = sorted(value['prices'])
        n = len(prices)
        if n == 0:
            continue
        if n % 2 == 1:
            median_price = prices[n // 2]
        else:
            median_price = (prices[n // 2 - 1] + prices[n // 2]) / 2

        total_stock = sum(value['stocks'])

        # 除了腾隆外，其他供应商库存小于2的跳过
        if supplier != '腾隆' and total_stock < 2:
            continue

        final_data.append({
            'supplier': supplier,
            'code': code,
            'brand': brand,
            'price': median_price,
            'expiry_date': value['expiry_date'],
            'warehouse': value['warehouse'],
            'stock': total_stock,
            'remark': value['remark'],
            'fetch_time': value['fetch_time']
        })

    logger.info(f"去重汇总后剩余 {len(final_data)} 条数据")
    return final_data


def fetch_supplier_data(supplier_name, server, database, username, password):
    """
    从数据库获取指定供应商的数据
    """
    # 定义连接字符串（Windows 版本）
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=no"
    )

    try:
        # 建立连接
        conn = pyodbc.connect(conn_str)
        # 创建游标对象
        cursor = conn.cursor()

        # 执行查询 - 统一查询三家供应商数据
        cursor.execute("""
            SELECT 
                REPLACE(bianma, ' ', '') AS bianma, 
                CASE 
                    WHEN mingcheng LIKE '%下线%' THEN 'XX' 
                    WHEN REPLACE(fenleima, ' ', '') = '正厂' THEN '原厂' 
                    ELSE fenleima 
                END AS fenleima, 
                shuliang, 
                shoujia, 
                gs 
            FROM kucun 
            WHERE chexing != '奔驰' 
              AND gs IN ('腾隆', '沐博', '宝翼隆') 
              AND shuliang > 1 
              AND mingcheng NOT LIKE '%一比一%' 
              AND fenleima NOT LIKE '%一比一%'
        """)

        # 获取结果
        rows = cursor.fetchall()
        conn.close()

        # 处理数据
        current_time = datetime.now()
        processed_data = []

        for row in rows:
            # SQL查询结果：bianma, fenleima, shuliang, shoujia, gs
            bianma = row[0]      # 编码（已在SQL中处理）
            fenleima = row[1]    # 分类码/品牌（已在SQL中处理）
            shuliang = row[2]    # 数量
            shoujia = row[3]     # 售价
            gs = row[4]          # 供应商

            # 去除品牌名称前后的空格（SQL Server可能返回固定长度字符串）
            if fenleima:
                fenleima = fenleima.strip()

            # 品牌过滤
            if not fenleima:
                continue

            # 根据品牌处理价格
            original_price = float(shoujia)
            price = process_price_by_brand(original_price, fenleima)
            if price < 1:
                continue

            stock = shuliang
            expiry_date = (current_time + timedelta(days=int(stock))).strftime("%Y-%m-%d %H:%M:%S")

            processed_data.append({
                'supplier': gs,
                'code': bianma,
                'brand': fenleima,
                'price': price,  # 处理后的价格
                'original_price': original_price,  # 原价格
                'expiry_date': expiry_date,
                'warehouse': '广州越秀仓',
                'stock': stock,
                'remark': '',
                'fetch_time': current_time.strftime("%Y-%m-%d %H:%M:%S")
            })

        return processed_data

    except Exception as e:
        logger.exception(f"获取{supplier_name}数据时出错")
        return []


def sql_sever_data():
    """腾隆/宝翼隆/沐博数据主入口"""
    # 数据库连接信息
    server = "159.75.116.155,5399"
    database = "yyserver"
    username = "sa"
    password = "sql37365680."

    # 读取brands.json文件中的有效品牌
    valid_brands = load_brands_from_json()

    # 获取各供应商数据
    all_data = []

    logger.info("获取腾隆数据...")
    tenglong_data = fetch_supplier_data('腾隆', server, database, username, password)
    all_data.extend(tenglong_data)

    logger.info("获取宝翼隆数据...")
    baoyilong_data = fetch_supplier_data('宝翼隆', server, database, username, password)
    all_data.extend(baoyilong_data)

    logger.info("获取沐博数据...")
    mubo_data = fetch_supplier_data('沐博', server, database, username, password)
    all_data.extend(mubo_data)

    logger.info(f"总共获取到 {len(all_data)} 条原始数据")

    # 处理数据（去序号、去重、取中间值、品牌过滤、库存过滤）
    final_data = process_supplier_data(all_data, valid_brands)
    logger.info(f"处理后剩余 {len(final_data)} 条数据")

    # 批量保存到数据库
    db_manager = get_db_connection()
    try:
        # 批量插入数据
        batch_size = 1000  # 批量处理大小
        for i in range(0, len(final_data), batch_size):
            batch = final_data[i:i + batch_size]

            # 准备批量插入数据
            batch_data = []
            for item in batch:
                batch_data.append((
                    item['supplier'],
                    item['code'],
                    item['brand'],
                    item['price'],
                    item['expiry_date'],
                    item['warehouse'],
                    item['stock'],
                    item['remark'],
                    item['fetch_time']
                ))

            # 批量插入
            sql = """
                INSERT INTO tenglong_data (supplier, code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            logger.info(f"已批量保存 {min(i + batch_size, len(final_data))} / {len(final_data)} 条腾隆数据")

    finally:
        db_manager.close()

    # 将处理后的数据保存到各公司整合表
    # 转换为DataFrame格式
    df = pd.DataFrame(final_data)
    df = df.rename(columns={
        'supplier': '供应商名称',
        'code': '原厂OE码',
        'brand': '品牌',
        'price': '价格',
        'expiry_date': '失效时间',
        'warehouse': '仓库名称',
        'stock': '库存',
        'remark': '备注'
    })
    df['原价格'] = df.get('original_price', df['价格'])

    # 保存到各公司表（腾隆数据不是万拓也不是昌盛）
    save_to_company_tables(df, is_wantuo=False, is_changsheng=False)

    logger.info("腾隆数据已批量保存到数据库")
