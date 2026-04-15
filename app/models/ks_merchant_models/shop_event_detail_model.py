"""
店铺事件明细表模型

对应数据库表：crmapp_shop_event_detail
"""

from typing import Dict, Any, List, Optional
from app.utils.database_connection import get_db_connection


class ShopEventDetailModel:
    """
    事件明细表模型
    
    存储每日事件详情（接口2数据）
    """
    
    __tablename__ = 'crmapp_shop_event_detail'
    
    def get_by_date(self, event_date: str) -> List[Dict[str, Any]]:
        """
        根据日期查询所有事件明细
        
        Args:
            event_date: 事件日期，格式 YYYY-MM-DD
            
        Returns:
            记录字典列表
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT id, event_date, event_type_key, event_type_name,
                           event_count, statistics_unit, event_influence, event_suggest,
                           created_at, updated_at
                    FROM {self.__tablename__}
                    WHERE event_date = %s
                    ORDER BY event_count DESC
                """
                cursor.execute(sql, (event_date,))
                return cursor.fetchall()
        finally:
            conn.close()
    
    def get_by_date_and_type(self, event_date: str, event_type_key: str) -> Optional[Dict[str, Any]]:
        """
        根据日期和事件类型查询单条记录
        
        Args:
            event_date: 事件日期
            event_type_key: 事件类型标识
            
        Returns:
            记录字典，不存在返回None
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT id, event_date, event_type_key, event_type_name,
                           event_count, statistics_unit, event_influence, event_suggest,
                           created_at, updated_at
                    FROM {self.__tablename__}
                    WHERE event_date = %s AND event_type_key = %s
                """
                cursor.execute(sql, (event_date, event_type_key))
                return cursor.fetchone()
        finally:
            conn.close()
    
    def get_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        根据日期范围查询记录
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            记录字典列表
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT id, event_date, event_type_key, event_type_name,
                           event_count, statistics_unit, event_influence, event_suggest,
                           created_at, updated_at
                    FROM {self.__tablename__}
                    WHERE event_date BETWEEN %s AND %s
                    ORDER BY event_date DESC, event_count DESC
                """
                cursor.execute(sql, (start_date, end_date))
                return cursor.fetchall()
        finally:
            conn.close()
    
    def batch_insert(self, data_list: List[Dict[str, Any]]) -> int:
        """
        批量插入或更新记录
        
        使用 ON DUPLICATE KEY UPDATE 实现存在则更新、不存在则插入
        唯一索引：uk_date_type (event_date, event_type_key)
        
        Args:
            data_list: 数据字典列表，每个字典包含:
                - event_date: 日期
                - event_type_key: 事件类型标识
                - event_type_name: 事件类型名称
                - event_count: 事件数量
                - statistics_unit: 统计单位
                - event_influence: 影响说明
                - event_suggest: 处理建议
                
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
                        (event_date, event_type_key, event_type_name, event_count,
                         statistics_unit, event_influence, event_suggest)
                    VALUES 
                        (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        event_type_name = VALUES(event_type_name),
                        event_count = VALUES(event_count),
                        statistics_unit = VALUES(statistics_unit),
                        event_influence = VALUES(event_influence),
                        event_suggest = VALUES(event_suggest),
                        updated_at = CURRENT_TIMESTAMP
                """
                values = [
                    (
                        d['event_date'],
                        d['event_type_key'],
                        d.get('event_type_name', ''),
                        d.get('event_count', 0),
                        d.get('statistics_unit', ''),
                        d.get('event_influence', ''),
                        d.get('event_suggest', '')
                    )
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
            data: 数据字典
            
        Returns:
            影响的行数
        """
        return self.batch_insert([data])
    
    def delete_by_date(self, event_date: str) -> int:
        """
        根据日期删除所有记录
        
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
    
    def get_event_types_by_date(self, event_date: str) -> List[str]:
        """
        获取指定日期所有事件类型
        
        Args:
            event_date: 事件日期
            
        Returns:
            事件类型标识列表
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT event_type_key
                    FROM {self.__tablename__}
                    WHERE event_date = %s
                    ORDER BY event_count DESC
                """
                cursor.execute(sql, (event_date,))
                results = cursor.fetchall()
                return [r['event_type_key'] for r in results]
        finally:
            conn.close()
    
    def get_all(self, limit: int = 1000) -> List[Dict[str, Any]]:
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
                    SELECT id, event_date, event_type_key, event_type_name,
                           event_count, statistics_unit, event_influence, event_suggest,
                           created_at, updated_at
                    FROM {self.__tablename__}
                    ORDER BY event_date DESC, event_count DESC
                    LIMIT %s
                """
                cursor.execute(sql, (limit,))
                return cursor.fetchall()
        finally:
            conn.close()
