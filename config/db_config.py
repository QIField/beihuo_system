import os
from pathlib import Path

def is_local_environment():
    """判断是否为本地开发环境"""
    current_file_path = Path(__file__).resolve()
    current_path_str = str(current_file_path).lower().replace('\\', '/')
    
    return (
        current_path_str.startswith('g:/work/') or
        current_path_str.startswith('e:/work download/') or
        os.environ.get('FLASK_ENV') == 'development' or
        'localhost' in os.environ.get('HOSTNAME', '').lower()
    )

def get_mysql_config():
    """根据环境返回数据库配置"""
    if is_local_environment():
        return {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': int(os.environ.get('DB_PORT', 3306)),
            'user': os.environ.get('DB_USER', 'root'),
            'password': os.environ.get('DB_PASSWORD', '123456'),
            'database': os.environ.get('DB_NAME', 'test'),
            'charset': 'utf8mb4',
            'autocommit': True,
            'use_unicode': True
        }
    else:
        return {
            'host': '113.45.176.129',
            'port': 3306,
            'user': 'fsbbr_data',
            'password': 'wRCA8AGn3a568f4X',
            'database': 'fsbbr_data',
            'charset': 'utf8mb4',
            'autocommit': True,
            'use_unicode': True
        }