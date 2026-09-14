# -*- coding:utf-8 -*-
"""
测试 benz_parts_api.fetch_realtime_data（/new/api/car-parts/fetch-realtime）
直接发起真实 HTTP 请求，需先启动服务（默认本机 5000 端口）。

运行方式：
    python -m tests.app.api.car_parts_api.benz_parts_api_test
"""
import json
import os
import requests

# 接口地址，可用环境变量 BENZ_API_BASE 覆盖，默认本机开发服务
BASE_URL = os.environ.get('BENZ_API_BASE', 'http://127.0.0.1:5000/new/api/car-parts')


def test_fetch_realtime_data(part_number='e1111', key='7Y4Y6RNdkDCwTJDJEBWz'):
    """
    测试实时获取零件信息和库存信息接口

    :param part_number: 零件编号
    :param key: 接口密钥
    :return: 接口返回的 data 字典；请求失败则抛出异常
    """
    url = f"{BASE_URL}/fetch-realtime"
    headers = {"Content-Type": "application/json"}
    payload = {
        "key": key,
        "part_number": part_number
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    print(f"状态码: {response.status_code}")

    result = response.json()
    print(result)
    print(f"响应消息: {result.get('msg')}")

    assert response.status_code == 200, f"HTTP 状态码异常: {response.status_code}"
    assert result.get('code') == 200, f"业务码异常: {result.get('code')}, msg: {result.get('msg')}"

    data = result.get('data')
    print(f"零件编号: {data.get('part_number')}")
    print(f"零件信息: {json.dumps(data.get('part_info'), ensure_ascii=False, indent=2)}")
    print(f"库存信息: {json.dumps(data.get('stock_info'), ensure_ascii=False, indent=2)}")
    return data


if __name__ == '__main__':
    test_fetch_realtime_data()
