# -*- coding: utf-8 -*-
"""
佛山万拓库存数据获取模块

从卓之星API获取库存数据，并格式化为虚拟库存标准格式
"""

import requests
import json
import re
import time
from datetime import datetime, timedelta
import pandas as pd
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')



API_BASE_URL = "http://api.inheartsoft.com/dw-api/kc2018"
API_PSIGN = "7be06d54152d0bd916f09b0b055f76ad"
GSIGN = "EFA9CC150A42AA1AAD67B069606C3B71"


def clean_oecode(pjcode):
    """
    清洗零件编码，生成标准OE码

    处理步骤：
    1. 去掉所有空格
    2. 去掉 '-' 及后面的所有内容
    3. 去掉所有中文字符

    :param pjcode: 原始零件编码
    :return: 清洗后的OE码
    """
    if pd.isna(pjcode) or pjcode == '':
        return ''

    code = str(pjcode)
    # 1. 去掉所有空格
    code = code.replace(' ', '')
    # 2. 去掉 '-' 及后面的所有内容
    code = code.split('-')[0]
    # 3. 去掉所有中文字符
    code = re.sub(r'[\u4e00-\u9fa5]+', '', code)

    return code


def get_allkckey():
    """
    获取库存查询密钥
    """
    url = f"{API_BASE_URL}?psign={API_PSIGN}&gsign={GSIGN}&mode=allkckey"
    response = requests.get(url, timeout=30)
    data = response.json()
    return data['allkckey']


def get_inventory_page(allkckey, pindex):
    """
    获取单页库存数据

    :param allkckey: 库存查询密钥
    :param pindex: 页码（从1开始）
    :return: 该页响应数据字典
    """
    url = f"{API_BASE_URL}?psign={API_PSIGN}&gsign={GSIGN}&allkckey={allkckey}&mode=all_kc&pindex={pindex}"
    response = requests.get(url, timeout=30)
    return response.json()


def get_all_inventory():
    """
    获取所有库存数据（自动分页）

    :return: 所有数据列表
    """
    all_data = []

    # 第一步：获取密钥
    allkckey = get_allkckey()
    logger.info(f"[佛山万拓] 获取到allkckey: {allkckey}")

    # 第二步：分页获取数据
    pindex = 1
    logger.info(f"[佛山万拓] 开始分页获取数据...")

    while True:
        page_data = None
        last_error = None

        for attempt in range(3):
            try:
                data = get_inventory_page(allkckey, pindex)

                if data.get('msgcode') == 9:
                    logger.warning(f"[佛山万拓] 第 {pindex} 页 allkckey无效或已超时，重新获取key (attempt={attempt + 1})")
                    try:
                        allkckey = get_allkckey()
                        logger.info(f"[佛山万拓] 重新获取到allkckey: {allkckey}")
                    except Exception:
                        logger.exception("[佛山万拓] 重新获取allkckey失败")
                    last_error = data.get('msgtext')
                    continue

                if data.get('msgcode') != 0:
                    logger.warning(f"[佛山万拓] 第 {pindex} 页 接口返回异常: msgcode={data.get('msgcode')}, msgtext={data.get('msgtext')}")
                    last_error = data.get('msgtext')
                    continue

                page_data = data.get('list')
                if page_data is None:
                    logger.warning(f"[佛山万拓] 第 {pindex} 页 响应中缺少list字段: {json.dumps(data, ensure_ascii=False)[:500]}")
                    last_error = 'missing list'
                    continue
                break
            except Exception as e:
                logger.exception(f"[佛山万拓] 第 {pindex} 页第{attempt + 1}次请求失败")
                last_error = str(e)

        if page_data is None:
            raise RuntimeError(f"[佛山万拓] 第 {pindex} 页最终失败，原因: {last_error}")

        if pindex == 1 and not page_data:
            raise RuntimeError(f"[佛山万拓] 第一页数据为空，allkckey={allkckey}")

        if not page_data:
            # 没有数据了，结束循环
            break

        all_data.extend(page_data)
        logger.info(f"[佛山万拓] 第 {pindex} 页: {len(page_data)} 条")

        pindex += 1
        # 添加延时，避免请求过快
        time.sleep(0.5)

    logger.info(f"[佛山万拓] 共获取 {len(all_data)} 条数据")
    return all_data


def start():
    """
    佛山万拓库存数据获取入口

    从卓之星API获取数据，转换为虚拟库存标准格式

    :return: 标准格式的DataFrame
        ['供应商名称', '原厂OE码', '品牌', '价格', '失效时间', '仓库名称', '库存', '备注']
    """
    # 1. 获取所有数据
    raw_data = get_all_inventory()
    if not raw_data:
        raise RuntimeError("[佛山万拓] 没有获取到数据")

    # 2. 转换为DataFrame
    df = pd.DataFrame(raw_data)

    # 3. 计算失效时间（当前时间 + 1天）
    tomorrow_ts = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

    # 4. 字段映射和转换
    df['供应商名称'] = '佛山万拓'
    df['原厂OE码'] = df['pjcode'].apply(clean_oecode)

    # 品牌映射
    brand_mapping = {
        'WANTUO': '巴博瑞',
        '菲儿': '菲尔',
        '品牌': '巴博瑞'
    }
    df['品牌'] = df['pjfactory'].fillna('')
    df['品牌'] = df['品牌'].replace(brand_mapping)

    # 只保留品牌为'菲尔'和'巴博瑞'的数据
    df = df[df['品牌'].isin(['菲尔', '巴博瑞'])]

    df['价格'] = df['xsprice'].fillna(0)
    df['失效时间'] = str(tomorrow_ts)
    df['仓库名称'] = '佛山禅城仓'
    df['库存'] = df['kcamount'].fillna(0).astype(int)
    df['备注'] = df['pjgensize'].fillna('')

    # 5. 库存大于30的设为30
    df.loc[df['库存'] > 30, '库存'] = 30

    # 6. 选择需要的列
    df = df[['供应商名称', '原厂OE码', '品牌', '价格', '失效时间', '仓库名称', '库存', '备注']]

    logger.info(f"[佛山万拓] 数据处理完成，共 {len(df)} 条")
    return df


if __name__ == "__main__":
    df = start()
    logger.info(f"\n数据预览：")
    logger.info(df.head(10))
    logger.info(f"\n数据形状: {df.shape}")
