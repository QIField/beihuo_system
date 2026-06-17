# 实时获取宝马零件信息接口文档

## 接口信息
**接口名称**: 实时获取宝马零件信息和库存信息（不入库）
**请求方法**: POST
**请求URL**: /new/api/car-parts/bmw/fetch-realtime

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
    "part_number": "零件编号",
    "cookie": "BMW Brilliance 登录态 Cookie（可选）"
}
```

### 参数说明
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| key | String | 是 | 接口密钥，固定值：7Y4Y6RNdkDCwTJDJEBWz |
| part_number | String | 是 | 零件编号（OE号），例如：22118835572 |
| cookie | String | 否 | BMW Brilliance 登录态 Cookie；不传或为空时，将使用系统配置（bmw_car_parts_libray.cookie）中的 Cookie |

---

## 响应示例

### 成功响应 (200)
```json
{
    "code": 200,
    "msg": "获取成功",
    "data": {
        "detail": {
            "oe": "22118835572",
            "零件名": "零件名称",
            "基本单元": "件",
            "族组": "物料组",
            "毛重": "1.067 KG",
            "净重": "0.980 KG",
            "体积": "22.040 CDM",
            "零售价": "1234.56",
            "经销商折扣(Stock)": "25%",
            "经销商折扣(Rush)": "20%",
            "经销商净值(Stock)": "925.92",
            "经销商净值(Rush)": "987.65",
            "可用库存": "35 件",
            "采集时间": "2026-06-17 10:30:00"
        },
        "stock": {
            "oe": "22118835572",
            "零件": "零件名称",
            "折扣代码": "XXXXX",
            "零售价": "1234.56",
            "销售单位": "件",
            "库房-北京": "10",
            "在途-北京": "5",
            "再定购点-北京": "20",
            "主仓-北京": "15",
            "库房-上海": "8",
            "在途-上海": "3",
            "再定购点-上海": "15",
            "主仓-上海": "12",
            "库房-佛山": "5",
            "在途-佛山": "2",
            "再定购点-佛山": "10",
            "主仓-佛山": "8",
            "库房-成都": "3",
            "在途-成都": "1",
            "再定购点-成都": "8",
            "主仓-成都": "5",
            "库房-沈阳": "4",
            "在途-沈阳": "0",
            "再定购点-沈阳": "6",
            "主仓-沈阳": "3",
            "库房-合肥": "2",
            "在途-合肥": "1",
            "再定购点-合肥": "5",
            "主仓-合肥": "4",
            "库房-宁波": "3",
            "在途-宁波": "1",
            "再定购点-宁波": "5",
            "主仓-宁波": "3",
            "采集时间": "2026-06-17 10:30:00"
        }
    }
}
```

### 响应字段说明

#### data 字段结构：

| 字段 | 说明 |
|------|------|
| detail | 零件详细信息（来自宝马零件详情页面数据，中文 key） |
| stock | 库存信息（来自宝马库存检查页面数据，含 7 个仓库信息：北京、上海、佛山、成都、沈阳、合肥、宁波，中文 key） |

---

## 错误响应示例

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

### 密钥验证失败 (403)
```json
{
    "code": 403,
    "msg": "密钥验证失败",
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

### 参数错误 - Cookie 未配置 (400)
```json
{
    "code": 400,
    "msg": "参数错误: 未配置 BMW Brilliance 登录 Cookie，请在请求中传入 cookie 或在配置中设置",
    "data": null
}
```

### 数据未查询到 (404)
```json
{
    "code": 404,
    "msg": "数据未查询到: 具体错误信息",
    "data": null
}
```

### 数据解析失败 / Cookie 失效 (502)
```json
{
    "code": 502,
    "msg": "数据解析(请查看是否cookie不正确)失败: 具体错误信息",
    "data": null
}
```

### 爬虫异常 (502)
```json
{
    "code": 502,
    "msg": "爬虫异常: 具体错误信息",
    "data": null
}
```

### 服务器内部错误 (500)
```json
{
    "code": 500,
    "msg": "获取数据失败: 具体错误信息",
    "data": null
}
```

---

## 错误码说明
| 错误码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误（密钥/零件号为空、Cookie未配置等） |
| 403 | 密钥验证失败 |
| 404 | 数据未查询到（零件不存在或未激活） |
| 502 | 爬虫请求失败（Cookie 失效、页面结构变更、网络问题等） |
| 500 | 服务器内部错误 |

---

## 使用说明
1. 该接口用于实时从 **BMW Brilliance（华晨宝马）** 配件库获取零件信息和库存信息，数据不会存入本地数据库
2. 请求必须携带有效的密钥，密钥固定为：7Y4Y6RNdkDCwTJDJEBWz
3. part_number 为必填参数，用于指定要查询的零件编号（OE号）
4. cookie 为可选参数；不传或为空时自动使用系统配置中的 Cookie
5. 返回的数据包含完整的零件信息（detail）和 7 个仓库的库存信息（stock），均为中文 key

---

## Python 示例代码

### 示例 1: 使用 requests 库
```python
import requests
import json

# 接口地址
url = "http://x.fsbbr.net/new/api/car-parts/bmw/fetch-realtime"

# 请求头
headers = {
    "Content-Type": "application/json"
}

# 请求参数
payload = {
    "key": "7Y4Y6RNdkDCwTJDJEBWz",
    "part_number": "22118835572"  # 替换为实际零件编号
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
```

### 示例 2: 使用自定义 Cookie
```python
import requests
import json

# 接口地址
url = "http://x.fsbbr.net/new/api/car-parts/bmw/fetch-realtime"

# 请求头
headers = {
    "Content-Type": "application/json"
}

# 请求参数（携带自定义 Cookie）
payload = {
    "key": "7Y4Y6RNdkDCwTJDJEBWz",
    "part_number": "22118835572",
    "cookie": "sessionid=xxxxxxxxxxx; csrftoken=yyyyyyyy"  # 自定义 BMW Brilliance 登录 Cookie
}

try:
    response = requests.post(url, headers=headers, json=payload)
    result = response.json()
    
    if result.get('code') == 200:
        print("获取成功！")
        data = result.get('data')
        print(f"零件信息: {json.dumps(data.get('detail'), ensure_ascii=False, indent=2)}")
        print(f"库存信息: {json.dumps(data.get('stock'), ensure_ascii=False, indent=2)}")
    else:
        print(f"获取失败: {result.get('msg')}")

except Exception as e:
    print(f"请求失败: {str(e)}")
```

### 示例 3: 封装为函数
```python
import requests
import json

def fetch_realtime_part_info_bmw(part_number, cookie=None, base_url="http://x.fsbbr.net"):
    """
    实时获取宝马零件信息
    
    Args:
        part_number (str): 零件编号
        cookie (str, optional): BMW Brilliance 登录态 Cookie，不传时使用配置中的 Cookie
        base_url (str): 基础URL，默认为 http://x.fsbbr.net
    
    Returns:
        dict: 响应结果
    """
    url = f"{base_url}/new/api/car-parts/bmw/fetch-realtime"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "key": "7Y4Y6RNdkDCwTJDJEBWz",
        "part_number": part_number
    }
    
    if cookie:
        payload["cookie"] = cookie
    
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
    # 调用函数（使用系统配置中的 Cookie）
    result = fetch_realtime_part_info_bmw("22118835572")
    
    # 处理结果
    if result.get('code') == 200:
        print("获取成功！")
        data = result.get('data')
        detail = data.get('detail', {})
        stock = data.get('stock', {})
        print(f"零件名: {detail.get('零件名')}")
        print(f"零售价: {detail.get('零售价')}")
        print(f"北京库房: {stock.get('库房-北京')}")
    else:
        print(f"获取失败: {result.get('msg')}")
```
