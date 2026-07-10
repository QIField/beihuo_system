import os
import pymysql
from pymysql.cursors import DictCursor, Cursor
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
            maxconnections=50,  # 最大连接数（线上并发高，增加到50）
            mincached=10,       # 最小缓存连接数（预热10个连接）
            maxcached=20,       # 最大缓存连接数
            maxshared=10,       # 最大共享连接数
            blocking=True,      # 超过最大连接数时是否阻塞等待
            setsession=[],      # 开始会话前执行的命令序列
            ping=1,             # 连接时ping MySQL服务端，检查连接是否有效
            **db_config
        )


def get_db_connection():
    """
    获取数据库连接
    从连接池获取一个可用的连接

    注意：业务代码中优先使用 DBCursorContext / db_cursor()，
    避免直接调用本函数后手动管理游标和事务。必须直接使用时，
    请显式指定 Cursor 或 DictCursor，不要依赖默认游标类型。
    """
    global POOL
    
    if POOL is None:
        create_pool()
    
    # 从连接池获取连接
    connection = POOL.connection()
    
    # 设置字符集以确保正确处理 utf8mb4
    # 注意：这里不能使用 with 语句，因为 with 会关闭游标但连接需要保持打开
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute("SET CHARACTER SET utf8mb4")
        cursor.execute("SET character_set_connection=utf8mb4")
    except Exception as e:
        print(f"设置字符集时出错: {e}")
    finally:
        # 确保游标被关闭，但连接保持打开
        if cursor:
            cursor.close()
    
    return connection


def get_tuple_cursor(connection):
    """
    获取返回元组格式的游标（默认行为）
    
    使用场景：
    - 只需要获取值，不需要列名
    - 性能略好于字典游标
    - 示例：result[0], row[1]
    
    :param connection: 数据库连接对象
    :return: 元组格式游标
    """
    return connection.cursor()


def get_dict_cursor(connection):
    """
    获取返回字典格式的游标
    
    使用场景：
    - 需要通过列名访问数据
    - 代码可读性更好
    - 示例：result['total'], row['name']
    
    :param connection: 数据库连接对象
    :return: 字典格式游标
    """
    return connection.cursor(DictCursor)


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
        print(f"         [失败] 数据库操作出错: {str(e)}")
        # 回滚事务以确保数据一致性
        conn.rollback()
        return None
    finally:
        if local_connection and hasattr(conn, 'close'):
            # 如果是从连接池获取的连接，调用close()会将其返回到池中而不是实际关闭
            conn.close()


# ==================== 数据库上下文管理器 ====================

