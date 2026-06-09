# 实时获取零件信息接口文档

## 接口信息
**接口名称**: 实时获取零件信息和库存信息（不入库）
**请求方法**: POST
**请求URL**: /new/api/car-parts/fetch-realtime

---

## 请求头
| 键 | 值 |
|----|-----|
| Content-Type | application/json |

---

## 请求参数 (Body - raw JSON)
```json
{
    "key": "7Y4Y6RNdkDCwTJDJEBWz",
    "part_number": "零件编号"
}
```

### 参数说明
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| key | String | 是 | 接口密钥，固定值：7Y4Y6RNdkDCwTJDJEBWz |
| part_number | String | 是 | 零件编号 |

---

## 响应示例

### 成功响应 (200)
```json
{
    "code": 200,
    "msg": "获取成功",
    "data": {
        "part_number": "零件编号",
        "part_info": {
            "part_number": "零件编号",
            "descriptions": "英文描述",
            "description_cn": "中文描述",
            "marketing_code": "营销代码",
            "dealer_discount_group": "经销商折扣组",
            "msrp": 100.0,
            "dealer_fixed_nominal_margin": 10.0,
            "wholesale_price": 90.0,
            "marketing_code_description": "营销代码描述",
            "quantity_unit": "数量单位",
            "sales_pack_size": "销售包装规格",
            "weight": 1000,
            "length": "100",
            "width": "50",
            "height": "30",
            "effective_date": "2026-01-01",
            "data_source": "mercedes",
            "l_model_zh": "车型中文名",
            "brand": "奔驰",
            "category": "分类",
            "ccc_mark": "CCC标识",
            "volume": 0.15,
            "hazmat_code": "危险货物代码",
            "origin_country": "德国",
            "shelf_life": "存储期限",
            "is_hazmat": "否",
            "purchase_price": 85.0,
            "part_nr_info_super_session": "{}"
        },
        "stock_info": [
            {
                "location": "仓库位置",
                "quantity": 100,
                "available_quantity": 95
            }
        ]
    }
}
```

### 密钥验证失败 (403)
```json
{
    "code": 403,
    "msg": "密钥验证失败",
    "data": null
}
```

### 请求参数为空 (400)
```json
{
    "code": 400,
    "msg": "请求参数不能为空",
    "data": null
}
```

### 密钥为空 (400)
```json
{
    "code": 400,
    "msg": "密钥不能为空",
    "data": null
}
```

### 零件编号为空 (400)
```json
{
    "code": 400,
    "msg": "零件编号不能为空",
    "data": null
}
```

### 服务器错误 (500)
```json
{
    "code": 500,
    "msg": "获取数据失败: 错误信息",
    "data": null
}
```

---

## 错误码说明
| 错误码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 403 | 密钥验证失败 |
| 500 | 服务器内部错误 |

---

## 使用说明
1. 该接口用于实时从奔驰大库获取零件信息和库存信息，数据不会存入本地数据库
2. 请求必须携带有效的密钥，密钥固定为：7Y4Y6RNdkDCwTJDJEBWz
3. part_number为必填参数，用于指定要查询的零件编号
4. 返回的数据包含完整的零件信息和库存信息列表

---

## Python 示例代码

### 示例 1: 使用 requests 库
```python
import requests
import json

# 接口地址
url = "http://localhost:5000/new/api/car-parts/fetch-realtime"

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
```


### 示例 2: 封装为函数
```python
import requests
import json

def fetch_realtime_part_info(part_number, base_url="http://localhost:5000"):
    """
    实时获取零件信息
    
    Args:
        part_number (str): 零件编号
        base_url (str): 基础URL，默认为 http://localhost:5000
    
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
```

**注意**: 请将 `http://localhost:5000` 替换为实际的服务器地址和端口。
