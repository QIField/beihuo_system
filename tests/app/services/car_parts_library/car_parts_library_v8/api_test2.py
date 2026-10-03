# -*- coding:utf-8 -*-
# @Time    : 2026/6/6 10:04
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : api_test2.py
# @Software: PyCharm
import requests
import json

def fetch_realtime_part_info(part_number, base_url="http://x.fsbbr.net"):
    """
    实时获取零件信息
    
    Args:
        part_number (str): 零件编号
        base_url (str): 基础URL，默认为 http://x.fsbbr.net
    
    Returns:
        dict: 响应结果
    """
    url = f"{base_url}/new/api/car-parts/fetch-realtime"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "key": "7Y4Y6RNdkDCwTJDJEBWz",
        "part_number": part_number
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # 检查HTTP错误
        return response.json()
    except requests.exceptions.RequestException as e:
        return {
            "code": 500,
            "msg": f"请求失败: {str(e)}",
            "data": None
        }

# 使用示例
if __name__ == "__main__":
    # 调用函数
    result = fetch_realtime_part_info("A2642000301")
    
    # 处理结果
    if result.get('code') == 200:
        print("获取成功！")
        data = result.get('data')
        print(f"零件编号: {data.get('part_number')}")
        print(f"零件描述: {data.get('part_info', {}).get('description_cn')}")
        print(f"库存数量: {len(data.get('stock_info', []))}")
    else:
        print(f"获取失败: {result.get('msg')}")