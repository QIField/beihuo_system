# -*- coding: utf-8 -*-
"""
盛旻库存数据获取模块

从卓之星API获取库存数据，并格式化为虚拟库存标准格式
"""

import requests
import json
import time
import re
from datetime import datetime, timedelta
import pandas as pd


API_BASE_URL = "http://api.inheartsoft.com/dw-api/kc2018"
API_PSIGN = "7be06d54152d0bd916f09b0b055f76ad"
GSIGN = "925A988C98A919C18C1D393F85A693A5"


# 保留的品牌列表
ALLOWED_BRANDS = [
    '原厂(SJZX)', '爱斯达克', '采埃孚', '盖茨', '斯泰必鲁斯', '蒙诺', '曼牌', '斯凯孚',
    'VDO', 'ATE', '萨克斯', '进口威巴克', '伊顿', '天博', '华克', '萨来力', 'AMK',
    '京西重工', '法雷奥', '博世', '索恩格', 'FC', '博格华纳BORG', 'TRW', '德尔福',
    '博世(BOSCH)BS', '岱高进口'
]


# 品牌映射
BRAND_MAPPING = {
    'FC': '巴博瑞',
    'TRW': '天合',
    'VDO': '威迪欧',
    '博格华纳BORG': '博格华纳',
    '博世(BOSCH)BS': '博世',
    '岱高进口': '岱高',
    '进口威巴克': '威巴克',
    '原厂(SJZX)': '原厂'
}


def clean_oecode(code):
    """
    清洗OE码
    1. 去掉 - 及后面的所有内容
    2. 去掉末尾的中文
    3. 去掉末尾的英文字母
    """
    if pd.isna(code) or code == '':
        return ''
    code = str(code).strip()
    # 1. 先去掉 - 及后面的所有内容
    code = code.split('-')[0]
    # 2. 去掉末尾的中文
    code = re.sub(r'[\u4e00-\u9fa5]+$', '', code)
    # 3. 去掉末尾的英文字母（只去掉末尾连续的字母）
    code = re.sub(r'[A-Za-z]+$', '', code)
    return code


def get_allkckey():
    """
    获取库存查询密钥

    :return: allkckey字符串，失败返回None
    """
    url = f"{API_BASE_URL}?psign={API_PSIGN}&gsign={GSIGN}&mode=allkckey"
    try:
        response = requests.get(url, timeout=30)
        data = response.json()
        return data.get('allkckey')
    except Exception as e:
        print(f"获取allkckey失败: {e}")
        return None


def get_inventory_page(allkckey, pindex):
    """
    获取单页库存数据

    :param allkckey: 库存查询密钥
    :param pindex: 页码（从1开始）
    :return: 该页原始数据列表，失败返回空列表
    """
    url = f"{API_BASE_URL}?psign={API_PSIGN}&gsign={GSIGN}&allkckey={allkckey}&mode=all_kc&pindex={pindex}"
    try:
        response = requests.get(url, timeout=30)
        data = response.json()
        return data.get('list', [])
    except Exception as e:
        print(f"获取第{pindex}页数据失败: {e}")
        return []


def get_all_inventory():
    """
    获取所有库存数据（自动分页）

    :return: 所有原始数据列表
    """
    all_data = []

    # 第一步：获取密钥
    allkckey = get_allkckey()
    if not allkckey:
        return all_data

    print(f"[盛旻] 获取到allkckey: {allkckey}")

    # 第二步：分页获取数据
    pindex = 1
    print(f"[盛旻] 开始分页获取数据...")

    while True:
        page_data = get_inventory_page(allkckey, pindex)

        if not page_data:
            # 没有数据了，结束循环
            break

        all_data.extend(page_data)
        print(f"[盛旻] 第 {pindex} 页: {len(page_data)} 条")

        pindex += 1
        # 添加延时，避免请求过快
        time.sleep(0.5)

    print(f"[盛旻] 共获取 {len(all_data)} 条原始数据")
    return all_data


def start():
    """
    盛旻库存数据获取入口

    从卓之星API获取数据，转换为虚拟库存标准格式

    :return: 标准格式的DataFrame
        ['供应商名称', '原厂OE码', '品牌', '价格', '失效时间', '仓库名称', '库存', '备注']
    """
    # 1. 获取所有原始数据
    raw_data = get_all_inventory()
    if not raw_data:
        print("[盛旻] 没有获取到数据")
        return pd.DataFrame(columns=['供应商名称', '原厂OE码', '品牌', '价格', '失效时间', '仓库名称', '库存', '备注'])

    # 2. 转换为DataFrame
    df = pd.DataFrame(raw_data)

    # 3. 计算失效时间（当前时间 + 1天）
    tomorrow_ts = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

    # 4. 筛选只保留指定品牌的数据
    df = df[df['pjbrand'].isin(ALLOWED_BRANDS)]
    print(f"[盛旻] 品牌筛选后剩余 {len(df)} 条数据")

    # 5. 字段映射和转换
    df['供应商名称'] = '盛旻'
    df['原厂OE码'] = df['pjcode'].apply(clean_oecode)
    df['品牌'] = df['pjbrand'].replace(BRAND_MAPPING)
    df['价格'] = df['sxpfprice'].fillna(0)
    df['失效时间'] = str(tomorrow_ts)
    df['仓库名称'] = '广州越秀仓'
    df['库存'] = df['kcamount'].fillna(0).astype(int)
    df['备注'] = df['pjtype'].fillna('')

    # 6. 选择需要的列
    df = df[['供应商名称', '原厂OE码', '品牌', '价格', '失效时间', '仓库名称', '库存', '备注']]

    print(f"[盛旻] 数据处理完成，共 {len(df)} 条")
    return df


if __name__ == "__main__":
    df = start()
    print(f"\n数据预览：")
    print(df.head(10))
    print(f"\n数据形状: {df.shape}")
