#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量更新产品视图信息脚本
功能：
1. 读取Excel的配件编码、品牌、品牌号、开思描述、开思价、同行价、汽配龙价格
2. 优先使用品牌号获取product_id，否则使用配件编码+品牌
3. 调用CRM API更新产品视图信息
"""

import os
import sys
import time
import math
import pandas as pd
import pymysql
import requests
from pathlib import Path

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
from app.utils.crm_updateview_logger import execute_update_view_with_log, fetch_view_then_update


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
    更新产品视图信息（先查view再回传完整字段）
    """
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

    # 只收集有值的字段
    new_values = {}

    if cass_desc and str(cass_desc).strip():
        new_values["cass_desc"] = str(cass_desc).strip()

    if store_cass_price and str(store_cass_price).strip():
        try:
            val = float(store_cass_price)
            if not math.isnan(val):
                new_values["store_cass_price"] = val
        except (ValueError, TypeError):
            pass

    if store_peer_price and str(store_peer_price).strip():
        try:
            val = float(store_peer_price)
            if not math.isnan(val):
                new_values["store_peer_price"] = val
        except (ValueError, TypeError):
            pass

    if qpl_price and str(qpl_price).strip():
        try:
            val = float(qpl_price)
            if not math.isnan(val):
                new_values["qpl_price"] = val
        except (ValueError, TypeError):
            pass

    return fetch_view_then_update(
        session=session,
        product_id=str(product_id),
        new_values=new_values,
        source="batch_update_view",
        store_code="fsbbr",
        headers=headers,
        timeout=30,
    )


def process_excel(excel_path):
    """
    处理Excel文件，批量更新产品视图
    """
    print(f"正在读取Excel文件: {excel_path}")
    
    # 根据文件扩展名选择读取方式
    # 配件编码、品牌号可能包含前导零，强制按字符串读取
    file_ext = Path(excel_path).suffix.lower()
    read_dtype = {'配件编码': str, '品牌号': str}
    if file_ext == '.xls':
        df = pd.read_excel(excel_path, engine='xlrd', dtype=read_dtype)
    else:
        df = pd.read_excel(excel_path, engine='openpyxl', dtype=read_dtype)
    
    print(f"读取完成，共 {len(df)} 行数据")
    
    # 检查必要列是否存在
    required_columns = ['配件编码', '品牌']
    for col in required_columns:
        if col not in df.columns:
            print(f"错误：未找到必要列 '{col}'")
            print(f"可用列名: {list(df.columns)}")
            return None
    
    # 添加状态列
    if '更新状态' not in df.columns:
        df['更新状态'] = ''
    
    # 创建CRM会话
    print("正在获取CRM认证信息...")
    session = create_crm_session()
    print("CRM认证完成")
    
    # 数据库连接
    conn = get_db_connection()
    
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 逐条处理
            for idx, row in df.iterrows():
                peijian_code = row.get('配件编码', '')
                brand = row.get('品牌', '')
                brand_code = row.get('品牌号', '')
                
                print(f"\n处理第 {idx + 1}/{len(df)} 行")
                print(f"  配件编码: {peijian_code}, 品牌: {brand}, 品牌号: {brand_code}")
                
                # 检查配件编码和品牌是否为空
                if pd.isna(peijian_code) or not str(peijian_code).strip():
                    df.at[idx, '更新状态'] = '配件编码为空'
                    print("  跳过：配件编码为空")
                    continue
                
                if pd.isna(brand) or not str(brand).strip():
                    df.at[idx, '更新状态'] = '品牌为空'
                    print("  跳过：品牌为空")
                    continue
                
                peijian_code = str(peijian_code).strip()
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
                
                # 方式二：使用配件编码+品牌获取product_id
                if not product_id:
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
                    print(f"  [成功] 更新成功: {msg}")
                else:
                    df.at[idx, '更新状态'] = f'更新失败: {msg}'
                    print(f"  [失败] 更新失败: {msg}")
                
    finally:
        conn.close()
    
    # 保存结果
    output_path = str(Path(excel_path).parent / f"{Path(excel_path).stem}_更新结果.xlsx")
    print(f"\n正在保存结果到: {output_path}")
    
    # 使用openpyxl引擎保存为xlsx格式
    df.to_excel(output_path, index=False, engine='openpyxl')
    print("保存完成！")
    
    # 统计信息
    success_count = len(df[df['更新状态'].str.contains('更新成功', na=False)])
    print(f"\n处理统计:")
    print(f"  总行数: {len(df)}")
    print(f"  更新成功: {success_count}")
    print(f"  更新失败/跳过: {len(df) - success_count}")
    
    return df


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量更新产品视图信息工具')
    parser.add_argument('excel_path', help='Excel文件路径')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.excel_path):
        print(f"错误：文件不存在 {args.excel_path}")
        sys.exit(1)
    
    try:
        result_df = process_excel(excel_path=args.excel_path)
        
        if result_df is not None:
            print("\n处理完成！")
            # 显示前5行结果
            print("\n前5行数据预览:")
            preview_columns = ['配件编码', '品牌', '品牌号', '更新状态']
            available_columns = [c for c in preview_columns if c in result_df.columns]
            print(result_df[available_columns].head())
            
    except Exception as e:
        print(f"处理出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
