"""
Excel导出模块
生成结果Excel文件
"""

import os
import pandas as pd
from datetime import datetime


def generate_result_excel(df, merged_results, output_dir='static/uploads/b2b_results'):
    """
    生成结果Excel文件
    
    Args:
        df: 原始DataFrame
        merged_results: 合并后的结果列表
        output_dir: 输出目录
    
    Returns:
        str: 生成的文件路径
    """
    # 确保目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'b2b_upload_result_{timestamp}.xlsx'
    filepath = os.path.join(output_dir, filename)
    
    # 创建结果DataFrame
    result_df = df.copy()
    
    # 添加处理结果列
    result_df['处理结果'] = ''
    
    # 填充结果
    for res in merged_results:
        idx = res['index']
        if idx < len(result_df):
            result_df.at[idx, '处理结果'] = res['处理结果']
    
    # 保存Excel
    result_df.to_excel(filepath, index=False, engine='openpyxl')
    
    print(f"结果文件已生成：{filepath}")
    return filepath


def get_recent_results(days=7, output_dir='static/uploads/b2b_results'):
    """
    获取最近的结果文件列表
    
    Returns:
        list: 文件信息列表
    """
    if not os.path.exists(output_dir):
        return []
    
    files = []
    now = datetime.now()
    
    for filename in os.listdir(output_dir):
        if filename.endswith('.xlsx'):
            filepath = os.path.join(output_dir, filename)
            file_stat = os.stat(filepath)
            file_time = datetime.fromtimestamp(file_stat.st_ctime)
            
            # 只返回指定天数内的
            if (now - file_time).days <= days:
                files.append({
                    'filename': filename,
                    'created_at': file_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'size': file_stat.st_size,
                    'filepath': filepath
                })
    
    # 按时间倒序
    files.sort(key=lambda x: x['created_at'], reverse=True)
    
    return files
