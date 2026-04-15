"""
店铺事件汇总表模型

对应数据库表：crmapp_shop_event_summary
"""

from typing import Dict, Any, List, Optional
from datetime import date
from app.utils.database_connection import get_db_connection


class ShopEventSummaryModel:
    """
    每日事件汇总表模型
    
    存储每日事件总数统计（接口1数据）
    """
    
    __tablename__ = 'crmapp_shop_event_summary'
    
    def get_by_date(self, event_date: str) -> Optional[Dict[str, Any]]:
        """
        根据日期查询单条记录
        
        Args:
            event_date: 事件日期，格式 YYYY-MM-DD
            
        Returns:
            记录字典，不存在返回None
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT id, event_date, total_event_count, created_at, updated_at
                    FROM {self.__tablename__}
                    WHERE event_date = %s
                """
                cursor.execute(sql, (event_date,))
                return cursor.fetchone()
        finally:
            conn.close()
    
    def get_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        根据日期范围查询记录
        
        Args:
            start_date: 开始日期，格式 YYYY-MM-DD
            end_date: 结束日期，格式 YYYY-MM-DD
            
        Returns:
            记录字典列表
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT id, event_date, total_event_count, created_at, updated_at
                    FROM {self.__tablename__}
                    WHERE event_date BETWEEN %s AND %s
                    ORDER BY event_date
                """
                cursor.execute(sql, (start_date, end_date))
                return cursor.fetchall()
        finally:
            conn.close()
    
    def batch_insert(self, data_list: List[Dict[str, Any]]) -> int:
        """
        批量插入或更新记录
        
        使用 ON DUPLICATE KEY UPDATE 实现存在则更新、不存在则插入
        
        Args:
            data_list: 数据字典列表，每个字典包含:
                - event_date: 日期
                - total_event_count: 事件总数
                
        Returns:
            影响的行数
        """
        if not data_list:
            return 0
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    INSERT INTO {self.__tablename__} 
                        (event_date, total_event_count)
                    VALUES 
                        (%s, %s)
                    ON DUPLICATE KEY UPDATE 
                        total_event_count = VALUES(total_event_count),
                        updated_at = CURRENT_TIMESTAMP
                """
                values = [
                    (d['event_date'], d['total_event_count'])
                    for d in data_list
                ]
                cursor.executemany(sql, values)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            print(f"批量插入失败: {e}")
            raise
        finally:
            conn.close()
    
    def save_or_update(self, data: Dict[str, Any]) -> int:
        """
        单条记录保存或更新
        
        Args:
            data: 数据字典，包含:
                - event_date: 日期
                - total_event_count: 事件总数
                
        Returns:
            影响的行数
        """
        return self.batch_insert([data])
    
    def delete_by_date(self, event_date: str) -> int:
        """
        根据日期删除记录
        
        Args:
            event_date: 事件日期
            
        Returns:
            删除的行数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"DELETE FROM {self.__tablename__} WHERE event_date = %s"
                cursor.execute(sql, (event_date,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            print(f"删除失败: {e}")
            raise
        finally:
            conn.close()
    
    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        查询所有记录
        
        Args:
            limit: 返回记录数限制
            
        Returns:
            记录字典列表
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT id, event_date, total_event_count, created_at, updated_at
                    FROM {self.__tablename__}
                    ORDER BY event_date DESC
                    LIMIT %s
                """
                cursor.execute(sql, (limit,))
                return cursor.fetchall()
        finally:
            conn.close()
