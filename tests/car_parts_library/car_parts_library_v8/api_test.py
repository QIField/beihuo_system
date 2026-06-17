import requests
import json

# 接口地址
url = "http://x.fsbbr.net/new/api/car-parts/fetch-realtime"

# 请求头
headers = {
    "Content-Type": "application/json"
}

# 请求参数
payload = {
    "key": "7Y4Y6RNdkDCwTJDJEBWz",
    "part_number": "A2642000301"  # 替换为实际零件编号
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
        print(f"零件编号: {data.get('part_number')}")
        print(f"零件信息: {json.dumps(data.get('part_info'), ensure_ascii=False, indent=2)}")
        print(f"库存信息: {json.dumps(data.get('stock_info'), ensure_ascii=False, indent=2)}")
    else:
        print(f"错误: {result.get('msg')}")
        
except Exception as e:
    print(f"请求失败: {str(e)}")