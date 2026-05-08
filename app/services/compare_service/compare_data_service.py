"""
比价模块数据服务层
用于操作 crmapp_compare_summary 表的增删改查
"""
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pymysql
from app.utils.database_connection import get_db_connection
from app.utils.search.parser import parse_space, parse_comma


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
        'avg_sales_6m', 'sales_7d', 'sales_6m', 'sales_12m', 'product_remark',
        'updated_time'
    ]
    
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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
    
    # 允许的排序字段白名单（防止SQL注入）
    ALLOWED_SORT_FIELDS = {
        'oe', 'brand', 'product_name', 'vehicle_brand',
        'supplier_price', 'dealer_purchase_price', 'dealer_sale_price',
        'max_price', 'min_price', 'inquiry_count',
        'today_sales', 'yesterday_sales', 'month_sales',
        'avg_sales_12m', 'avg_sales_6m', 'sales_7d', 'sales_6m', 'sales_12m',
        'updated_time', 'price_update_time', 'product_level'
    }

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
        order_desc: bool = True,
        sort_field: str = '',
        sort_order: str = 'asc'
    ) -> Tuple[List[Dict], int]:
        """
        查询数据列表（支持分页、筛选和排序）

        参数:
            oe: OE号筛选
            brand: 品牌筛选
            product_name: 产品名称筛选
            vehicle_brand: 车辆品牌筛选
            company: 公司/组织筛选（必填）
            page: 页码
            limit: 每页条数
            order_by: 默认排序字段
            order_desc: 是否降序
            sort_field: 用户点击的排序字段（优先级高于order_by）
            sort_order: 排序方向 asc/desc

        返回:
            (数据列表, 总记录数)
        """
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.Cursor) as cursor:
            # 构建WHERE条件
            where_conditions = []
            params = []

            # 必须按公司/组织过滤
            if company:
                where_conditions.append("company = %s")
                params.append(company)

            # 处理多行搜索
            oe_list = parse_space(oe) if oe else []
            brand_list = parse_comma(brand) if brand else []
            product_name_list = parse_comma(product_name) if product_name else []
            vehicle_brand_list = parse_comma(vehicle_brand) if vehicle_brand else []

            if oe_list:
                or_conditions = []
                for item in oe_list:
                    or_conditions.append("oe LIKE %s")
                    params.append(f"%{item}%")
                where_conditions.append("(" + " OR ".join(or_conditions) + ")")

            if brand_list:
                or_conditions = []
                for item in brand_list:
                    or_conditions.append("brand LIKE %s")
                    params.append(f"%{item}%")
                where_conditions.append("(" + " OR ".join(or_conditions) + ")")

            if product_name_list:
                or_conditions = []
                for item in product_name_list:
                    or_conditions.append("product_name LIKE %s")
                    params.append(f"%{item}%")
                where_conditions.append("(" + " OR ".join(or_conditions) + ")")

            if vehicle_brand_list:
                or_conditions = []
                for item in vehicle_brand_list:
                    or_conditions.append("vehicle_brand LIKE %s")
                    params.append(f"%{item}%")
                where_conditions.append("(" + " OR ".join(or_conditions) + ")")

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            # 查询总数
            count_sql = f"SELECT COUNT(*) FROM {CompareDataService.TABLE_NAME} {where_clause}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            # 确定排序字段（优先使用用户指定的排序字段）
            if sort_field and sort_field in CompareDataService.ALLOWED_SORT_FIELDS:
                final_order_by = sort_field
                final_order_desc = sort_order == 'desc'
            else:
                final_order_by = order_by
                final_order_desc = order_desc

            # 查询数据
            order_direction = "DESC" if final_order_desc else "ASC"
            offset = (page - 1) * limit

            # 价格字段特殊处理：NULL 和 0 放在最后，确保按有效价格排序
            price_fields = {'supplier_price', 'dealer_purchase_price', 'dealer_sale_price', 'max_price', 'min_price'}
            if sort_field in price_fields:
                # 使用 CASE WHEN 将 NULL 和 0 排在最后
                nulls_last = "DESC" if final_order_desc else "ASC"
                order_clause = f"CASE WHEN {sort_field} IS NULL OR {sort_field} = 0 THEN 1 ELSE 0 END ASC, {sort_field} {order_direction}"
            else:
                order_clause = f"{final_order_by} {order_direction}"

            data_sql = f"""
                SELECT * FROM {CompareDataService.TABLE_NAME}
                {where_clause}
                ORDER BY {order_clause}
                LIMIT %s OFFSET %s
            """
            cursor.execute(data_sql, params + [limit, offset])

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            data = []
            for row in rows:
                item = dict(zip(columns, row))
                # 格式化时间字段
                for time_field in ['price_update_time', 'updated_time']:
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
                
                # 调试：打印前3条数据的供应商价格
                if len(data) <= 3:
                    print(f"[DEBUG] supplier_price 调试: oe={item.get('oe')}, supplier_price={item.get('supplier_price')}, type={type(item.get('supplier_price'))}")

            return data, total
        
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
                sql = f"SELECT * FROM {CompareDataService.TABLE_NAME} ORDER BY updated_time DESC"
                cursor.execute(sql)
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                data = []
                for row in rows:
                    item = dict(zip(columns, row))
                    # 格式化时间字段
                    for time_field in ['price_update_time', 'updated_time']:
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
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


    @staticmethod
    def get_quote_history_batch(product_keys: List[Tuple[str, str]], company: str = 'fsbbr', months: int = 36) -> Dict[str, List[Dict]]:
        """
        批量查询多个产品的询价历史
        
        参数:
            product_keys: 产品标识列表，每个元素为 (oe, brand) 元组
            company: 公司代码
            months: 查询最近多少个月的数据，默认36个月
            
        返回:
            字典，key为 "oe|brand"，value为该产品的询价历史列表
            每个历史记录包含：year_month, quote_count
        """
        if not product_keys:
            return {}
        
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
                # 计算起始年月（最近N个月）
                from datetime import datetime, timedelta
                now = datetime.now()
                start_date = now - timedelta(days=30 * months)
                start_year_month = start_date.strftime('%Y-%m')
                
                # 构建 OR 条件查询多个产品
                or_conditions = []
                params = [company, start_year_month]
                
                for oe, brand in product_keys:
                    or_conditions.append("(oe = %s AND brand = %s)")
                    params.extend([oe, brand])
                
                where_clause = " OR ".join(or_conditions)
                
                sql = f"""
                    SELECT oe, brand, `year_month`, quote_count
                    FROM crmapp_quote_count_ks
                    WHERE company = %s AND `year_month` >= %s AND ({where_clause})
                    ORDER BY oe, brand, `year_month` DESC
                """
                
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                
                # 按产品分组
                result = {}
                for row in rows:
                    oe, brand, year_month, quote_count = row
                    key = f"{oe}|{brand}"
                    if key not in result:
                        result[key] = []
                    result[key].append({
                        'year_month': year_month,
                        'quote_count': quote_count
                    })
                
                return result
        except Exception as e:
            print(f"批量查询询价历史时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def get_quote_history(oe: str, brand: str, company: str = 'fsbbr', months: int = 36) -> List[Dict]:
        """
        查询单个产品的询价历史
        
        参数:
            oe: OE号
            brand: 品牌
            company: 公司代码
            months: 查询最近多少个月的数据
            
        返回:
            询价历史列表，每个元素包含 year_month 和 quote_count
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
                # 计算起始年月
                from datetime import datetime, timedelta
                now = datetime.now()
                start_date = now - timedelta(days=30 * months)
                start_year_month = start_date.strftime('%Y-%m')
                
                sql = """
                    SELECT `year_month`, quote_count
                    FROM crmapp_quote_count_ks
                    WHERE oe = %s AND brand = %s AND company = %s AND `year_month` >= %s
                    ORDER BY `year_month` DESC
                """
                
                cursor.execute(sql, (oe, brand, company, start_year_month))
                rows = cursor.fetchall()
                
                return [{'year_month': row[0], 'quote_count': row[1]} for row in rows]
        except Exception as e:
            print(f"查询询价历史时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def get_oe_with_different_replace_numbers(
        oe: str = '',
        brand: str = '',
        product_name: str = '',
        vehicle_brand: str = '',
        company: str = '',
        page: int = 1,
        limit: int = 100
    ) -> Tuple[List[Dict], int]:
        """
        查询 replace_number 有差异的 OE 分组数据
        
        逻辑：
        1. 先找出有差异的 oe（该 oe 下不同 brand 的 replace_number 不一致）
        2. 查询这些 oe 的所有数据（包含所有 brand）
        3. 支持分页和筛选
        
        参数:
            oe: OE号筛选
            brand: 品牌筛选
            product_name: 产品名称筛选
            vehicle_brand: 车辆品牌筛选
            company: 公司/组织筛选
            page: 页码
            limit: 每页条数
            
        返回:
            (数据列表, 总记录数)
        """
        conn = get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.Cursor) as cursor:
                # 构建基础 WHERE 条件
                where_conditions = []
                params = []
                
                # 必须按公司过滤
                if company:
                    where_conditions.append("company = %s")
                    params.append(company)
                
                # 处理多行搜索
                oe_list = parse_space(oe) if oe else []
                brand_list = parse_comma(brand) if brand else []
                product_name_list = parse_comma(product_name) if product_name else []
                vehicle_brand_list = parse_comma(vehicle_brand) if vehicle_brand else []
                
                if oe_list:
                    or_conditions = []
                    for item in oe_list:
                        or_conditions.append("oe LIKE %s")
                        params.append(f"%{item}%")
                    where_conditions.append("(" + " OR ".join(or_conditions) + ")")
                
                if brand_list:
                    or_conditions = []
                    for item in brand_list:
                        or_conditions.append("brand LIKE %s")
                        params.append(f"%{item}%")
                    where_conditions.append("(" + " OR ".join(or_conditions) + ")")
                
                if product_name_list:
                    or_conditions = []
                    for item in product_name_list:
                        or_conditions.append("product_name LIKE %s")
                        params.append(f"%{item}%")
                    where_conditions.append("(" + " OR ".join(or_conditions) + ")")
                
                if vehicle_brand_list:
                    or_conditions = []
                    for item in vehicle_brand_list:
                        or_conditions.append("vehicle_brand LIKE %s")
                        params.append(f"%{item}%")
                    where_conditions.append("(" + " OR ".join(or_conditions) + ")")
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else "WHERE 1=1"
                
                # 第一步：找出有差异的 oe
                # 使用子查询：按 oe 分组，统计不同 replace_number 的数量
                diff_oe_sql = f"""
                    SELECT oe FROM {CompareDataService.TABLE_NAME}
                    {where_clause}
                    GROUP BY oe
                    HAVING COUNT(DISTINCT IFNULL(replace_number, '')) > 1
                """
                
                cursor.execute(diff_oe_sql, params)
                diff_oe_rows = cursor.fetchall()
                diff_oe_list = [row[0] for row in diff_oe_rows]
                
                if not diff_oe_list:
                    return [], 0
                
                # 第二步：查询这些 oe 的总数
                # 构建 IN 条件
                in_placeholders = ', '.join(['%s'] * len(diff_oe_list))
                count_sql = f"""
                    SELECT COUNT(*) FROM {CompareDataService.TABLE_NAME}
                    WHERE oe IN ({in_placeholders})
                    {(" AND " + " AND ".join(where_conditions)) if where_conditions else ""}
                """
                count_params = diff_oe_list + params if where_conditions else diff_oe_list
                cursor.execute(count_sql, count_params)
                total = cursor.fetchone()[0]
                
                # 第三步：查询具体数据（分页）
                offset = (page - 1) * limit
                data_sql = f"""
                    SELECT * FROM {CompareDataService.TABLE_NAME}
                    WHERE oe IN ({in_placeholders})
                    {(" AND " + " AND ".join(where_conditions)) if where_conditions else ""}
                    ORDER BY oe, brand
                    LIMIT %s OFFSET %s
                """
                data_params = diff_oe_list + params + [limit, offset] if where_conditions else diff_oe_list + [limit, offset]
                
                cursor.execute(data_sql, data_params)
                rows = cursor.fetchall()
                
                columns = [desc[0] for desc in cursor.description]
                data = []
                oe_brand_list = []  # 收集所有oe和brand用于批量查询
                for row in rows:
                    item = dict(zip(columns, row))
                    # 格式化时间字段
                    for time_field in ['price_update_time', 'updated_time', 'created_time']:
                        if item.get(time_field):
                            if hasattr(item[time_field], 'strftime'):
                                item[time_field] = item[time_field].strftime('%Y-%m-%d %H:%M:%S')
                    # 格式化价格字段
                    for price_field in ['max_price', 'min_price', 'supplier_price',
                                       'dealer_purchase_price', 'dealer_sale_price',
                                       'avg_sales_12m', 'avg_sales_6m']:
                        if item.get(price_field) is not None:
                            item[price_field] = float(item[price_field])
                    
                    # 收集oe和brand用于批量查询库存和采购历史
                    oe_brand_list.append((item.get('oe', ''), item.get('brand', '')))
                    
                    data.append(item)
                
                # 批量查询库存和采购历史
                if data:
                    stock_map = CompareDataService._batch_get_stock_quantity(cursor, oe_brand_list, company)
                    purchase_map = CompareDataService._batch_get_purchase_history(cursor, oe_brand_list, company)
                    
                    # 将查询结果添加到数据中
                    for item in data:
                        key = (item.get('oe', ''), item.get('brand', ''))
                        item['stock_quantity'] = stock_map.get(key, 0)
                        item['has_purchase_history'] = purchase_map.get(key, False)
                
                return data, total
                
        except Exception as e:
            print(f"查询 replace_number 差异数据时出错: {str(e)}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def _batch_get_stock_quantity(cursor, oe_brand_list: List[Tuple[str, str]], company: str) -> Dict[Tuple[str, str], int]:
        """
        批量查询库存数量
        
        参数:
            cursor: 数据库游标
            oe_brand_list: OE和品牌元组列表 [(oe, brand), ...]
            company: 公司代码
            
        返回:
            字典 {(oe, brand): stock_quantity}
        """
        if not oe_brand_list:
            return {}
        
        # 去重
        unique_pairs = list(set(oe_brand_list))
        
        result = {}
        # 分批查询，避免SQL过长
        batch_size = 500
        for i in range(0, len(unique_pairs), batch_size):
            batch = unique_pairs[i:i + batch_size]
            
            # 构建OR条件
            or_conditions = []
            params = [company]
            for oe, brand in batch:
                if oe and brand:
                    or_conditions.append("(number = %s AND brand_name = %s)")
                    params.extend([oe, brand])
            
            if not or_conditions:
                continue
            
            sql = f"""
                SELECT number, brand_name, SUM(stock_quantity) as total_stock
                FROM crmapp_inventory_detail
                WHERE company = %s AND ({' OR '.join(or_conditions)})
                GROUP BY number, brand_name
            """
            
            try:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                for row in rows:
                    key = (row[0], row[1])
                    result[key] = int(row[2]) if row[2] else 0
            except Exception as e:
                print(f"查询库存失败: {e}")
        
        return result
    
    @staticmethod
    def _batch_get_purchase_history(cursor, oe_brand_list: List[Tuple[str, str]], company: str) -> Dict[Tuple[str, str], bool]:
        """
        批量查询是否有采购历史
        
        参数:
            cursor: 数据库游标
            oe_brand_list: OE和品牌元组列表 [(oe, brand), ...]
            company: 公司代码
            
        返回:
            字典 {(oe, brand): True/False}
        """
        if not oe_brand_list:
            return {}
        
        # 去重
        unique_pairs = list(set(oe_brand_list))
        
        result = {}
        # 分批查询
        batch_size = 500
        for i in range(0, len(unique_pairs), batch_size):
            batch = unique_pairs[i:i + batch_size]
            
            # 构建OR条件
            or_conditions = []
            params = [company]
            for oe, brand in batch:
                if oe and brand:
                    or_conditions.append("(number = %s AND brand = %s)")
                    params.extend([oe, brand])
            
            if not or_conditions:
                continue
            
            sql = f"""
                SELECT DISTINCT number, brand
                FROM crmapp_procurement_history_detail
                WHERE company = %s AND ({' OR '.join(or_conditions)})
                LIMIT 10000
            """
            
            try:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                for row in rows:
                    key = (row[0], row[1])
                    result[key] = True
            except Exception as e:
                print(f"查询采购历史失败: {e}")
        
        # 对于没有查询到的，设置为False
        for oe, brand in unique_pairs:
            key = (oe, brand)
            if key not in result:
                result[key] = False
        
        return result


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


def get_oe_with_different_replace_numbers(
    oe: str = '',
    brand: str = '',
    product_name: str = '',
    vehicle_brand: str = '',
    company: str = '',
    page: int = 1,
    limit: int = 100
) -> Tuple[List[Dict], int]:
    """
    查询 replace_number 有差异的 OE 分组数据
    
    逻辑：
    1. 按 oe 分组，收集所有 brand 和 replace_number
    2. 检查每个 oe 下的 replace_number 是否有差异（去重后数量>1）
    3. 只返回有差异的 oe 分组数据（该 oe 下的所有 brand 都展示）
    
    参数:
        oe: OE号筛选
        brand: 品牌筛选
        product_name: 产品名称筛选
        vehicle_brand: 车辆品牌筛选
        company: 公司/组织筛选
        page: 页码
        limit: 每页条数
        
    返回:
        (数据列表, 总记录数)
        数据列表格式: [{oe, brand, replace_number, replace_number_with_keys, product_name, ...}, ...]
    """
    return CompareDataService.get_oe_with_different_replace_numbers(
        oe=oe, brand=brand, product_name=product_name, 
        vehicle_brand=vehicle_brand, company=company,
        page=page, limit=limit
    )
