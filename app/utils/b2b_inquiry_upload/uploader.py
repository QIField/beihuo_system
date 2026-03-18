"""
B2B上传核心模块
复用virtual_inventory的B2B上传逻辑
"""

import pandas as pd
import json
import requests
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


def login(company='fsbbr'):
    """
    登录B2B系统获取Token
    复用virtual_inventory的登录逻辑
    """
    config = {
        'fsbbr': {
            "AccessKeyId": "tdFsi8qAQVDz0PAotz56CNFJib3evY8H",
            "AccessKeySecret": "wHsV0V1Fk7MJBQ8tcy6XTd4VhLMxgtEr9vZhDjU9yxrtDwyBTFE8QI0WQY3c7Npp"
        }
    }
    url = "https://openapi.gzbbr.com/login/index"
    data = config.get(company, config['fsbbr'])
    
    for attempt in range(3):
        try:
            response = requests.post(url, data=data, timeout=(10, 30))
            response.raise_for_status()
            result = response.json()
            return result['data']['token']
        except requests.exceptions.ConnectTimeout:
            if attempt == 2:
                raise
            time.sleep(5)
        except Exception as e:
            if attempt == 2:
                raise Exception(f"登录失败: {e}")
            time.sleep(5)


def getAllCassWarehouse(token):
    """
    获取所有仓库映射
    """
    url = "https://openapi.gzbbr.com/Product.Quote/getAllCassWarehouse"
    headers = {'token': token}
    
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=(10, 30))
            response.raise_for_status()
            result = response.json()
            return pd.DataFrame(result['data'])
        except requests.exceptions.ConnectTimeout:
            if attempt == 2:
                raise
            time.sleep(5)


def getAllSupplierChannel(token):
    """
    获取所有供应商渠道映射
    """
    url = "https://openapi.gzbbr.com/Product.Quote/getAllSupplierChannel"
    headers = {'token': token}
    
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=(10, 30))
            response.raise_for_status()
            result = response.json()
            data = pd.DataFrame(result['data'])
            if 'byname' in data.columns:
                del data['byname']
            return data
        except requests.exceptions.ConnectTimeout:
            if attempt == 2:
                raise
            time.sleep(5)


def load_crm_aliases_mapping():
    """
    加载CRM品牌别名映射
    """
    try:
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        excel_path = os.path.join(project_root, "static", "excel", "crm可用别名.xlsx")
        
        if not os.path.exists(excel_path):
            print(f"警告: 未找到 {excel_path}")
            return {}
        
        df = pd.read_excel(excel_path)
        brand_mapping = {}
        
        for _, row in df.iterrows():
            pp_name = row.get('pp_name', '')
            pp_names_str = str(row.get('pp_names', '')) if pd.notna(row.get('pp_names')) else ""
            
            possible_names = [name.strip() for name in pp_names_str.split(',')]
            for name in possible_names:
                if name and name != "-":
                    brand_mapping[name] = pp_name
        
        return brand_mapping
    except Exception as e:
        print(f"加载品牌映射失败: {e}")
        return {}


def prepare_data(df):
    """
    准备上传数据，过滤无效数据
    """
    valid_items = []
    skipped_items = []
    
    for idx, row in df.iterrows():
        item = {
            'index': idx,
            'oe': str(row.get('oe', '')).strip(),
            'brand': str(row.get('brand', '')).strip(),
            'supplier': str(row.get('supplier', '')).strip(),
            'warehouse': str(row.get('warehouse', '')).strip(),
            'price': float(row.get('price', 0)) if pd.notna(row.get('price')) else 0,
            'stock_quantity': int(row.get('stock_quantity', 0)) if pd.notna(row.get('stock_quantity')) else 0,
            'expire_time': row.get('expire_time', ''),
            'remark': str(row.get('remark', '')).strip(),
        }
        
        # 检查是否跳过
        skip_reasons = []
        if not item['supplier']:
            skip_reasons.append('supplier为空')
        if not item['warehouse']:
            skip_reasons.append('warehouse为空')
        
        if skip_reasons:
            item['skip_reason'] = '、'.join(skip_reasons)
            skipped_items.append(item)
        else:
            valid_items.append(item)
    
    return valid_items, skipped_items


