"""
B2B上传核心模块
复用virtual_inventory的B2B上传逻辑
"""

import pandas as pd
import json
import requests
import time
from datetime import datetime, timedelta


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
        
        # 保存原价格（如果存在），用于采购记录表
        if 'original_price' in df.columns:
            item['original_price'] = float(row.get('original_price', item['price'])) if pd.notna(row.get('original_price')) else item['price']
        else:
            item['original_price'] = item['price']
        
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
    返回包含update_msg字段的结果
    """
    oe = item['oe']
    brand = item['brand']
    
    # 品牌映射
    mapped_brand = brand_mapping.get(brand, brand)
    
    # 查找仓库ID
    warehouse_match = warehouse_df[warehouse_df['warehouse_name'] == item['warehouse']]
    if warehouse_match.empty:
        error_msg = f'仓库未找到: {item["warehouse"]}'
        return {
            'oe': oe,
            'status': 'error',
            'msg': error_msg,
            'operation': None,
            'mapped_brand': mapped_brand if mapped_brand != brand else None,
            'update_msg': error_msg
        }
    
    # 查找供应商ID
    supplier_match = supplier_df[supplier_df['name'] == item['supplier']]
    if supplier_match.empty:
        error_msg = f'供应商未找到: {item["supplier"]}'
        return {
            'oe': oe,
            'status': 'error',
            'msg': error_msg,
            'operation': None,
            'mapped_brand': mapped_brand if mapped_brand != brand else None,
            'update_msg': error_msg
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
                    'mapped_brand': mapped_brand if mapped_brand != brand else None,
                    'update_msg': error_msg
                }
            elif succes_data and len(succes_data) > 0:
                operation = succes_data[0].get('operation_name', 'unknown')
                success_msg = succes_data[0].get('message', f'上传{operation}成功')
                return {
                    'oe': oe,
                    'status': 'success',
                    'msg': success_msg,
                    'operation': operation,
                    'mapped_brand': mapped_brand if mapped_brand != brand else None,
                    'update_msg': success_msg
                }
        
        # 响应格式不符合预期
        error_msg = f'响应格式异常: {json.dumps(result, ensure_ascii=False)[:200]}'
        return {
            'oe': oe,
            'status': 'error',
            'msg': error_msg,
            'operation': None,
            'mapped_brand': mapped_brand if mapped_brand != brand else None,
            'update_msg': error_msg
        }
        
    except Exception as e:
        error_msg = f'请求异常: {str(e)}'
        return {
            'oe': oe,
            'status': 'error',
            'msg': error_msg,
            'operation': None,
            'mapped_brand': mapped_brand if mapped_brand != brand else None,
            'update_msg': error_msg
        }


def batch_upload(items):
    """
    批量上传（循环处理）
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
    
    # 循环处理每个项目
    for item in items:
        try:
            result = upload_single_item(item, token, warehouse_df, supplier_df, brand_mapping)
            results[result['oe']] = result
        except Exception as e:
            results[item['oe']] = {
                'oe': item['oe'],
                'status': 'error',
                'msg': f'处理异常: {str(e)}',
                'operation': None,
                'mapped_brand': None,
                'update_msg': f'处理异常: {str(e)}'
            }
    
    return results


def batch_upload_with_callback(items, callback=None):
    """
    批量上传并支持回调函数
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
    
    # 循环处理每个项目
    for item in items:
        try:
            result = upload_single_item(item, token, warehouse_df, supplier_df, brand_mapping)
            results[result['oe']] = result
            
            # 调用回调函数
            if callback:
                callback(result)
        except Exception as e:
            results[item['oe']] = {
                'oe': item['oe'],
                'status': 'error',
                'msg': f'处理异常: {str(e)}',
                'operation': None,
                'mapped_brand': None,
                'update_msg': f'处理异常: {str(e)}'
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


def validate_b2b_upload(items, company='fsbbr'):
    """
    验证B2B上传可行性（不实际上传，只验证仓库、供应商等映射是否存在）
    用于导入前的预验证，确保数据能成功上传

    Args:
        items: 待验证的数据列表
        company: 公司代码
        
    Returns:
        dict: {oe: {'status': 'success'/'error', 'msg': '...'}, ...}
    """
    if not items:
        return {}
    
    print(f"[B2B验证] 开始验证 {len(items)} 条数据...")
    
    try:
        # 登录获取token和映射表
        token = login(company)
        warehouse_df = getAllCassWarehouse(token)
        supplier_df = getAllSupplierChannel(token)
        brand_mapping = load_crm_aliases_mapping()
        
        results = {}
        
        for item in items:
            oe = item['oe']
            brand = item['brand']
            supplier = item['supplier']
            warehouse = item['warehouse']
            
            # 品牌映射
            mapped_brand = brand_mapping.get(brand, brand)
            
            # 验证仓库是否存在
            warehouse_match = warehouse_df[warehouse_df['warehouse_name'] == warehouse]
            if warehouse_match.empty:
                results[oe] = {
                    'status': 'error',
                    'msg': f'仓库未找到: {warehouse}'
                }
                continue
            
            # 验证供应商是否存在
            supplier_match = supplier_df[supplier_df['name'] == supplier]
            if supplier_match.empty:
                results[oe] = {
                    'status': 'error',
                    'msg': f'供应商未找到: {supplier}'
                }
                continue
            
            # 验证通过
            results[oe] = {
                'status': 'success',
                'msg': '验证通过',
                'mapped_brand': mapped_brand if mapped_brand != brand else None,
                'warehouse_id': int(warehouse_match.iloc[0]['cass_warehouse_id']),
                'supplier_id': int(supplier_match.iloc[0]['supplier_channel_id'])
            }
        
        success_count = sum(1 for r in results.values() if r['status'] == 'success')
        print(f"[B2B验证] 完成: 通过={success_count}, 失败={len(results) - success_count}")
        return results
        
    except Exception as e:
        print(f"[B2B验证] 验证过程异常: {e}")
        # 如果验证过程出错，返回所有项目都失败
        return {item['oe']: {'status': 'error', 'msg': f'验证异常: {str(e)}'} for item in items}
