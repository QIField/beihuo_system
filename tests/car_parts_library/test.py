# -*- coding:utf-8 -*-
# @Time    : 2026/6/17 15:55
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : test.py
# @Software: PyCharm
import requests
import json

# 接口地址
url = "http://127.0.0.1:5000/new/api/car-parts/bmw/fetch-realtime"

# 请求头
headers = {
    "Content-Type": "application/json"
}

# 请求参数
payload = {
    "key": "7Y4Y6RNdkDCwTJDJEBWz",
    "part_number": "28108070791"  # 替换为实际零件编号
}

try:
    # 发送 POST 请求
    response = requests.post(url, headers=headers, data=json.dumps(payload))

    # 打印状态码
    print(f"状态码: {response.status_code}")

    # 解析响应数据
    result = response.json()

    # 打印响应结果
    print(f"响应消息: {result.get('msg')}")
    if result.get('code') == 200:
        data = result.get('data')
        print(f"零件信息: {json.dumps(data.get('detail'), ensure_ascii=False, indent=2)}")
        print(f"库存信息: {json.dumps(data.get('stock'), ensure_ascii=False, indent=2)}")
    else:
        print(f"错误: {result.get('msg')}")

except Exception as e:
    print(f"请求失败: {str(e)}")