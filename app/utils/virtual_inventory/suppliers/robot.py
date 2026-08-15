# -*- coding: utf-8 -*-
"""
机器人/卓智行数据抓取模块

包含：
- 广星库存抓取（get_zhuozhixing_multi）
- 从 jqr_data 表读取机器人数据并与广星合并后保存（fetch_and_process_latest_data）
"""

import json
import re
from datetime import datetime, timedelta

import pymysql
import requests
import pandas as pd

from ..brands import process_price_by_brand, normalize_brand
from ..database import get_db_connection
from ..persistence import save_to_company_tables
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')


BASE_URL = 'http://api.inheartsoft.com/dw-api/kc2018'
PSIGN = '7be06d54152d0bd916f09b0b055f76ad'

SUPPLIERS = [
    # {'name': '鑫峰', 'gsign': 'B810A2A5ABAE10EAEE19B3BE563B24A9'},  # 鑫峰数据已停用
    {'name': '广星', 'gsign': '9F478C130BCD573232B129C5928F0B42'},
]


def get_zhuozhixing_multi():
    """
    获取广星库存（鑫峰已停用）
    :return: DataFrame
    """
    all_dataframes = []

    for supplier_info in SUPPLIERS:
        supplier_name = supplier_info['name']
        gsign = supplier_info['gsign']

        def fetch_allkckey():
            url = f"{BASE_URL}?psign={PSIGN}&gsign={gsign}&mode=allkckey"
            resp = requests.request("GET", url)
            resp.raise_for_status()
            return json.loads(resp.text)['allkckey']

        try:
            allkckey = fetch_allkckey()
        except Exception:
            logger.exception(f"获取{supplier_name} allkckey失败")
            continue

        logger.info(f"{supplier_name} allkckey: {allkckey}")
        pindex = 1
        res_list = []

        while True:
            page_data = None
            last_error = None

            for attempt in range(3):
                url = f"{BASE_URL}?psign={PSIGN}&gsign={gsign}&allkckey={allkckey}&mode=all_kc&pindex={pindex}"
                try:
                    response = requests.request("GET", url)
                    response.raise_for_status()
                    data = json.loads(response.text)

                    if data.get('msgcode') == 9:
                        logger.warning(f"{supplier_name} 第{pindex}页 allkckey无效或已超时，重新获取key (attempt={attempt + 1})")
                        try:
                            allkckey = fetch_allkckey()
                            logger.info(f"{supplier_name} 重新获取到allkckey: {allkckey}")
                        except Exception:
                            logger.exception(f"{supplier_name} 重新获取allkckey失败")
                        last_error = data.get('msgtext')
                        continue

                    if data.get('msgcode') != 0:
                        logger.warning(f"{supplier_name} 第{pindex}页 接口返回异常: msgcode={data.get('msgcode')}, msgtext={data.get('msgtext')}")
                        last_error = data.get('msgtext')
                        continue

                    page_data = data.get('list')
                    if page_data is None:
                        logger.warning(f"{supplier_name} 第{pindex}页 响应中缺少list字段: {response.text[:500]}")
                        last_error = 'missing list'
                        continue
                    break
                except Exception as e:
                    logger.exception(f"{supplier_name} 第{pindex}页第{attempt + 1}次请求失败")
                    last_error = str(e)

            if page_data is None:
                logger.error(f"{supplier_name} 第{pindex}页最终失败，原因: {last_error}")
                break

            if len(page_data) == 0:
                break
            res_list.append(pd.DataFrame(page_data))
            logger.info(f"{supplier_name} 第{pindex}页获取到{len(page_data)}条")
            pindex = pindex + 1

        if res_list:  # 如果有数据
            df = pd.concat(res_list, ignore_index=True)
            df = df.rename(columns={"pjid": "配件ID", "pjcode": "零件编码", "pjoemcode": "制造编码", "pjname": "零件名称",
                                    "pjename": "零件英文名称",
                                    "pjsize": "零件车型", "pjfactory": "产地", "xsprice": "价格", "kcamount": "库存数",
                                    'pjpp': '零件品牌',
                                    'pjbrand': '品牌', 'ppcode': '品牌编码', 'gxcode': '公会编码', 'pjgensize': '通用车型',
                                    'hhcode': '互换码', 'Isgx': '是否共享',
                                    'kcid': '商家库存表自增ID', 'kcdepot': '库号（仓库）'})

            # 特殊后缀列表（识别到末尾有这些字符串时直接去除，以后新增直接追加到列表）
            SPECIAL_SUFFIXES = ['INATZ4', 'INATZ3', 'INA4', 'TZ3']
            suffix_pattern = r'(' + '|'.join(SPECIAL_SUFFIXES) + r')$'

            # 完整 OE 码清洗：去空格 → 去正厂 → 去横杠 → 去开头 A → 去特殊后缀 → 去末尾字母/中文/符号
            oe_clean = (df['零件编码']
                .str.replace(' ', '', regex=False)
                .str.replace('正厂', '', regex=False)
                .str.replace('-', '', regex=False)
                .str.lstrip('A')
                .str.replace(suffix_pattern, '', regex=True)
                .str.replace(r'[A-Za-z\u4e00-\u9fff\W_]+$', '', regex=True)
            )
            df['oe_number1'] = oe_clean
            df['ys_oe1'] = oe_clean
            # 更新时间
            df['updateTime'] = str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            df['update1'] = str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            # 名称
            df['product_name1'] = df['零件名称']
            # 品牌
            df['brand_name1'] = df['产地'].str.replace(' ', '').replace('正厂', '原厂件')
            # 供应商
            df['seller_name1'] = supplier_name  # 使用当前供应商名称
            # 价格
            df['price1'] = df['价格']
            # 库存
            df['quantity1'] = df['库存数']
            # 地区
            df['city_name'] = '广州'
            # 备注
            df['make_vehicle1'] = df['通用车型']
            df['spider_date1'] = str(datetime.now().strftime('%Y-%m-%d'))
            df['make_name1'] = ''
            df = df[['spider_date1', 'oe_number1','ys_oe1','update1','product_name1','brand_name1','seller_name1','quantity1',
                     'price1','make_name1','make_vehicle1','city_name']]

            df = df[['seller_name1', 'oe_number1', 'ys_oe1', 'brand_name1', 'price1', 'city_name', 'quantity1']]
            all_dataframes.append(df)

    if all_dataframes:
        return pd.concat(all_dataframes, ignore_index=True)
    else:
        return pd.DataFrame()  # 返回空DataFrame


