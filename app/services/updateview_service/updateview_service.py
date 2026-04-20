#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UpdateView Service - 批量更新CRM产品视图信息
业务逻辑层，支持异步处理和进度回调
"""

import os
import sys
import time
import pandas as pd
import pymysql
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量，跳过数据库选择提示
os.environ['DB_HOST'] = '113.46.196.69'
os.environ['DB_PORT'] = '3306'
os.environ['DB_USER'] = 'BBR_test'
os.environ['DB_PASSWORD'] = 'SkYwiC5DDhZA8XtH'
os.environ['DB_NAME'] = 'bbr_test'

from app.utils.database_connection import get_db_connection
from config.cookie_config import create_crm_session


def get_oe_by_brand_code(brand_code, cursor):
    """从数据库根据brand_code获取oe"""
    sql = """
        SELECT oe, brand, product_name 
        FROM crmapp_compare_summary 
        WHERE brand_code = %s 
        LIMIT 1
    """
    cursor.execute(sql, (brand_code,))
    result = cursor.fetchone()
    if result:
        return {
            'oe': result['oe'],
            'brand': result['brand'],
            'product_name': result['product_name']
        }
    return None


def get_product_list_by_numberlist(session, numberlist):
    """
    调用API-1: POST /api/Product.Product/list
    根据oe号或配件编码获取产品列表
    """
    url = "https://crm.gzbbr.com/api/Product.Product/list"
    headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8',
        'origin': 'https://crm.gzbbr.com',
        'referer': 'https://crm.gzbbr.com/',
    }
    
    # 从session获取authorization
    auth_token = session.headers.get('authorization')
    if auth_token:
        headers['authorization'] = auth_token
    
    payload = {
        "numberlist": numberlist,
        "page": 1,
        "limit": 32
    }
    
    try:
        import requests
        response = session.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 200 and data.get('data'):
            return data['data']
        return None
    except Exception as e:
        print(f"  API-1调用失败: {e}")
        return None


def find_product_id_by_brand_code(api_response, brand_code):
    """
    方式一：在API-1响应中根据brand_code查找product_id
    """
    if not api_response or 'data' not in api_response:
        return None
    
    products_data = api_response.get('data', [])
    
    for item in products_data:
        child_list = item.get('child', [])
        for child in child_list:
            # 匹配brand_code
            if child.get('brand_code') == brand_code:
                return child.get('product_id')
            # 也尝试匹配number
            if child.get('number') == brand_code:
                return child.get('product_id')
            # 尝试匹配original_number
            if child.get('original_number') == brand_code:
                return child.get('product_id')
    
    return None


def find_product_id_by_number_and_brand(api_response, number, brand_name):
    """
    方式二：在API-1响应中根据number和brand_name查找product_id
    """
    if not api_response or 'data' not in api_response:
        return None
    
    products_data = api_response.get('data', [])
    
    for item in products_data:
        child_list = item.get('child', [])
        for child in child_list:
            # 同时匹配number和brand_name
            child_number = child.get('number', '')
            child_brand = child.get('brand_name', '')
            
            if child_number == number and child_brand == brand_name:
                return child.get('product_id')
            
            # 也尝试匹配original_number
            if child.get('original_number') == number and child_brand == brand_name:
                return child.get('product_id')
    
    return None


def update_product_view(session, product_id, cass_desc, store_cass_price, store_peer_price, qpl_price):
    """
    调用API: POST /api/Product.Product/updateView
    更新产品视图信息
    只包含有值的字段，空字段不作为参数传递
    """
    url = "https://crm.gzbbr.com/api/Product.Product/updateView"
    headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8',
        'origin': 'https://crm.gzbbr.com',
        'referer': 'https://crm.gzbbr.com/',
    }
    
    # 从session获取authorization
    auth_token = session.headers.get('authorization')
    if auth_token:
        headers['authorization'] = auth_token
    
    # 构建payload，只包含有值的字段
    payload = {
        "product_id": str(product_id)
    }
    
    # 开思描述：有值才添加
    if cass_desc and str(cass_desc).strip():
        payload["cass_desc"] = str(cass_desc).strip()
    
    import math
    
    # 辅助函数：检查值是否有效（不是空、不是nan、不是null字符串）
    def is_valid_value(val):
        if not val:
            return False
        val_str = str(val).strip().lower()
        if val_str in ['', 'nan', 'null', 'none']:
            return False
        return True
    
    # 开思价：有值才添加，转为float
    if is_valid_value(store_cass_price):
        try:
            val = float(store_cass_price)
            if not math.isnan(val):  # 过滤nan值
                payload["store_cass_price"] = val
        except (ValueError, TypeError):
            pass  # 转换失败则不添加
    
    # 同行价：有值才添加，转为float
    if is_valid_value(store_peer_price):
        try:
            val = float(store_peer_price)
            if not math.isnan(val):  # 过滤nan值
                payload["store_peer_price"] = val
        except (ValueError, TypeError):
            pass  # 转换失败则不添加
    
    # 汽配龙价格：有值才添加，转为float
    if is_valid_value(qpl_price):
        try:
            val = float(qpl_price)
            if not math.isnan(val):  # 过滤nan值
                payload["qpl_price"] = val
        except (ValueError, TypeError):
            pass  # 转换失败则不添加
    
    # 打印调试信息
    print(f"    [DEBUG] 发送的payload: {payload}")
    
    try:
        import requests
        response = session.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 200:
            return True, data.get('msg', '更新成功')
        else:
            return False, data.get('msg', '更新失败')
    except Exception as e:
        print(f"    [DEBUG] API调用异常: {e}")
        print(f"    [DEBUG] payload内容: {payload}")
        return False, f"API调用失败: {e}"


def process_update_crm_product_async(file_path, progress_callback=None, **kwargs):
    """
    异步处理更新CRM产品视图信息
    
    参数:
        file_path: Excel文件路径
        progress_callback: 进度回调函数，接收(current, total, message)参数
        **kwargs: 额外参数（兼容异步任务框架）
    
    返回:
        result_file_path: 结果文件路径
    """
    print(f"[UpdateView Service] 开始处理文件: {file_path}")
    
    # 读取Excel文件
    file_ext = Path(file_path).suffix.lower()
    if file_ext == '.xls':
        df = pd.read_excel(file_path, engine='xlrd')
    else:
        df = pd.read_excel(file_path, engine='openpyxl')
    
    total_rows = len(df)
    print(f"[UpdateView Service] 读取完成，共 {total_rows} 行数据")
    
    # 检查必要列是否存在
    # 方式一：品牌号（不需要配件编码，不需要品牌）
    # 方式二：配件编码 + 品牌（不需要品牌号）
    # 两种方式至少满足一种
    has_brand_code_col = '品牌号' in df.columns
    has_peijian_code_col = '配件编码' in df.columns
    has_brand_col = '品牌' in df.columns
    
    if not has_brand_code_col and not (has_peijian_code_col and has_brand_col):
        raise ValueError(f"Excel文件需要包含'品牌号'列，或同时包含'配件编码'和'品牌'列")
    
    # 添加状态列
    if '更新状态' not in df.columns:
        df['更新状态'] = ''
    
    # 创建CRM会话
    print("[UpdateView Service] 正在获取CRM认证信息...")
    session = create_crm_session()
    print("[UpdateView Service] CRM认证完成")
    
    # 数据库连接
    conn = get_db_connection()
    
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 逐条处理
            for idx, row in df.iterrows():
                peijian_code = row.get('配件编码', '')
                brand = row.get('品牌', '')
                brand_code = row.get('品牌号', '')
                
                # 上报进度
                if progress_callback:
                    progress_callback(
                        current=idx + 1,
                        total=total_rows,
                        message=f"正在处理第 {idx + 1}/{total_rows} 行: {peijian_code}"
                    )
                
                print(f"\n[UpdateView Service] 处理第 {idx + 1}/{total_rows} 行")
                print(f"  配件编码: {peijian_code}, 品牌: {brand}, 品牌号: {brand_code}")
                
                # 检查是否有品牌号（方式一）
                has_brand_code = not pd.isna(brand_code) and str(brand_code).strip()
                # 检查是否有配件编码+品牌（方式二）
                has_peijian_code = not pd.isna(peijian_code) and str(peijian_code).strip()
                has_brand = not pd.isna(brand) and str(brand).strip()
                
                # 两种方式都不满足，跳过
                if not has_brand_code and not (has_peijian_code and has_brand):
                    df.at[idx, '更新状态'] = '品牌号为空，且配件编码或品牌为空'
                    print("  跳过：品牌号为空，且配件编码或品牌为空")
                    continue
                
                if has_brand_code:
                    brand_code = str(brand_code).strip()
                if has_peijian_code:
                    peijian_code = str(peijian_code).strip()
                if has_brand:
                    brand = str(brand).strip()
                
                product_id = None
                
                # 方式一：优先使用品牌号获取product_id
                if not pd.isna(brand_code) and str(brand_code).strip():
                    brand_code = str(brand_code).strip()
                    print(f"  方式一：使用品牌号 {brand_code} 获取product_id")
                    
                    # 从数据库获取oe
                    db_result = get_oe_by_brand_code(brand_code, cursor)
                    if db_result and db_result.get('oe'):
                        oe = db_result['oe']
                        print(f"    数据库匹配成功: OE={oe}")
                        
                        # 调用API-1
                        time.sleep(0.5)
                        api1_response = get_product_list_by_numberlist(session, oe)
                        
                        if api1_response:
                            # 用品牌号匹配product_id
                            product_id = find_product_id_by_brand_code(api1_response, brand_code)
                            if product_id:
                                print(f"    API匹配成功: product_id={product_id}")
                            else:
                                print(f"    API响应中未找到品牌号 {brand_code}")
                        else:
                            print(f"    API-1调用失败")
                    else:
                        print(f"    数据库未找到品牌号 {brand_code} 的OE")
                
                # 方式二：使用配件编码+品牌获取product_id（只有在有配件编码时才执行）
                if not product_id and has_peijian_code:
                    print(f"  方式二：使用配件编码 {peijian_code} + 品牌 {brand} 获取product_id")
                    
                    # 调用API-1
                    time.sleep(0.5)
                    api1_response = get_product_list_by_numberlist(session, peijian_code)
                    
                    if api1_response:
                        # 用配件编码+品牌匹配product_id
                        product_id = find_product_id_by_number_and_brand(api1_response, peijian_code, brand)
                        if product_id:
                            print(f"    API匹配成功: product_id={product_id}")
                        else:
                            print(f"    API响应中未找到配件编码 {peijian_code} 和品牌 {brand} 的组合")
                    else:
                        print(f"    API-1调用失败")
                
                # 如果没有找到product_id，跳过
                if not product_id:
                    df.at[idx, '更新状态'] = '未找到product_id'
                    print(f"  跳过：无法获取product_id")
                    continue
                
                # 获取要更新的字段值
                cass_desc = row.get('开思描述', '')
                store_cass_price = row.get('开思价', '')
                store_peer_price = row.get('同行价', '')
                qpl_price = row.get('汽配龙价格', '')
                
                # 处理空值
                cass_desc = str(cass_desc) if not pd.isna(cass_desc) else ''
                
                print(f"  准备更新:")
                print(f"    开思描述: {cass_desc[:30] if cass_desc else '(空)'}...")
                print(f"    开思价: {store_cass_price if not pd.isna(store_cass_price) else 'null'}")
                print(f"    同行价: {store_peer_price if not pd.isna(store_peer_price) else 'null'}")
                print(f"    汽配龙价格: {qpl_price if not pd.isna(qpl_price) else 'null'}")
                
                # 调用更新API
                time.sleep(0.5)
                success, msg = update_product_view(
                    session, 
                    product_id, 
                    cass_desc, 
                    store_cass_price, 
                    store_peer_price, 
                    qpl_price
                )
                
                if success:
                    df.at[idx, '更新状态'] = f'更新成功: {msg}'
                    print(f"  ✓ 更新成功: {msg}")
                else:
                    df.at[idx, '更新状态'] = f'更新失败: {msg}'
                    print(f"  ✗ 更新失败: {msg}")
                
    finally:
        conn.close()
    
    # 保存结果文件
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file_name = f"updateview_result_{timestamp}.xlsx"
    result_file_path = os.path.join(os.path.dirname(file_path), result_file_name)
    
    print(f"\n[UpdateView Service] 正在保存结果到: {result_file_path}")
    df.to_excel(result_file_path, index=False, engine='openpyxl')
    print("[UpdateView Service] 保存完成！")
    
    # 统计信息
    success_count = len(df[df['更新状态'].str.contains('更新成功', na=False)])
    print(f"\n[UpdateView Service] 处理统计:")
    print(f"  总行数: {len(df)}")
    print(f"  更新成功: {success_count}")
    print(f"  更新失败/跳过: {len(df) - success_count}")
    
    return result_file_path
