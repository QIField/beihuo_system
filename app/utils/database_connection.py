import os
import pymysql
from pathlib import Path
from dbutils.pooled_db import PooledDB
from config.db_config import get_mysql_config  # 导入配置文件中的函数

# 创建连接池的全局变量
POOL = None


def create_pool():
    """创建数据库连接池"""
    global POOL
    
    if POOL is None:
        # 从配置文件获取数据库配置
        db_config = get_mysql_config()
        
        POOL = PooledDB(
            creator=pymysql,
            maxconnections=20,  # 最大连接数
            mincached=3,        # 最小缓存连接数
            maxcached=5,        # 最大缓存连接数
            maxshared=3,        # 最大共享连接数
            blocking=True,      # 超过最大连接数时是否阻塞等待
            setsession=[],      # 开始会话前执行的命令序列
            ping=0,             # ping MySQL服务端，检查是否连通，0表示不ping
            **db_config
        )


def get_db_connection():
    """
    获取数据库连接
    从连接池获取一个可用的连接
    """
    global POOL
    
    if POOL is None:
        create_pool()
    
    # 从连接池获取连接
    connection = POOL.connection()
    
    # 设置字符集以确保正确处理 utf8mb4
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute("SET CHARACTER SET utf8mb4")
            cursor.execute("SET character_set_connection=utf8mb4")
    except Exception as e:
        print(f"设置字符集时出错: {e}")
    
    return connection


def _execute_db_operation(operation_func, connection=None):
    """
    执行数据库操作的辅助函数
    
    参数:
        operation_func: 接收cursor参数的数据库操作函数
        connection: 可选的数据库连接对象，若为None则创建新连接
    """
    local_connection = connection is None
    conn = connection or get_db_connection()
    
    try:
        with conn.cursor() as cursor:
            result = operation_func(cursor)
        # 提交事务以确保更改生效
        conn.commit()
        return result
    except Exception as e:
        print(f"         ✗ 数据库操作出错: {str(e)}")
        # 回滚事务以确保数据一致性
        conn.rollback()
        return None
    finally:
        if local_connection and hasattr(conn, 'close'):
            # 如果是从连接池获取的连接，调用close()会将其返回到池中而不是实际关闭
            conn.close()