# -*- coding:utf-8 -*-
# @Time    : 2026/4/11 18:23
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : config.py
# @Software: PyCharm
import os
from pathlib import Path
from dotenv import load_dotenv

# # 获取项目根目录（从当前文件向上 2 层：config -> beihuo_system）
# BASE_DIR = Path(__file__).resolve().parent.parent
# # .env 文件路径（项目根目录下的 .env）
# ENV_PATH = BASE_DIR / ".env"
#
# # 加载 .env 文件中的环境变量
# load_dotenv(dotenv_path=ENV_PATH)


class ORMConfig:
    """SQLAlchemy ORM 配置类"""
    
    # 数据库连接配置（分开配置项）
    # 默认使用本地数据库
    HOST = os.getenv("ORM_MYSQL_HOST", "localhost")
    PORT = int(os.getenv("ORM_MYSQL_PORT", "3306"))
    USER = os.getenv("ORM_MYSQL_USER", "root")
    PASSWORD = os.getenv("ORM_MYSQL_PASSWORD", "root")
    DATABASE = os.getenv("ORM_MYSQL_DATABASE", "fsbbr_data_test")
    CHARSET = os.getenv("ORM_MYSQL_CHARSET", "utf8mb4")
    
    # 动态构建数据库连接 URL
    @classmethod
    def get_database_url(cls):
        """构建 SQLAlchemy 数据库连接 URL"""
        return f"mysql+pymysql://{cls.USER}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.DATABASE}?charset={cls.CHARSET}"
    
    # 连接池大小：保持的连接数
    POOL_SIZE = int(os.getenv("ORM_POOL_SIZE", "10"))
    
    # 最大溢出连接数：超过 pool_size 后可以额外创建的连接数
    MAX_OVERFLOW = int(os.getenv("ORM_MAX_OVERFLOW", "20"))
    
    # 连接池超时时间（秒）：获取连接时的最大等待时间
    POOL_TIMEOUT = int(os.getenv("ORM_POOL_TIMEOUT", "30"))
    
    # 连接回收时间（秒）：连接超过这个时间会被回收，避免 MySQL 断开连接
    POOL_RECYCLE = int(os.getenv("ORM_POOL_RECYCLE", "3600"))
    
    # 是否打印 SQL 语句：开发时设为 true 方便调试，生产环境设为 false
    ECHO = os.getenv("ORM_ECHO", "false").lower() == "true"
