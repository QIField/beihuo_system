"""
Excel导出模块
获取 B2B 上传结果文件列表
"""

import os
from datetime import datetime


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
