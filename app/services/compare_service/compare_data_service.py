"""
比价模块数据服务层
用于操作 crmapp_compare_summary 表的增删改查
"""
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from app.utils.database_connection import get_db_connection


class CompareDataService:
    """比价数据汇总表服务类"""
    
    TABLE_NAME = 'crmapp_compare_summary'
    
    # 表字段定义（与数据库字段对应）
    FIELDS = [
        'id', 'oe', 'brand', 'company', 'product_name', 'vehicle_brand', 'replace_number',
        'brand_code', 'inquiry_count', 'product_level', 'best_sales_month',
        'best_sales_season', 'max_price', 'min_price', 'supplier_price',
        'dealer_purchase_price', 'dealer_sale_price', 'price_update_time',
        'today_sales', 'yesterday_sales', 'month_sales', 'avg_sales_12m',
        'avg_sales_6m', 'sales_7d', 'product_remark', 'created_time', 'updated_time'
    ]
    
    @staticmethod
    def create_table():
        """创建比价数据汇总表（如果不存在）"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS crmapp_compare_summary (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                    oe VARCHAR(255) NOT NULL COMMENT 'OE号',
                    brand VARCHAR(255) COMMENT '品牌',
                    company VARCHAR(100) DEFAULT 'fsbbr' COMMENT '公司/门店代码',
                    product_name VARCHAR(500) COMMENT '产品名称',
                    vehicle_brand VARCHAR(255) COMMENT '车辆品牌',
                    replace_number VARCHAR(255) COMMENT '替换号',
                    brand_code VARCHAR(255) COMMENT '品牌编码',
                    inquiry_count INT DEFAULT 0 COMMENT '询价次数',
                    product_level VARCHAR(50) COMMENT '产品等级',
                    best_sales_month VARCHAR(20) COMMENT '销量最好的月份',
                    best_sales_season VARCHAR(20) COMMENT '销量最好的季节',
                    max_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '最高价',
                    min_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '最低价',
                    supplier_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '供应商价格',
                    dealer_purchase_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '4S含税进价',
                    dealer_sale_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '4S含税售价',
                    price_update_time DATETIME COMMENT '更新价格时间',
                    today_sales INT DEFAULT 0 COMMENT '今日销量',
                    yesterday_sales INT DEFAULT 0 COMMENT '昨日销量',
                    month_sales INT DEFAULT 0 COMMENT '本月销量',
                    avg_sales_12m DECIMAL(10,2) DEFAULT 0.00 COMMENT '近12个月月均销量',
                    avg_sales_6m DECIMAL(10,2) DEFAULT 0.00 COMMENT '近6个月月均销量',
                    sales_7d INT DEFAULT 0 COMMENT '近7天销量',
                    product_remark TEXT COMMENT '系统产品备注',
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_oe (oe),
                    INDEX idx_brand (brand),
                    INDEX idx_company (company),
                    INDEX idx_product_name (product_name),
                    INDEX idx_vehicle_brand (vehicle_brand),
                    INDEX idx_brand_code (brand_code),
                    INDEX idx_oe_brand (oe, brand),
                    INDEX idx_oe_brand_company (oe, brand, company),
                    INDEX idx_updated_time (updated_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='比价数据汇总表';
                """
                cursor.execute(create_table_sql)
                conn.commit()
                print(f"表 {CompareDataService.TABLE_NAME} 创建成功或已存在")
                return True
        except Exception as e:
            print(f"创建表时出错: {str(e)}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def insert(data: Dict) -> int:
        """
        插入单条数据
        
        参数:
            data: 字典，包含字段名和值
            
        返回:
            插入记录的ID
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 过滤掉不存在的字段
                valid_data = {k: v for k, v in data.items() if k in CompareDataService.FIELDS}
                
                if not valid_data:
                    raise ValueError("没有有效的字段数据")
                
                columns = ', '.join(valid_data.keys())
                placeholders = ', '.join(['%s'] * len(valid_data))
                sql = f"INSERT INTO {CompareDataService.TABLE_NAME} ({columns}) VALUES ({placeholders})"
                
                cursor.execute(sql, list(valid_data.values()))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            print(f"插入数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def batch_insert(data_list: List[Dict]) -> int:
        """
        批量插入数据
        
        参数:
            data_list: 字典列表
            
        返回:
            插入的记录数
        """
        if not data_list:
            return 0
            
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 获取第一条数据的所有字段
                valid_data = {k: v for k, v in data_list[0].items() if k in CompareDataService.FIELDS}
                columns = ', '.join(valid_data.keys())
                placeholders = ', '.join(['%s'] * len(valid_data))
                sql = f"INSERT INTO {CompareDataService.TABLE_NAME} ({columns}) VALUES ({placeholders})"
                
                # 准备数据
                values = []
                for data in data_list:
                    valid_data = {k: v for k, v in data.items() if k in CompareDataService.FIELDS}
                    values.append(list(valid_data.values()))
                
                cursor.executemany(sql, values)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            print(f"批量插入数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def update_by_oe(oe: str, data: Dict) -> int:
        """
        根据OE号更新数据
        
        参数:
            oe: OE号
            data: 要更新的字段和值
            
        返回:
            更新的记录数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 过滤掉不存在的字段和id字段
                valid_data = {k: v for k, v in data.items() 
                             if k in CompareDataService.FIELDS and k != 'id'}
                
                if not valid_data:
                    return 0
                
                set_clause = ', '.join([f"{k} = %s" for k in valid_data.keys()])
                sql = f"UPDATE {CompareDataService.TABLE_NAME} SET {set_clause} WHERE oe = %s"
                
                cursor.execute(sql, list(valid_data.values()) + [oe])
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            print(f"更新数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def update_by_id(record_id: int, data: Dict) -> int:
        """
        根据ID更新数据
        
        参数:
            record_id: 记录ID
            data: 要更新的字段和值
            
        返回:
            更新的记录数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                valid_data = {k: v for k, v in data.items() 
                             if k in CompareDataService.FIELDS and k != 'id'}
                
                if not valid_data:
                    return 0
                
                set_clause = ', '.join([f"{k} = %s" for k in valid_data.keys()])
                sql = f"UPDATE {CompareDataService.TABLE_NAME} SET {set_clause} WHERE id = %s"
                
                cursor.execute(sql, list(valid_data.values()) + [record_id])
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            print(f"更新数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def delete_by_oe(oe: str) -> int:
        """
        根据OE号删除数据
        
        参数:
            oe: OE号
            
        返回:
            删除的记录数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"DELETE FROM {CompareDataService.TABLE_NAME} WHERE oe = %s"
                cursor.execute(sql, [oe])
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            print(f"删除数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def delete_by_id(record_id: int) -> int:
        """
        根据ID删除数据
        
        参数:
            record_id: 记录ID
            
        返回:
            删除的记录数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"DELETE FROM {CompareDataService.TABLE_NAME} WHERE id = %s"
                cursor.execute(sql, [record_id])
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            print(f"删除数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def get_by_oe(oe: str) -> Optional[Dict]:
        """
        根据OE号查询单条数据
        
        参数:
            oe: OE号
            
        返回:
            数据字典，如果不存在返回None
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"SELECT * FROM {CompareDataService.TABLE_NAME} WHERE oe = %s LIMIT 1"
                cursor.execute(sql, [oe])
                result = cursor.fetchone()
                
                if result:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, result))
                return None
        except Exception as e:
            print(f"查询数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def get_by_id(record_id: int) -> Optional[Dict]:
        """
        根据ID查询单条数据
        
        参数:
            record_id: 记录ID
            
        返回:
            数据字典，如果不存在返回None
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"SELECT * FROM {CompareDataService.TABLE_NAME} WHERE id = %s LIMIT 1"
                cursor.execute(sql, [record_id])
                result = cursor.fetchone()
                
                if result:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, result))
                return None
        except Exception as e:
            print(f"查询数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def list_data(
        oe: str = '',
        brand: str = '',
        product_name: str = '',
        vehicle_brand: str = '',
        company: str = '',
        page: int = 1,
        limit: int = 100,
        order_by: str = 'updated_time',
        order_desc: bool = True
    ) -> Tuple[List[Dict], int]:
        """
        查询数据列表（支持分页和筛选）
        
        参数:
            oe: OE号筛选
            brand: 品牌筛选
            product_name: 产品名称筛选
            vehicle_brand: 车辆品牌筛选
            company: 公司/组织筛选（必填）
            page: 页码
            limit: 每页条数
            order_by: 排序字段
            order_desc: 是否降序
            
        返回:
            (数据列表, 总记录数)
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 构建WHERE条件
                where_conditions = []
                params = []
                
                # 必须按公司/组织过滤
                if company:
                    where_conditions.append("company = %s")
                    params.append(company)
                
                if oe:
                    where_conditions.append("oe LIKE %s")
                    params.append(f"%{oe}%")
                if brand:
                    where_conditions.append("brand LIKE %s")
                    params.append(f"%{brand}%")
                if product_name:
                    where_conditions.append("product_name LIKE %s")
                    params.append(f"%{product_name}%")
                if vehicle_brand:
                    where_conditions.append("vehicle_brand LIKE %s")
                    params.append(f"%{vehicle_brand}%")
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                # 查询总数
                count_sql = f"SELECT COUNT(*) FROM {CompareDataService.TABLE_NAME} {where_clause}"
                cursor.execute(count_sql, params)
                total = cursor.fetchone()[0]
                
                # 查询数据
                order_direction = "DESC" if order_desc else "ASC"
                offset = (page - 1) * limit
                
                data_sql = f"""
                    SELECT * FROM {CompareDataService.TABLE_NAME}
                    {where_clause}
                    ORDER BY {order_by} {order_direction}
                    LIMIT %s OFFSET %s
                """
                cursor.execute(data_sql, params + [limit, offset])
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                data = []
                for row in rows:
                    item = dict(zip(columns, row))
                    # 格式化时间字段
                    for time_field in ['price_update_time', 'created_time', 'updated_time']:
                        if item.get(time_field):
                            if hasattr(item[time_field], 'strftime'):
                                item[time_field] = item[time_field].strftime('%Y-%m-%d %H:%M:%S')
                    # 格式化价格字段
                    for price_field in ['max_price', 'min_price', 'supplier_price', 
                                       'dealer_purchase_price', 'dealer_sale_price',
                                       'avg_sales_12m', 'avg_sales_6m']:
                        if item.get(price_field) is not None:
                            item[price_field] = float(item[price_field])
                    data.append(item)
                
                return data, total
        except Exception as e:
            print(f"查询列表时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def get_all_data() -> List[Dict]:
        """
        获取所有数据（不分页，用于导出）
        
        返回:
            所有数据列表
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"SELECT * FROM {CompareDataService.TABLE_NAME} ORDER BY updated_time DESC"
                cursor.execute(sql)
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                data = []
                for row in rows:
                    item = dict(zip(columns, row))
                    # 格式化时间字段
                    for time_field in ['price_update_time', 'created_time', 'updated_time']:
                        if item.get(time_field):
                            if hasattr(item[time_field], 'strftime'):
                                item[time_field] = item[time_field].strftime('%Y-%m-%d %H:%M:%S')
                    data.append(item)
                
                return data
        except Exception as e:
            print(f"查询所有数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def upsert_by_oe_brand_company(data: Dict) -> int:
        """
        根据OE号+品牌+公司插入或更新数据（如果存在则更新，不存在则插入）
        依赖数据库唯一索引 uk_oe_brand_company 防止重复
        
        参数:
            data: 数据字典，必须包含oe、brand和company字段
            
        返回:
            记录ID
        """
        if 'oe' not in data or not data['oe']:
            raise ValueError("数据必须包含oe字段")
        if 'company' not in data or not data['company']:
            raise ValueError("数据必须包含company字段")
        
        # 根据 oe + brand + company 查询是否已存在
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    SELECT id FROM {CompareDataService.TABLE_NAME} 
                    WHERE oe = %s AND brand = %s AND company = %s LIMIT 1
                """, (data['oe'], data.get('brand', ''), data['company']))
                result = cursor.fetchone()
                
                if result:
                    # 更新
                    record_id = result[0]
                    CompareDataService.update_by_id(record_id, data)
                    return record_id
                else:
                    # 插入
                    return CompareDataService.insert(data)
        finally:
            conn.close()
    
    @staticmethod
    def clear_all_data() -> int:
        """
        清空所有数据（慎用）
        
        返回:
            删除的记录数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = f"DELETE FROM {CompareDataService.TABLE_NAME}"
                cursor.execute(sql)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            print(f"清空数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def get_statistics() -> Dict:
        """
        获取统计数据
        
        返回:
            统计信息字典
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                stats = {}
                
                # 总记录数
                cursor.execute(f"SELECT COUNT(*) FROM {CompareDataService.TABLE_NAME}")
                stats['total_count'] = cursor.fetchone()[0]
                
                # 唯一OE数量
                cursor.execute(f"SELECT COUNT(DISTINCT oe) FROM {CompareDataService.TABLE_NAME}")
                stats['unique_oe_count'] = cursor.fetchone()[0]
                
                # 唯一品牌数量
                cursor.execute(f"SELECT COUNT(DISTINCT brand) FROM {CompareDataService.TABLE_NAME} WHERE brand IS NOT NULL")
                stats['unique_brand_count'] = cursor.fetchone()[0]
                
                # 价格统计
                cursor.execute(f"""
                    SELECT 
                        MIN(min_price), MAX(max_price), AVG(supplier_price),
                        AVG(dealer_purchase_price), AVG(dealer_sale_price)
                    FROM {CompareDataService.TABLE_NAME}
                    WHERE min_price > 0 OR max_price > 0
                """)
                result = cursor.fetchone()
                stats['min_price'] = float(result[0]) if result[0] else 0
                stats['max_price'] = float(result[1]) if result[1] else 0
                stats['avg_supplier_price'] = float(result[2]) if result[2] else 0
                stats['avg_dealer_purchase_price'] = float(result[3]) if result[3] else 0
                stats['avg_dealer_sale_price'] = float(result[4]) if result[4] else 0
                
                # 销量统计
                cursor.execute(f"""
                    SELECT 
                        SUM(today_sales), SUM(yesterday_sales), SUM(month_sales),
                        SUM(sales_7d)
                    FROM {CompareDataService.TABLE_NAME}
                """)
                result = cursor.fetchone()
                stats['total_today_sales'] = int(result[0]) if result[0] else 0
                stats['total_yesterday_sales'] = int(result[1]) if result[1] else 0
                stats['total_month_sales'] = int(result[2]) if result[2] else 0
                stats['total_7d_sales'] = int(result[3]) if result[3] else 0
                
                return stats
        except Exception as e:
            print(f"获取统计数据时出错: {str(e)}")
            raise
        finally:
            conn.close()


# 便捷函数（模块级别）
def init_compare_summary_table():
    """初始化比价数据汇总表"""
    return CompareDataService.create_table()


def insert_compare_data(data: Dict) -> int:
    """插入单条数据"""
    return CompareDataService.insert(data)


def batch_insert_compare_data(data_list: List[Dict]) -> int:
    """批量插入数据"""
    return CompareDataService.batch_insert(data_list)


def update_compare_data_by_oe(oe: str, data: Dict) -> int:
    """根据OE更新数据"""
    return CompareDataService.update_by_oe(oe, data)


def get_compare_data_by_oe(oe: str) -> Optional[Dict]:
    """根据OE查询数据"""
    return CompareDataService.get_by_oe(oe)


def list_compare_data(**kwargs) -> Tuple[List[Dict], int]:
    """查询数据列表"""
    return CompareDataService.list_data(**kwargs)


def upsert_compare_data(data: Dict) -> int:
    """插入或更新数据"""
    return CompareDataService.upsert_by_oe(data)
