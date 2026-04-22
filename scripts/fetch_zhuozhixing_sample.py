# -*- coding: utf-8 -*-
"""
获取卓之星API原数据示例

用于查看佛山万拓（或其他供应商）的价格数据
"""

import requests
import json


def fetch_price_data(supplier_name, gsign, sample_size=50):
    """
    获取卓之星API的价格数据样本

    Args:
        supplier_name: 供应商名称（用于显示）
        gsign: 供应商密钥
        sample_size: 获取的样本数量（默认50条）
    """
    psign = "7be06d54152d0bd916f09b0b055f76ad"
    base_url = "http://api.inheartsoft.com/dw-api/kc2018"

    print(f"\n{'='*60}")
    print(f"供应商: {supplier_name}")
    print(f"gsign: {gsign}")
    print(f"{'='*60}\n")

    # 第一步：获取 allkckey
    print("[1/2] 正在获取 allkckey...")
    url = f"{base_url}?psign={psign}&gsign={gsign}&mode=allkckey"
    try:
        response = requests.get(url, timeout=30)
        data = response.json()
        allkckey = data.get('allkckey')
        print(f"✓ allkckey: {allkckey}\n")
    except Exception as e:
        print(f"✗ 获取 allkckey 失败: {e}")
        return

    # 第二步：获取数据样本
    print(f"[2/2] 正在获取前 {sample_size} 条数据...")
    url = f"{base_url}?psign={psign}&gsign={gsign}&allkckey={allkckey}&mode=all_kc&pindex=1"
    try:
        response = requests.get(url, timeout=30)
        data = response.json()
        raw_list = data.get('list', [])

        if not raw_list:
            print("✗ 没有获取到数据")
            return

        # 只取前几条
        sample = raw_list[:sample_size]
        print(f"✓ 本页共 {len(raw_list)} 条，展示前 {len(sample)} 条的价格\n")

    except Exception as e:
        print(f"✗ 获取数据失败: {e}")
        return

    # 打印价格数据
    print(f"{'='*60}")
    print(f"{'序号':<6}{'零件编码':<20}{'零件名称':<25}{'价格':<10}")
    print(f"{'-'*60}")

    for i, item in enumerate(sample, 1):
        pjcode = item.get('pjcode', '')[:18]  # 截断避免过长
        pjname = item.get('pjname', '')[:23]  # 截断避免过长
        xsprice = item.get('xsprice', '')
        print(f"{i:<6}{pjcode:<20}{pjname:<25}{xsprice:<10}")

    print(f"{'='*60}")
    print(f"数据总数: {len(raw_list)} 条（仅第1页）")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    # 佛山万拓
    fetch_price_data(
        supplier_name="佛山万拓",
        gsign="EFA9CC150A42AA1AAD67B069606C3B71",
        sample_size=50
    )

    # 如需查看其他供应商，取消下面的注释：
    # fetch_price_data("广星", "9F478C130BCD573232B129C5928F0B42", 50)
    # fetch_price_data("鑫峰", "B810A2A5ABAE10EAEE19B3BE563B24A9", 50)
