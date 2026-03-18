"""
文件清理模块
自动清理7天前的结果文件
"""

import os
from datetime import datetime, timedelta


def cleanup_old_results(days=7, output_dir='static/uploads/b2b_results'):
    """
    清理指定天数前的结果文件
    
    Args:
        days: 保留天数，默认7天
        output_dir: 输出目录
    
    Returns:
        int: 清理的文件数量
    """
    if not os.path.exists(output_dir):
        return 0
    
    now = datetime.now()
    cleaned_count = 0
    
    for filename in os.listdir(output_dir):
        filepath = os.path.join(output_dir, filename)
        if os.path.isfile(filepath) and filename.endswith('.xlsx'):
            file_time = datetime.fromtimestamp(os.path.getctime(filepath))
            
            if (now - file_time).days > days:
                try:
                    os.remove(filepath)
                    cleaned_count += 1
                    print(f"清理旧文件：{filename}")
                except Exception as e:
                    print(f"清理文件失败 {filename}: {e}")
    
    if cleaned_count > 0:
        print(f"共清理{cleaned_count}个旧文件")
    
    return cleaned_count
