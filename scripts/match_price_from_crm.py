#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取Excel中的数据，从crmapp_compare_summary表匹配最高价和最低价
Excel C列(长数字)匹配数据库oe列，且brand字段为'马勒'
"""

import sys
import pandas as pd
import pymysql
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.db_config import _create_config


def get_price_data_from_db(oe_list):
    """
    从数据库查询最高价和最低价（brand='马勒'）
    
    Args:
        oe_list: oe编号列表
    
    Returns:
        dict: {oe: {'max_price': xx, 'min_price': xx}}
    """
    if not oe_list:
        return {}
    
    # 使用线上数据库配置
    config = _create_config("online")
    
    result = {}
    conn = None
    try:
        conn = pymysql.connect(**config)
        with conn.cursor() as cursor:
            # 构建IN查询，增加brand='马勒'条件
            placeholders = ', '.join(['%s'] * len(oe_list))
            query = f"""
                SELECT oe, max_price, min_price
                FROM crmapp_compare_summary
                WHERE oe IN ({placeholders}) AND brand = '马勒'
            """
            cursor.execute(query, tuple(oe_list))
            rows = cursor.fetchall()
            for row in rows:
                oe, max_price, min_price = row
                result[oe] = {
                    'max_price': max_price,
                    'min_price': min_price
                }
    except Exception as e:
        print(f"数据库查询错误: {e}")
        raise
    finally:
        if conn:
            conn.close()
    
    return result


def process_excel(input_path, output_path):
    """
    处理Excel文件，匹配价格数据
    
    Args:
        input_path: 输入Excel文件路径
        output_path: 输出Excel文件路径
    """
    print(f"读取文件: {input_path}")
    
    # 读取Excel
    df = pd.read_excel(input_path)
    
    print(f"Excel列名: {df.columns.tolist()}")
    
    # 获取C列数据（长数字列）
    col_c = df.columns[2]  # C列
    
    print(f"使用C列 '{col_c}' 匹配数据库oe列")
    print("筛选条件: brand = '马勒'")
    
    # 获取所有OE编号（去除空值）
    oe_list = df[col_c].dropna().astype(str).tolist()
    print(f"共 {len(oe_list)} 个OE编号")
    
    # 去重
    unique_oes = list(set(oe_list))
    print(f"去重后 {len(unique_oes)} 个")
    
    # 从数据库查询价格
    print("正在从数据库查询价格数据...")
    price_data = get_price_data_from_db(unique_oes)
    print(f"数据库匹配到 {len(price_data)} 条记录")
    
    # 新增最高价和最低价列
    df['最高价'] = df[col_c].astype(str).map(
        lambda x: price_data.get(x, {}).get('max_price')
    )
    df['最低价'] = df[col_c].astype(str).map(
        lambda x: price_data.get(x, {}).get('min_price')
    )
    
    # 统计匹配情况
    matched_count = df['最高价'].notna().sum()
    unmatched_count = len(df) - matched_count
    
    print(f"\n匹配结果:")
    print(f"  - 成功匹配: {matched_count} 条")
    print(f"  - 未匹配: {unmatched_count} 条")
    
    # 保存到新的Excel
    df.to_excel(output_path, index=False)
    print(f"\n结果已保存: {output_path}")
    
    return df


def main():
    # 输入文件路径
    input_file = r"G:\wechat\xwechat_files\kangweiyang001_eba2\msg\file\2026-04\马勒(1).xlsx"
    
    # 输出文件路径（在同一目录，添加_结果后缀）
    input_path = Path(input_file)
    output_file = input_path.parent / f"{input_path.stem}_结果.xlsx"
    
    try:
        process_excel(input_file, output_file)
        print("\n✅ 处理完成!")
    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        raise


if __name__ == "__main__":
    main()
