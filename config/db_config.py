import os
import threading
from pathlib import Path

# 缓存用户选择的数据库配置，避免重复询问
_selected_config = None
# 线程锁，确保多线程环境下只询问一次
_config_lock = threading.Lock()

def is_local_environment():
    """
    判断是否为本地开发环境
    通过检测文件路径或环境变量来判断
    """
    current_file_path = Path(__file__).resolve()
    current_path_str = str(current_file_path).lower().replace('\\', '/')
    
    return (
        current_path_str.startswith('g:/work/') or
        current_path_str.startswith('e:/work download/') or
        os.environ.get('FLASK_ENV') == 'development' or
        'localhost' in os.environ.get('HOSTNAME', '').lower()
    )


def _ask_database_choice():
    """
    本地开发环境下，询问用户选择数据库
    提供两个选项：本地数据库（快速开发）或线上数据库（真实延迟测试）
    """
    print("\n" + "=" * 60)
    print("🗄️  数据库连接选择")
    print("=" * 60)
    print("1. 本地数据库 (localhost) - 快速开发，无网络延迟")
    print("2. 线上数据库 (113.45.176.129) - 真实延迟测试，模拟生产环境")
    print("=" * 60)
    
    while True:
        choice = input("请选择数据库 [1/2，默认1]: ").strip() or "1"
        if choice in ["1", "2"]:
            break
        print("❌ 无效输入，请输入 1 或 2")
    
    if choice == "2":
        print("⚠️  已选择线上数据库，请注意：")
        print("   - 所有操作都有真实网络延迟")
        print("   - 请谨慎操作，避免影响线上数据")
        return "online"
    else:
        print("✅ 已选择本地数据库")
        return "local"


def _create_config(choice):
    """根据选择创建数据库配置"""
    if choice == "local":
        return {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': int(os.environ.get('DB_PORT', 3306)),
            'user': os.environ.get('DB_USER', 'root'),
            'password': os.environ.get('DB_PASSWORD', 'root'),
            'database': os.environ.get('DB_NAME', 'fsbbr_data_test'),
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


def get_mysql_config():
    """
    根据环境返回数据库配置
    - 线上环境：自动使用线上数据库
    - 本地环境：询问用户选择，并记住选择直到程序重启
    
    使用线程锁确保多线程环境下只询问一次
    """
    global _selected_config
    
    # 快速路径：如果已经选择过，直接返回
    if _selected_config is not None:
        return _selected_config
    
    # 获取锁，确保只有一个线程执行初始化
    with _config_lock:
        # 双重检查：获取锁后再次确认配置是否已被其他线程设置
        if _selected_config is not None:
            return _selected_config
        
        # 判断当前环境
        if is_local_environment():
            # 本地开发环境：询问用户选择
            choice = _ask_database_choice()
            _selected_config = _create_config(choice)
        else:
            # 线上服务器环境：自动使用线上数据库
            _selected_config = _create_config("online")
        
        # 打印当前连接的数据库信息（隐藏密码）
        config_display = _selected_config.copy()
        config_display['password'] = '********'
        print(f"\n📡 当前数据库配置: {config_display}\n")
    
    return _selected_config