def upload_single_item(item, token, warehouse_df, supplier_df, brand_mapping):
    """
    单条数据上传到B2B
    """
    oe = item['oe']
    brand = item['brand']
    
    # 品牌映射
    mapped_brand = brand_mapping.get(brand, brand)
    
    # 查找仓库ID
    warehouse_match = warehouse_df[warehouse_df['warehouse_name'] == item['warehouse']]
    if warehouse_match.empty:
        return {
            'oe': oe,
            'status': 'error',
            'msg': f'仓库未找到: {item["warehouse"]}',
            'operation': None,
            'mapped_brand': mapped_brand if mapped_brand != brand else None
        }
    
    # 查找供应商ID
    supplier_match = supplier_df[supplier_df['name'] == item['supplier']]
    if supplier_match.empty:
        return {
            'oe': oe,
            'status': 'error',
            'msg': f'供应商未找到: {item["supplier"]}',
            'operation': None,
            'mapped_brand': mapped_brand if mapped_brand != brand else None
        }
    
    # 构建上传数据
    upload_record = {
        "number": oe,
        "brand_name": mapped_brand,
        "price": item['price'],
        "cass_warehouse_id": int(warehouse_match.iloc[0]['cass_warehouse_id']),
        "supplier_channel_id": int(supplier_match.iloc[0]['supplier_channel_id']),
        "stock": item['stock_quantity'],
        "lose_date": item['expire_time'] if item['expire_time'] else (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d 23:00:00'),
        "remark": item['remark']
    }
    
    # 调用B2B上传API
    url = "https://openapi.gzbbr.com/Product.Quote/batchSave"
    headers = {
        'token': token,
        'Content-Type': 'application/json'
    }
    payload = json.dumps({"params": [upload_record]})
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=(15, 180))
        result = response.json()
        
        if 'data' in result and 'succes_data' in result['data']:
            succes_data = result['data'].get('succes_data', []) or []
            error_data = result['data'].get('error_data', []) or []
            
            if error_data and len(error_data) > 0:
                error_msg = error_data[0].get('error_msg', '未知错误')
                return {
                    'oe': oe,
                    'status': 'error',
                    'msg': error_msg,
                    'operation': None,
                    'mapped_brand': mapped_brand if mapped_brand != brand else None
                }
            elif succes_data and len(succes_data) > 0:
                operation = succes_data[0].get('operation_name', 'unknown')
                return {
                    'oe': oe,
                    'status': 'success',
                    'msg': '上传成功',
                    'operation': operation,
                    'mapped_brand': mapped_brand if mapped_brand != brand else None
                }
        
        return {
            'oe': oe,
            'status': 'error',
            'msg': '响应格式异常',
            'operation': None,
            'mapped_brand': mapped_brand if mapped_brand != brand else None
        }
        
    except Exception as e:
        return {
            'oe': oe,
            'status': 'error',
            'msg': f'请求异常: {str(e)}',
            'operation': None,
            'mapped_brand': mapped_brand if mapped_brand != brand else None
        }


def batch_upload(items, max_workers=5):
    """
    批量上传（线程池）
    """
    if not items:
        return {}
    
    # 登录获取token
    token = login('fsbbr')
    
    # 获取映射表
    warehouse_df = getAllCassWarehouse(token)
    supplier_df = getAllSupplierChannel(token)
    brand_mapping = load_crm_aliases_mapping()
    
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {
            executor.submit(upload_single_item, item, token, warehouse_df, supplier_df, brand_mapping): item
            for item in items
        }
        
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                result = future.result()
                results[result['oe']] = result
            except Exception as e:
                results[item['oe']] = {
                    'oe': item['oe'],
                    'status': 'error',
                    'msg': f'处理异常: {str(e)}',
                    'operation': None,
                    'mapped_brand': None
                }
    
    return results


def upload_inquiry_data(df, company='fsbbr'):
    """
    主入口：询价数据B2B上传
    
    Returns:
        dict: {
            'b2b_results': {...},  # B2B上传结果
            'valid_items': [...],   # 有效数据
            'skipped_items': [...]  # 跳过的数据
        }
    """
    print(f"\n{'='*50}")
    print("开始B2B询价数据上传")
    print(f"{'='*50}")
    
    # 1. 准备数据
    valid_items, skipped_items = prepare_data(df)
    print(f"数据准备完成：有效{len(valid_items)}条，跳过{len(skipped_items)}条")
    
    # 2. 批量上传
    b2b_results = {}
    if valid_items:
        print(f"开始批量上传...")
        b2b_results = batch_upload(valid_items)
        
        success_count = sum(1 for r in b2b_results.values() if r['status'] == 'success')
        error_count = sum(1 for r in b2b_results.values() if r['status'] == 'error')
        print(f"上传完成：成功{success_count}条，失败{error_count}条")
    
    print(f"{'='*50}\n")
    
    return {
        'b2b_results': b2b_results,
        'valid_items': valid_items,
        'skipped_items': skipped_items
    }
