"""
数据库管理模块
负责 virtual_inventory 表的数据库操作
"""

import pymysql
from datetime import datetime, timedelta
from app.utils.database_connection import get_db_connection as get_pooled_db_connection


# MySQL 数据库配置
MYSQL_CONFIG = {
    'host': '113.45.176.129',
    'port': 3306,
    'user': 'fsbbr_data',
    'password': 'wRCA8AGn3a568f4X',
    'database': 'fsbbr_data',
    'charset': 'utf8mb4',
    'autocommit': True,
    'use_unicode': True
}


class DatabaseManager:
    """数据库连接管理器，支持自动重连"""
    
    def __init__(self, config=None):
        self.config = config or MYSQL_CONFIG
        self.connection = None
        self.connect()
    
    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = get_pooled_db_connection()
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False
    
    def check_connection(self):
        """检查数据库连接状态"""
        if self.connection is None:
            return False
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def ensure_connection(self):
        """确保数据库连接可用，否则重连"""
        if not self.check_connection():
            print("数据库连接已断开，正在尝试重连...")
            if self.connect():
                print("数据库重连成功")
                return True
            else:
                print("数据库重连失败")
                return False
        return True
    
    def execute_query(self, query, params=None):
        """执行查询，自动处理断连重连"""
        if not self.ensure_connection():
            raise Exception("数据库连接不可用")
        
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchall()
                return result
        except Exception as e:
            if self.ensure_connection():
                with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(query, params)
                    result = cursor.fetchall()
                    return result
            else:
                raise e
    
    def execute_update(self, query, params=None):
        """执行更新操作，自动处理断连重连"""
        if not self.ensure_connection():
            raise Exception("数据库连接不可用")
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
                return cursor.rowcount
        except Exception as e:
            if self.ensure_connection():
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    self.connection.commit()
                    return cursor.rowcount
            else:
                raise e
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()


def get_db_connection():
    """获取数据库连接管理器实例"""
    return DatabaseManager(MYSQL_CONFIG)


def get_current_day_time_range():
    """
    获取当前日期 00:00 到 23:59 的时间范围
    例如：今天是 16 号，则返回 16 号 00:00 到 16 号 23:59
    """
    now = datetime.now()
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=23, minute=59, second=59, microsecond=0)
    
    return start_time.strftime('%Y-%m-%d %H:%M:%S'), end_time.strftime('%Y-%m-%d %H:%M:%S')


def extract_oe_numbers_from_msg(update_msg):
    """
    检查 update_msg 是否符合特定格式
    格式要求：必须同时包含"物料所属品牌"、"OE号"和"产品数据不存在,请核查数据"
    """
    if not update_msg:
        return False
    
    required_keywords = ["物料所属品牌", "OE号", "产品数据不存在,请核查数据"]
    return all(keyword in update_msg for keyword in required_keywords)


def load_data_from_mysql(supplier_name=None):
    """
    从 MySQL 数据库读取 virtual_inventory 表数据
    返回包含 oe_code、brand、update_msg 和 fetch_time 列的数据
    筛选条件：update_msg 符合特定格式 且 fetch_time 在指定时间范围内
    
    Args:
        supplier_name: 可选，指定供应商名称进行筛选，如 '佛山万拓'
    """
    db_manager = get_db_connection()
    try:
        if db_manager is None:
            raise Exception("数据库连接失败")
        
        start_time, end_time = get_current_day_time_range()
        print(f"时间筛选范围: {start_time} 到 {end_time}")
        
        # 根据是否指定供应商构建查询
        if supplier_name:
            query = """
            SELECT oe_code, brand, update_msg, fetch_time, supplier_name 
            FROM virtual_inventory 
            WHERE update_msg IS NOT NULL 
              AND update_msg != '' 
              AND fetch_time BETWEEN %s AND %s
              AND supplier_name = %s
            """
            results = db_manager.execute_query(query, (start_time, end_time, supplier_name))
            print(f"从数据库读取到 {len(results)} 条记录（已按时间范围和供应商 '{supplier_name}' 筛选）")
        else:
            query = """
            SELECT oe_code, brand, update_msg, fetch_time 
            FROM virtual_inventory 
            WHERE update_msg IS NOT NULL 
              AND update_msg != '' 
              AND fetch_time BETWEEN %s AND %s
            """
            results = db_manager.execute_query(query, (start_time, end_time))
            print(f"从数据库读取到 {len(results)} 条记录（已按时间范围筛选）")
        
        filtered_results = []
        for row in results:
            if extract_oe_numbers_from_msg(row['update_msg']):
                filtered_results.append({
                    'oe_code': row['oe_code'],
                    'brand': row['brand'],
                    'update_msg': row['update_msg'],
                    'fetch_time': row['fetch_time'],
                    'supplier_name': row.get('supplier_name', '')
                })
        
        if supplier_name:
            print(f"筛选出 {len(filtered_results)} 条符合特定格式、时间范围和供应商 '{supplier_name}' 的记录")
        else:
            print(f"筛选出 {len(filtered_results)} 条符合特定格式和时间范围的记录")
        return filtered_results
    except Exception as e:
        print(f"从数据库读取数据时发生错误: {e}")
        return []
    finally:
        db_manager.close()


def update_msg_with_processed_result(db_manager, oe_number, brand, result):
    """
    更新数据库中对应 OE 号和品牌的 update_msg 列
    """
    try:
        if db_manager:
            # 延迟导入 update_status 分类函数，避免循环依赖
            from backend.virtual_inventory_api import get_update_status
            sql = "UPDATE virtual_inventory SET update_msg = %s, update_status = %s WHERE oe_code = %s AND brand = %s"
            new_msg = f"OE号【{oe_number}】处理结果：{result}"
            new_status = get_update_status(new_msg)
            affected_rows = db_manager.execute_update(sql, (new_msg, new_status, oe_number, brand))
            print(f"OE号 {oe_number} 和品牌 {brand} 的处理结果已更新到数据库，影响行数: {affected_rows}")
    except Exception as e:
        print(f"更新数据库中 OE号 {oe_number} 和品牌 {brand} 的处理结果时出错: {e}")
