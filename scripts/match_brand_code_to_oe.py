#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
品牌号匹配OE号脚本
功能：读取Excel文件中的品牌号，匹配数据库crmapp_compare_summary表的brand_code，返回对应的oe号
"""

import os
import sys
import pandas as pd
import pymysql
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.database_connection import get_db_connection


def match_brand_code_to_oe(excel_path, brand_code_column='品牌号', output_path=None):
    """
    匹配品牌号到OE号

    参数:
        excel_path: Excel文件路径
        brand_code_column: 品牌号列名，默认为'品牌号'
        output_path: 输出文件路径，默认为原文件名_带OE.xlsx

    返回:
        匹配结果DataFrame
    """
    # 1. 读取Excel文件
    print(f"正在读取Excel文件: {excel_path}")
    df = pd.read_excel(excel_path)
    print(f"读取完成，共 {len(df)} 行数据")

    # 检查品牌号列是否存在
    if brand_code_column not in df.columns:
        print(f"错误：未找到列 '{brand_code_column}'")
        print(f"可用列名: {list(df.columns)}")
        return None

    # 2. 获取所有品牌号（去重）
    brand_codes = df[brand_code_column].dropna().unique().tolist()
    print(f"共 {len(brand_codes)} 个唯一品牌号需要匹配")

    # 3. 从数据库查询匹配数据
    print("正在查询数据库...")
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 使用IN查询批量获取匹配数据
            format_strings = ','.join(['%s'] * len(brand_codes))
            sql = f"""
                SELECT brand_code, oe, brand, product_name, vehicle_brand
                FROM crmapp_compare_summary
                WHERE brand_code IN ({format_strings})
            """
            cursor.execute(sql, brand_codes)
            results = cursor.fetchall()

            # 创建brand_code到oe的映射（一个brand_code可能对应多个oe）
            brand_to_oe_map = {}
            for row in results:
                bc = row['brand_code']
                if bc not in brand_to_oe_map:
                    brand_to_oe_map[bc] = []
                brand_to_oe_map[bc].append({
                    'oe': row['oe'],
                    'brand': row['brand'],
                    'product_name': row['product_name'],
                    'vehicle_brand': row['vehicle_brand']
                })

            print(f"数据库中找到 {len(brand_to_oe_map)} 个品牌号的匹配数据")

    finally:
        conn.close()

    # 4. 将匹配结果添加到DataFrame
    print("正在匹配数据...")

    # 创建新列
    df['匹配到的OE'] = ''
    df['匹配到的品牌'] = ''
    df['产品名称'] = ''
    df['车型品牌'] = ''
    df['匹配状态'] = ''

    matched_count = 0
    unmatched_count = 0

    for idx, row in df.iterrows():
        brand_code = row[brand_code_column]

        if pd.isna(brand_code) or not brand_code:
            df.at[idx, '匹配状态'] = '品牌号为空'
            unmatched_count += 1
            continue

        brand_code = str(brand_code).strip()

        if brand_code in brand_to_oe_map:
            matches = brand_to_oe_map[brand_code]
            # 如果有多个匹配，用逗号分隔
            df.at[idx, '匹配到的OE'] = ', '.join([m['oe'] for m in matches if m['oe']])
            df.at[idx, '匹配到的品牌'] = ', '.join(set([m['brand'] for m in matches if m['brand']]))
            df.at[idx, '产品名称'] = matches[0]['product_name'] if matches else ''
            df.at[idx, '车型品牌'] = matches[0]['vehicle_brand'] if matches else ''
            df.at[idx, '匹配状态'] = f'匹配成功({len(matches)}条)'
            matched_count += 1
        else:
            df.at[idx, '匹配状态'] = '未找到匹配'
            unmatched_count += 1

    print(f"匹配完成: 成功 {matched_count} 条, 未匹配 {unmatched_count} 条")

    # 5. 保存结果
    if output_path is None:
        file_name = Path(excel_path).stem
        output_path = Path(excel_path).parent / f"{file_name}_带OE.xlsx"

    df.to_excel(output_path, index=False)
    print(f"结果已保存到: {output_path}")

    return df


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='品牌号匹配OE号工具')
    parser.add_argument('excel_path', help='Excel文件路径')
    parser.add_argument('-c', '--column', default='品牌号', help='品牌号列名，默认为"品牌号"')
    parser.add_argument('-o', '--output', help='输出文件路径')

    args = parser.parse_args()

    if not os.path.exists(args.excel_path):
        print(f"错误：文件不存在 {args.excel_path}")
        sys.exit(1)

    try:
        result_df = match_brand_code_to_oe(
            excel_path=args.excel_path,
            brand_code_column=args.column,
            output_path=args.output
        )

        if result_df is not None:
            print("\n处理完成！")
            # 显示前几行结果
            print("\n前5行数据预览:")
            preview_columns = ['品牌号', '匹配到的OE', '匹配状态']
            available_columns = [c for c in preview_columns if c in result_df.columns]
            print(result_df[available_columns].head())

    except Exception as e:
        print(f"处理出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
