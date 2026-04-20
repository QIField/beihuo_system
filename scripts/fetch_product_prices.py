#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取产品价格信息脚本
功能：
1. 读取Excel的"品牌号"列
2. 匹配数据库crmapp_compare_summary获取oe
3. 调用CRM API获取product_id
4. 调用CRM API获取价格信息
5. 将结果写入原Excel
"""

import os
import sys
import time
import pandas as pd
import pymysql
import requests
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
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


def get_product_id_by_numberlist(session, numberlist):
    """
    调用API-1: POST /api/Product.Product/list
    根据oe号获取产品列表，返回包含product_id的数据
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


def find_product_id_in_response(api_response, brand_code):
    """
    在API-1响应中根据brand_code查找product_id
    """
    if not api_response or 'data' not in api_response:
        return None
    
    products_data = api_response.get('data', [])
    
    for item in products_data:
        child_list = item.get('child', [])
        for child in child_list:
            # 匹配brand_code
            if child.get('brand_code') == brand_code or child.get('number') == brand_code:
                return child.get('product_id')
            # 也尝试匹配original_number
            if child.get('original_number') == brand_code:
                return child.get('product_id')
    
    return None


def get_product_detail(session, product_id):
    """
    调用API-2: GET /api/Product.Product/view
    根据product_id获取产品详情
    """
    url = f"https://crm.gzbbr.com/api/Product.Product/view?product_id={product_id}"
    headers = {
        'accept': 'application/json, text/plain, */*',
        'referer': 'https://crm.gzbbr.com/',
    }
    
    # 从session获取authorization
    auth_token = session.headers.get('authorization')
    if auth_token:
        headers['authorization'] = auth_token
    
    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 200 and data.get('data'):
            return data['data']
        return None
    except Exception as e:
        print(f"  API-2调用失败: {e}")
        return None


def extract_price_info(product_detail):
    """
    从产品详情中提取价格信息
    """
    if not product_detail:
        return {
            'cass_desc': '',
            'store_cass_price': '',
            'store_peer_price': '',
            'qpl_price': ''
        }
    
    return {
        'cass_desc': product_detail.get('cass_desc', ''),
        'store_cass_price': product_detail.get('store_cass_price', ''),
        'store_peer_price': product_detail.get('store_peer_price', ''),
        'qpl_price': product_detail.get('qpl_price', '')
    }


def process_excel(excel_path, brand_code_column='品牌号'):
    """
    处理Excel文件，获取价格信息
    """
    print(f"正在读取Excel文件: {excel_path}")
    
    # 根据文件扩展名选择读取方式
    file_ext = Path(excel_path).suffix.lower()
    if file_ext == '.xls':
        df = pd.read_excel(excel_path, engine='xlrd')
    else:
        df = pd.read_excel(excel_path, engine='openpyxl')
    
    print(f"读取完成，共 {len(df)} 行数据")
    
    # 检查品牌号列是否存在
    if brand_code_column not in df.columns:
        print(f"错误：未找到列 '{brand_code_column}'")
        print(f"可用列名: {list(df.columns)}")
        return None
    
    # 添加新列
    df['开思描述'] = ''
    df['开思价'] = ''
    df['同行价'] = ''
    df['汽配龙价格'] = ''
    df['处理状态'] = ''
    
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
                brand_code = row[brand_code_column]
                print(f"\n处理第 {idx + 1}/{len(df)} 行，品牌号: {brand_code}")
                
                # 检查品牌号是否为空
                if pd.isna(brand_code) or not str(brand_code).strip():
                    df.at[idx, '处理状态'] = '品牌号为空'
                    print("  跳过：品牌号为空")
                    continue
                
                brand_code = str(brand_code).strip()
                
                # 1. 从数据库获取oe
                db_result = get_oe_by_brand_code(brand_code, cursor)
                if not db_result or not db_result.get('oe'):
                    df.at[idx, '处理状态'] = '数据库未找到OE'
                    print(f"  跳过：数据库未找到品牌号 {brand_code} 的OE")
                    continue
                
                oe = db_result['oe']
                print(f"  数据库匹配成功: OE={oe}")
                
                # 2. 调用API-1获取产品列表
                time.sleep(0.5)  # 避免请求过快
                api1_response = get_product_id_by_numberlist(session, oe)
                
                if not api1_response:
                    df.at[idx, '处理状态'] = 'API-1调用失败'
                    print("  跳过：API-1调用失败")
                    continue
                
                # 3. 在API-1响应中查找product_id
                product_id = find_product_id_in_response(api1_response, brand_code)
                
                if not product_id:
                    df.at[idx, '处理状态'] = 'API-1响应中未找到匹配'
                    print(f"  跳过：API-1响应中未找到品牌号 {brand_code}")
                    continue
                
                print(f"  API-1匹配成功: product_id={product_id}")
                
                # 4. 调用API-2获取产品详情
                time.sleep(0.5)  # 避免请求过快
                product_detail = get_product_detail(session, product_id)
                
                if not product_detail:
                    df.at[idx, '处理状态'] = 'API-2调用失败'
                    print("  跳过：API-2调用失败")
                    continue
                
                # 5. 提取价格信息
                price_info = extract_price_info(product_detail)
                
                # 6. 写入DataFrame
                df.at[idx, '开思描述'] = price_info['cass_desc']
                df.at[idx, '开思价'] = price_info['store_cass_price']
                df.at[idx, '同行价'] = price_info['store_peer_price']
                df.at[idx, '汽配龙价格'] = price_info['qpl_price']
                df.at[idx, '处理状态'] = '成功'
                
                print(f"  成功获取价格信息:")
                print(f"    开思描述: {price_info['cass_desc'][:30] if price_info['cass_desc'] else '无'}...")
                print(f"    开思价: {price_info['store_cass_price']}")
                print(f"    同行价: {price_info['store_peer_price']}")
                print(f"    汽配龙价格: {price_info['qpl_price']}")
                
    finally:
        conn.close()
    
    # 保存结果
    output_path = str(Path(excel_path).parent / f"{Path(excel_path).stem}_含价格.xlsx")
    print(f"\n正在保存结果到: {output_path}")
    
    # 使用openpyxl引擎保存为xlsx格式
    df.to_excel(output_path, index=False, engine='openpyxl')
    print("保存完成！")
    
    # 统计信息
    success_count = len(df[df['处理状态'] == '成功'])
    print(f"\n处理统计:")
    print(f"  总行数: {len(df)}")
    print(f"  成功: {success_count}")
    print(f"  失败: {len(df) - success_count}")
    
    return df


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='获取产品价格信息工具')
    parser.add_argument('excel_path', nargs='?', default=r'G:\work\work_documents\销售_退货查询_明细_20260417100826.xls',
                        help='Excel文件路径')
    parser.add_argument('-c', '--column', default='品牌号', help='品牌号列名，默认为"品牌号"')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.excel_path):
        print(f"错误：文件不存在 {args.excel_path}")
        sys.exit(1)
    
    try:
        result_df = process_excel(
            excel_path=args.excel_path,
            brand_code_column=args.column
        )
        
        if result_df is not None:
            print("\n处理完成！")
            # 显示前5行结果
            print("\n前5行数据预览:")
            preview_columns = ['品牌号', '开思描述', '开思价', '同行价', '汽配龙价格', '处理状态']
            available_columns = [c for c in preview_columns if c in result_df.columns]
            print(result_df[available_columns].head())
            
    except Exception as e:
        print(f"处理出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