def fetch_and_process_latest_data():
    """读取 jqr_data 最新日期数据，合并广星（鑫峰已停用），处理后保存"""
    host = '113.45.176.129'
    port = 3306
    user = 'fsbbr_data'
    password = 'wRCA8AGn3a568f4X'
    database = 'fsbbr_data'

    # 连接MySQL数据库
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        charset='utf8mb4'
    )

    try:
        # 先查询最新日期
        latest_date_query = """
        SELECT DATE(MAX(spider_date1)) as latest_date 
        FROM jqr_data
        """

        latest_date_result = pd.read_sql_query(latest_date_query, conn)
        latest_date = latest_date_result['latest_date'].iloc[0]

        if latest_date is None:
            logger.info("数据库中没有数据")
            return None

        logger.info(f"最新数据日期: {latest_date}")

        # 查询最新日期的所有数据
        data_query = f"""
        SELECT seller_name1, oe_number1, ys_oe1, brand_name1, price1, city_name, quantity1
        FROM jqr_data 
        WHERE DATE(spider_date1) = '{latest_date}'
        """

        # 读取数据
        df = pd.read_sql_query(data_query, conn)
        df2 = get_zhuozhixing_multi()  # 使用新函数获取广星数据（鑫峰已停用）
        df = pd.concat([df, df2])

        if df.empty:
            logger.info(f"在 {latest_date} 没有找到数据")
            return None

        # 应用品牌名称映射
        df['brand_name1'] = df['brand_name1'].apply(normalize_brand)

        # 仓库名称映射
        city_mapping = {
            "佛山": "佛山禅城仓",
            "广州": "广州越秀仓"
        }

        # 应用仓库名称映射
        df['city_name'] = df['city_name'].replace(city_mapping)
        # 直接使用 ys_oe1 作为 OE 码，不做处理
        df['oe_number1'] = df['ys_oe1']
        # 计算当前时间+1天作为失效时间
        expiry_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

        # 创建新的DataFrame，匹配Excel表头
        result_df = pd.DataFrame({
            '供应商名称': df['seller_name1'],
            '原厂OE码': df['oe_number1'],  # 修改列名
            '品牌': df['brand_name1'],
            '价格': df['price1'],
            '失效时间': expiry_date,  # 当前时间+1天
            '仓库名称': df['city_name'],
            '库存': df['quantity1'],
            '备注': ''
        })

        # 按照'供应商名称', '原厂oe码', '品牌'去重，保留第一次出现的记录
        result_df = result_df.drop_duplicates(subset=['供应商名称', '原厂OE码', '品牌'], keep='first')

        # 批量保存到数据库
        db_manager = get_db_connection()
        try:
            # 批量插入数据
            batch_size = 1000  # 批量处理大小
            fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 保存原价格
            result_df['原价格'] = result_df['价格']

            # 根据品牌处理价格
            result_df['价格'] = result_df.apply(lambda row: process_price_by_brand(row['价格'], row['品牌']), axis=1)

            # 保存原始数据到机器人数据表
            for i in range(0, len(result_df), batch_size):
                batch = result_df.iloc[i:i + batch_size]

                # 准备批量插入数据
                batch_data = []
                for index, row in batch.iterrows():
                    batch_data.append((
                        row['供应商名称'],
                        row['原厂OE码'],
                        row['品牌'],
                        row['价格'],
                        row['失效时间'],
                        row['仓库名称'],
                        row['库存'],
                        row['备注'],
                        fetch_time  # 拉取时间
                    ))

                # 批量插入到机器人数据表
                sql = """
                    INSERT INTO robot_data (supplier_name, oe_number, brand_name, price, expiry_date, city_name, quantity, remark, fetch_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                db_manager.execute_many(sql, batch_data)
                logger.info(f"已批量保存 {min(i + batch_size, len(result_df))} / {len(result_df)} 条机器人数据到机器人数据表")

        finally:
            db_manager.close()

        # 将数据保存到各公司整合表（机器人数据不是万拓也不是昌盛）
        save_to_company_tables(result_df, is_wantuo=False, is_changsheng=False)

        logger.info(f"成功保存 {len(result_df)} 条机器人数据到数据库")
        return result_df

    except Exception as e:
        logger.exception(f"处理数据时发生错误")
        return None
    finally:
        conn.close()
