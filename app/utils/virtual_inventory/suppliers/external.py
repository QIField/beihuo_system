# -*- coding: utf-8 -*-
"""
外部 Excel 数据导入模块

从辅助服务接口获取 Excel 文件列表并导入虚拟库存。
"""

import json
from datetime import datetime, timedelta

import requests
import pandas as pd

from ..database import get_db_connection
from ..persistence import save_to_company_tables
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')


def _save_jiapei_raw_data(records):
    """将原始 JSON 记录保存到 jiapei_data 表"""
    db_manager = get_db_connection()
    try:
        sql = """
            INSERT INTO jiapei_data (
                supplier_name, oe_code, brand, price, expiry_date,
                warehouse, stock, remark, source_filename, fetch_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        db_manager.execute_many(sql, records)
        logger.info(f"已保存 {len(records)} 条原始记录到 jiapei_data")
    except Exception:
        logger.exception("保存 jiapei_data 原始数据失败")
    finally:
        db_manager.close()


def ggg2():
    url = "http://113.45.176.129:8001/get_xlsx_files"
    payload = {}
    headers = {
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
      'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      'Cache-Control': 'max-age=0',
      'Connection': 'keep-alive',
      'Upgrade-Insecure-Requests': '1',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }
    response = requests.request("GET", url, headers=headers, data=payload)

    # 添加错误处理
    try:
        response_data = json.loads(response.text)
    except json.JSONDecodeError:
        logger.info(f"响应不是有效的JSON格式: {response.text}")
        return pd.DataFrame()  # 返回空DataFrame

    # 检查是否有'files'键
    if 'files' not in response_data:
        logger.info(f"API响应中没有'files'键: {response_data}")
        return pd.DataFrame()  # 返回空DataFrame

    files = response_data['files']
    xs_df_list = []
    raw_records = []  # 用于保存原始 JSON 数据到 jiapei_data
    fetch_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for file in files:
        url = "http://113.45.176.129:8001/download/" + file['filename']
        response = requests.request("GET", url, headers=headers)
        try:
            file_data = json.loads(response.text)['data']
            cdf = pd.DataFrame(file_data)
            cdf['__source_filename__'] = file['filename']
            xs_df_list.append(cdf)

            # 保存原始记录到 jiapei_data
            for record in file_data:
                raw_records.append((
                    record.get('供应商名称', ''),
                    record.get('原厂oe码', ''),
                    record.get('品牌', ''),
                    record.get('价格', None),
                    record.get('失效时间', None),
                    record.get('仓库名称', ''),
                    record.get('库存', None),
                    record.get('备注', ''),
                    file['filename'],
                    fetch_time,
                ))
        except json.JSONDecodeError:
            logger.info(f"下载文件响应不是有效的JSON格式: {response.text}")
            continue
        except KeyError:
            logger.info(f"下载文件响应中没有'data'键: {response.text}")
            continue

    if raw_records:
        _save_jiapei_raw_data(raw_records)

    if not xs_df_list:  # 如果没有有效数据
        return pd.DataFrame()

    fd_df = pd.concat(xs_df_list)
    fd_df['原厂OE码'] = fd_df['原厂oe码']

    # 保存原价格（用于后续各公司价格计算）
    fd_df['原价格'] = fd_df['价格']

    # 替换nan值
    fd_df = fd_df.fillna('')

    # 添加拉取时间
    current_time = datetime.now()
    fetch_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    fd_df['fetch_time'] = fetch_time

    # 计算失效时间（当前时间+1天）
    expiry_date = (current_time + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    fd_df['失效时间'] = expiry_date

    # 批量保存到数据库（保存原始价格，不提前处理）
    db_manager = get_db_connection()
    try:
        # 批量插入数据
        batch_size = 1000  # 批量处理大小
        for i in range(0, len(fd_df), batch_size):
            batch = fd_df.iloc[i:i + batch_size]

            # 准备批量插入数据（保存原始价格）
            batch_data = []
            for index, row in batch.iterrows():
                batch_data.append((
                    row['供应商名称'],
                    row['原厂OE码'],
                    row['品牌'],
                    row['价格'],  # 原始价格
                    row['失效时间'],
                    row['仓库名称'],
                    row['库存'],
                    row['备注'],
                    row['fetch_time']
                ))

            # 批量插入到外部数据表
            sql = """
                INSERT INTO external_data (supplier_name, oe_code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            logger.info(f"已批量保存 {min(i + batch_size, len(fd_df))} / {len(fd_df)} 条外部数据到外部数据表")

    finally:
        db_manager.close()

    # 将数据保存到各公司整合表，使用 save_to_company_tables 统一处理价格
    # 根据供应商名称判断是否为万拓数据
    is_wantuo = '佛山万拓' in fd_df['供应商名称'].values if not fd_df.empty else False
    save_to_company_tables(fd_df, is_wantuo=is_wantuo, is_changsheng=False)

    return fd_df