class DBCursorContext:
    """
    数据库游标上下文管理器
    
    自动管理数据库连接和游标的生命周期，包括：
    - 自动获取和释放连接
    - 自动选择游标类型（元组或字典）
    - 自动提交或回滚事务
    - 异常安全（即使出错也会正确关闭资源）
    
    使用示例:
        # 使用字典游标（推荐用于查询）
        with DBCursorContext(dict_cursor=True) as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (1,))
            user = cursor.fetchone()
            print(user['name'])  # 通过列名访问
        
        # 使用元组游标（推荐用于简单查询）
        with DBCursorContext(dict_cursor=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]  # 通过索引访问
    """
    
    def __init__(self, dict_cursor=False, connection=None):
        """
        初始化上下文管理器
        
        :param dict_cursor: 是否使用字典游标，False表示使用元组游标
        :param connection: 可选的外部连接对象，如果不传则自动从连接池获取
        """
        self.dict_cursor = dict_cursor
        self.external_connection = connection
        self.connection = None
        self.cursor = None
        self._local_connection = False  # 标记是否本地创建的连接
    
    def __enter__(self):
        """
        进入 with 代码块时自动调用
        
        :return: 配置好的游标对象
        """
        # 获取连接（使用外部传入的或从连接池获取）
        if self.external_connection:
            self.connection = self.external_connection
            self._local_connection = False
        else:
            self.connection = get_db_connection()
            self._local_connection = True
        
        # 根据配置创建对应类型的游标
        if self.dict_cursor:
            self.cursor = self.connection.cursor(DictCursor)
        else:
            self.cursor = self.connection.cursor()
        
        return self.cursor
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出 with 代码块时自动调用（无论正常结束还是异常）
        
        :param exc_type: 异常类型（如果没有异常则为None）
        :param exc_val: 异常值
        :param exc_tb: 异常追踪信息
        :return: False 表示不吞掉异常，让异常继续向上抛出
        """
        try:
            if exc_type is not None:
                # 有异常发生，回滚事务
                if self.connection:
                    self.connection.rollback()
            else:
                # 正常结束，提交事务
                if self.connection:
                    self.connection.commit()
        except Exception as e:
            print(f"事务处理出错: {e}")
        finally:
            # 确保资源被正确释放
            if self.cursor:
                try:
                    self.cursor.close()
                except Exception:
                    pass
            
            # 只有本地创建的连接才需要关闭（归还连接池）
            if self._local_connection and self.connection:
                try:
                    self.connection.close()
                except Exception:
                    pass
        
        return False  # 不吞掉异常，让异常继续抛出


# 便捷的函数接口

def db_cursor(dict_cursor=False, connection=None):
    """
    获取数据库游标上下文管理器
    
    这是一个便捷的工厂函数，用于快速创建 DBCursorContext
    
    :param dict_cursor: 是否使用字典游标，默认为False（元组游标）
    :param connection: 可选的外部连接对象
    :return: DBCursorContext 上下文管理器
    
    使用示例:
        # 字典游标 - 通过列名访问数据
        with db_cursor(dict_cursor=True) as cursor:
            cursor.execute("SELECT id, name FROM users WHERE id = %s", (1,))
            user = cursor.fetchone()
            print(f"用户: {user['name']}")
        
        # 元组游标 - 通过索引访问数据
        with db_cursor(dict_cursor=False) as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM users")
            result = cursor.fetchone()
            print(f"总数: {result[0]}")
    """
    return DBCursorContext(dict_cursor=dict_cursor, connection=connection)


def db_query_one(sql, params=None, dict_cursor=True):
    """
    执行查询并返回单条记录
    
    这是一个高级封装，直接执行SQL并返回结果，无需手动管理游标
    
    :param sql: SQL查询语句
    :param params: SQL参数元组或列表
    :param dict_cursor: 是否使用字典游标，默认为True
    :return: 单条记录（字典或元组），如果没有结果则返回None
    
    使用示例:
        user = db_query_one("SELECT * FROM users WHERE id = %s", (1,))
        if user:
            print(user['name'])
        
        count = db_query_one("SELECT COUNT(*) as total FROM users", dict_cursor=True)
        if count:
            print(count['total'])
    """
    with DBCursorContext(dict_cursor=dict_cursor) as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchone()


def db_query_all(sql, params=None, dict_cursor=True):
    """
    执行查询并返回所有记录
    
    :param sql: SQL查询语句
    :param params: SQL参数元组或列表
    :param dict_cursor: 是否使用字典游标，默认为True
    :return: 记录列表（列表中的每个元素是字典或元组）
    
    使用示例:
        users = db_query_all("SELECT * FROM users WHERE status = %s", ('active',))
        for user in users:
            print(user['name'])
    """
    with DBCursorContext(dict_cursor=dict_cursor) as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchall()


def db_execute(sql, params=None):
    """
    执行INSERT、UPDATE、DELETE等操作
    
    :param sql: SQL执行语句
    :param params: SQL参数元组或列表
    :return: 受影响的行数，如果出错则返回-1
    
    使用示例:
        affected = db_execute("UPDATE users SET name = %s WHERE id = %s", ("张三", 1))
        print(f"更新了 {affected} 条记录")
    """
    try:
        with DBCursorContext(dict_cursor=False) as cursor:
            return cursor.execute(sql, params or ())
    except Exception as e:
        print(f"执行SQL出错: {e}")
        return -1