"""
店铺经营指标表模型

对应数据库表：crmapp_shop_business_indicator
"""

from typing import Dict, Any, List, Optional
from app.utils.database_connection import get_db_connection


class ShopBusinessIndicatorModel:
    """
    经营指标表模型
    
    存储每日经营指标数据（接口3数据）
    """
    
    __tablename__ = 'crmapp_shop_business_indicator'
    
    def get_by_date(self, indicator_date: str) -> Optional[Dict[str, Any]]:
        """
        根据日期查询单条记录
        
        Args:
            indicator_date: 指标日期，格式 YYYY-MM-DD
            
        Returns:
            记录字典，不存在返回None
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT id, indicator_date, sales_amount, system_quote_rate,
                           order_customer_count, total_quote_rate, system_quote_rate_detail,
                           manual_quote_rate, whole_order_quote_rate, spot_quote_rate,
                           quote_conversion_rate, system_quote_conversion_rate,
                           avg_quote_quality_count, return_sku_count, sku_return_rate,
                           return_amount, amount_return_rate,
                           created_at, updated_at
                    FROM {self.__tablename__}
                    WHERE indicator_date = %s
                """
                cursor.execute(sql, (indicator_date,))
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
                    SELECT id, indicator_date, sales_amount, system_quote_rate,
                           order_customer_count, total_quote_rate, system_quote_rate_detail,
                           manual_quote_rate, whole_order_quote_rate, spot_quote_rate,
                           quote_conversion_rate, system_quote_conversion_rate,
                           avg_quote_quality_count, return_sku_count, sku_return_rate,
                           return_amount, amount_return_rate,
                           created_at, updated_at
                    FROM {self.__tablename__}
                    WHERE indicator_date BETWEEN %s AND %s
                    ORDER BY indicator_date
                """
                cursor.execute(sql, (start_date, end_date))
                return cursor.fetchall()
        finally:
            conn.close()
    
    def batch_insert(self, data_list: List[Dict[str, Any]]) -> int:
        """
        批量插入或更新记录
        
        使用 ON DUPLICATE KEY UPDATE 实现存在则更新、不存在则插入
        唯一索引：uk_indicator_date (indicator_date)
        
        Args:
            data_list: 数据字典列表，每个字典包含:
                - indicator_date: 日期
                - sales_amount: 销售额
                - system_quote_rate: 系统报价成交额比例
                - order_customer_count: 下单客户数
                - ...其他指标字段
                
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
                        (indicator_date, sales_amount, system_quote_rate, order_customer_count,
                         total_quote_rate, system_quote_rate_detail, manual_quote_rate,
                         whole_order_quote_rate, spot_quote_rate, quote_conversion_rate,
                         system_quote_conversion_rate, avg_quote_quality_count, return_sku_count,
                         sku_return_rate, return_amount, amount_return_rate)
                    VALUES 
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        sales_amount = VALUES(sales_amount),
                        system_quote_rate = VALUES(system_quote_rate),
                        order_customer_count = VALUES(order_customer_count),
                        total_quote_rate = VALUES(total_quote_rate),
                        system_quote_rate_detail = VALUES(system_quote_rate_detail),
                        manual_quote_rate = VALUES(manual_quote_rate),
                        whole_order_quote_rate = VALUES(whole_order_quote_rate),
                        spot_quote_rate = VALUES(spot_quote_rate),
                        quote_conversion_rate = VALUES(quote_conversion_rate),
                        system_quote_conversion_rate = VALUES(system_quote_conversion_rate),
                        avg_quote_quality_count = VALUES(avg_quote_quality_count),
                        return_sku_count = VALUES(return_sku_count),
                        sku_return_rate = VALUES(sku_return_rate),
                        return_amount = VALUES(return_amount),
                        amount_return_rate = VALUES(amount_return_rate),
                        updated_at = CURRENT_TIMESTAMP
                """
                values = [
                    (
                        d.get('indicator_date'),
                        d.get('sales_amount'),
                        d.get('system_quote_rate'),
                        d.get('order_customer_count'),
                        d.get('total_quote_rate'),
                        d.get('system_quote_rate_detail'),
                        d.get('manual_quote_rate'),
                        d.get('whole_order_quote_rate'),
                        d.get('spot_quote_rate'),
                        d.get('quote_conversion_rate'),
                        d.get('system_quote_conversion_rate'),
                        d.get('avg_quote_quality_count'),
                        d.get('return_sku_count'),
                        d.get('sku_return_rate'),
                        d.get('return_amount'),
                        d.get('amount_return_rate')
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
    
    def delete_by_date(self, indicator_date: str) -> int:
        """
        根据日期删除记录
        
        Args:
            indicator_date: 指标日期
            
        Returns:
            删除的行数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"DELETE FROM {self.__tablename__} WHERE indicator_date = %s"
                cursor.execute(sql, (indicator_date,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            print(f"删除失败: {e}")
            raise
        finally:
            conn.close()
    
    def get_latest(self, limit: int = 7) -> List[Dict[str, Any]]:
        """
        获取最新的N条记录
        
        Args:
            limit: 返回记录数
            
        Returns:
            记录字典列表
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT id, indicator_date, sales_amount, system_quote_rate,
                           order_customer_count, total_quote_rate, system_quote_rate_detail,
                           manual_quote_rate, whole_order_quote_rate, spot_quote_rate,
                           quote_conversion_rate, system_quote_conversion_rate,
                           avg_quote_quality_count, return_sku_count, sku_return_rate,
                           return_amount, amount_return_rate,
                           created_at, updated_at
                    FROM {self.__tablename__}
                    ORDER BY indicator_date DESC
                    LIMIT %s
                """
                cursor.execute(sql, (limit,))
                return cursor.fetchall()
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
                    SELECT id, indicator_date, sales_amount, system_quote_rate,
                           order_customer_count, total_quote_rate, system_quote_rate_detail,
                           manual_quote_rate, whole_order_quote_rate, spot_quote_rate,
                           quote_conversion_rate, system_quote_conversion_rate,
                           avg_quote_quality_count, return_sku_count, sku_return_rate,
                           return_amount, amount_return_rate,
                           created_at, updated_at
                    FROM {self.__tablename__}
                    ORDER BY indicator_date DESC
                    LIMIT %s
                """
                cursor.execute(sql, (limit,))
                return cursor.fetchall()
        finally:
            conn.close()
