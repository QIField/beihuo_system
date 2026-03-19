# -*- coding: utf-8 -*-
"""
卓之星API客户端

负责从卓之星API获取库存数据
"""

import requests
import json
import time
from typing import List, Dict, Any, Optional
from .config import API_BASE_URL, API_PSIGN, MAX_RETRIES, RETRY_DELAY


class ZhuoZhiXingAPIClient:
    """卓之星API客户端"""

    def __init__(self, gsign: str):
        """
        初始化API客户端

        Args:
            gsign: 供应商签名（每个供应商不同）
        """
        self.gsign = gsign
        self.psign = API_PSIGN
        self.session = requests.Session()

    def _make_request(self, url: str) -> Optional[Dict[str, Any]]:
        """
        发送HTTP请求，带重试机制

        Args:
            url: 请求URL

        Returns:
            响应JSON数据，失败返回None
        """
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"    请求失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"    ✗ 请求最终失败: {url}")
                    return None
        return None

    def get_allkckey(self) -> Optional[str]:
        """
        获取库存查询密钥

        Returns:
            allkckey字符串，失败返回None
        """
        url = f"{API_BASE_URL}?psign={self.psign}&gsign={self.gsign}&mode=allkckey"
        print(f"  正在获取库存密钥...")

        data = self._make_request(url)
        if data and 'allkckey' in data:
            allkckey = data['allkckey']
            print(f"  ✓ 获取成功: {allkckey}")
            return allkckey
        else:
            print(f"  ✗ 获取库存密钥失败")
            return None

    def get_inventory_page(self, allkckey: str, pindex: int) -> List[Dict[str, Any]]:
        """
        获取单页库存数据

        Args:
            allkckey: 库存查询密钥
            pindex: 页码（从1开始）

        Returns:
            该页数据列表，失败返回空列表
        """
        url = f"{API_BASE_URL}?psign={self.psign}&gsign={self.gsign}&allkckey={allkckey}&mode=all_kc&pindex={pindex}"

        data = self._make_request(url)
        if data and 'list' in data:
            return data['list']
        else:
            return []

    def get_all_inventory(self) -> List[Dict[str, Any]]:
        """
        获取所有库存数据（自动分页）

        Returns:
            所有数据列表
        """
        all_data = []

        # 第一步：获取密钥
        allkckey = self.get_allkckey()
        if not allkckey:
            return all_data

        # 第二步：分页获取数据
        pindex = 1
        print(f"  开始分页获取数据...")

        while True:
            page_data = self.get_inventory_page(allkckey, pindex)

            if not page_data:
                # 没有数据了，结束循环
                break

            all_data.extend(page_data)
            print(f"    第 {pindex} 页: {len(page_data)} 条")

            pindex += 1

        print(f"  ✓ 共获取 {len(all_data)} 条数据")
        return all_data


def fetch_supplier_data(supplier_name: str, gsign: str) -> List[Dict[str, Any]]:
    """
    获取指定供应商的所有库存数据

    Args:
        supplier_name: 供应商名称（用于日志）
        gsign: 供应商签名

    Returns:
        库存数据列表
    """
    print(f"\n[{supplier_name}] 开始获取数据...")
    client = ZhuoZhiXingAPIClient(gsign)
    return client.get_all_inventory()
