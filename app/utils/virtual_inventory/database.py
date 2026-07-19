# -*- coding: utf-8 -*-
"""
虚拟库存模块数据库工具

提供数据库连接管理、业务时间范围计算、业务数据清理等功能。
"""

import pymysql
from datetime import datetime

from ..database_connection import get_db_connection as get_pooled_db_connection
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')


DB_CONFIG = {
    'host': '113.45.176.129',
    'port': 3306,
    'user': 'fsbbr_data',
    'password': 'wRCA8AGn3a568f4X',
    'database': 'fsbbr_data',
    'charset': 'utf8mb4'
}


def get_business_time_range(current_time):
    """
    计算给定时间所属的业务时间范围
    业务时间：当天00:00到23:59
    """
    business_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    business_end = business_start.replace(hour=23, minute=59, second=59, microsecond=0)

    return business_start, business_end


def clean_business_time_data():
    """
    清理当前业务时间范围内的数据（所有公司表）
    """
    current_time = datetime.now()
    business_start, business_end = get_business_time_range(current_time)

    logger.info(f"当前时间: {current_time}")
    logger.info(f"业务时间范围: {business_start} 到 {business_end}")

    tables = [
        'virtual_inventory',
        'virtual_inventory_zhbbr',
        'virtual_inventory_zsbbr',
        'virtual_inventory_dgby',
        'virtual_inventory_dghf'
    ]

    db_manager = get_db_connection()
    try:
        for table in tables:
            # 检查是否存在该业务时间段的数据
            check_query = f"""
                SELECT COUNT(*) as count
                FROM {table}
                WHERE fetch_time >= %s AND fetch_time < %s
            """
            result = db_manager.execute_query(check_query, (business_start, business_end))
            count = result[0]['count']

            if count > 0:
                logger.info(f"[{table}] 发现 {count} 条属于当前业务时间段的数据，正在删除...")

                delete_query = f"""
                    DELETE FROM {table}
                    WHERE fetch_time >= %s AND fetch_time < %s
                """
                deleted_count = db_manager.execute_update(delete_query, (business_start, business_end))
                logger.info(f"[{table}] 已删除 {deleted_count} 条数据")
            else:
                logger.info(f"[{table}] 当前业务时间段内没有数据")

    except Exception as e:
        logger.exception(f"清理业务时间数据时出错")
    finally:
        db_manager.close()


class DatabaseManager:
    def __init__(self, config):
        self.config = config
        self.connection = None
        self.connect()

    def connect(self):
        """建立数据库连接"""
        try:
            # 使用连接池获取连接
            self.connection = get_pooled_db_connection()
            return True
        except Exception as e:
            logger.exception(f"数据库连接失败")
            return False

    def check_connection(self):
        """检查数据库连接状态"""
        if self.connection is None:
            return False
        try:
            # 使用ping方法检查连接，自动重连
            self.connection.ping(reconnect=True)
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    def ensure_connection(self):
        """确保数据库连接可用，否则重连"""
        if not self.check_connection():
            logger.info("数据库连接已断开，正在尝试重连...")
            if self.connect():
                logger.info("数据库重连成功")
                return True
            else:
                logger.error("数据库重连失败")
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
            # 如果查询失败，尝试重连后重试
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
            # 如果更新失败，尝试重连后重试
            if self.ensure_connection():
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    self.connection.commit()
                    return cursor.rowcount
            else:
                raise e

    def execute_many(self, query, data):
        """批量执行操作，自动处理断连重连"""
        if not self.ensure_connection():
            raise Exception("数据库连接不可用")

        try:
            with self.connection.cursor() as cursor:
                cursor.executemany(query, data)
                self.connection.commit()
                return cursor.rowcount
        except Exception as e:
            # 如果批量操作失败，尝试重连后重试
            if self.ensure_connection():
                with self.connection.cursor() as cursor:
                    cursor.executemany(query, data)
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
    return DatabaseManager(DB_CONFIG)


def clear_all_tables():
    """清空所有表的数据并重置自动递增ID，但保留virtual_inventory表"""
    db_manager = get_db_connection()
    try:
        cursor = db_manager.connection.cursor()

        tables = [
            'tenglong_data',
            'beiermale_data',
            'aichebeimu_foshan_data',
            'aichebeimu_dongguan_data',
            'aichebeimu_zhongshan_data',
            'robot_data',
            'external_data',
            'jiapei_data'
            # 注意：这里不包括 'virtual_inventory' 表
        ]

        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            cursor.execute(f"ALTER TABLE {table} AUTO_INCREMENT = 1")

        db_manager.connection.commit()
    finally:
        db_manager.close()


def delete_old_data():
    """删除50天前的数据（所有公司汇总表）"""
    db_manager = get_db_connection()
    try:
        tables = [
            'virtual_inventory',
            'virtual_inventory_zhbbr',
            'virtual_inventory_zsbbr',
            'virtual_inventory_dgby',
            'virtual_inventory_dghf'
        ]

        for table in tables:
            delete_sql = f"""
                DELETE FROM {table}
                WHERE fetch_time < DATE_SUB(NOW(), INTERVAL 50 DAY)
            """
            deleted_count = db_manager.execute_update(delete_sql)
            logger.info(f"[{table}] 已删除 {deleted_count} 条50天前的数据")
    finally:
        db_manager.close()
