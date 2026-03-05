import sys
import os
from datetime import datetime, date

# 添加项目根目录到Python路径，以便导入其他模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.database_connection import get_db_connection


def format_time_only(date_value):
    """
    只返回时间部分，格式为 HH:MM:SS
    """
    if date_value is None:
        return ""
    
    if isinstance(date_value, str):
        # 如果是字符串格式，尝试解析
        try:
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%a, %d %b %Y %H:%M:%S %Z', '%Y-%m-%d']:
                try:
                    parsed_date = datetime.strptime(date_value, fmt)
                    return parsed_date.strftime('%H:%M:%S')
                except ValueError:
                    continue
            # 如果以上格式都不匹配，返回原值
            return date_value
        except:
            return date_value
    
    elif isinstance(date_value, datetime):
        return date_value.strftime('%H:%M:%S')
    
    else:
        try:
            dt = datetime.fromtimestamp(date_value.timestamp())
            return dt.strftime('%H:%M:%S')
        except:
            return str(date_value)


def get_crmapp_ks_auto_bill_data(page=1, page_size=10, target_date_str=None, start_date=None, end_date=None, ks_order_id='', crm_order_id=''):
    """
    根据指定条件查询crmapp_ks_auto_bill表的指定字段数据，支持分页和多种筛选条件
    :param page: 页码，默认为1
    :param page_size: 每页显示的数量，默认为10
    :param target_date_str: 目标日期字符串，格式为 'YYYY-MM-DD'
    :param start_date: 开始日期，格式为 'YYYY-MM-DD'
    :param end_date: 结束日期，格式为 'YYYY-MM-DD'
    :param ks_order_id: 开思订单号搜索条件
    :param crm_order_id: CRM订单号搜索条件
    :return: 查询结果列表
    """
    connection = None
    try:
        connection = get_db_connection()
        
        offset = (page - 1) * page_size
        
        with connection.cursor() as cursor:
            # 查询数据，支持分页和多种筛选条件
            sql = """
            SELECT 
                日期 AS date,
                开思订单号 AS ks_order_id,
                crm订单号 AS crm_order_id,
                crm订单链接 AS crm_order_link,
                执行日志 AS execution_log,
                crm订单状态 AS crm_order_status,
                客户 AS customer,
                数量 AS quantity,
                金额 AS amount
            FROM crmapp_ks_auto_bill 
            WHERE """
            
            params = []
            
            # 如果没有指定日期范围也没有目标日期，查询当天日期的数据
            if not start_date and not end_date and not target_date_str:
                from datetime import datetime
                target_date_str = datetime.now().strftime('%Y-%m-%d')
                sql += "DATE(日期) = %s "
                params.append(target_date_str)
            else:
                # 根据是否有日期范围来构建查询条件
                if start_date and end_date:
                    sql += "DATE(日期) BETWEEN %s AND %s "
                    params.extend([start_date, end_date])
                elif target_date_str:
                    sql += "DATE(日期) = %s "
                    params.append(target_date_str)
                else:
                    # 如果没有指定任何日期，查询所有数据
                    sql += "1=1 "
            
            # 添加订单号搜索条件
            if ks_order_id:
                sql += " AND 开思订单号 LIKE %s"
                params.append(f'%{ks_order_id}%')
                
            if crm_order_id:
                sql += " AND crm订单号 LIKE %s"
                params.append(f'%{crm_order_id}%')
            
            # 添加排序和分页
            sql += " ORDER BY 日期 DESC LIMIT %s OFFSET %s"
            params.extend([page_size, offset])
            
            cursor.execute(sql, params)
            
            # 获取查询结果
            results = cursor.fetchall()
            
            # 处理链接和客户字段
            processed_results = []
            for row in results:
                processed_row = dict(row)
                processed_results.append(processed_row)
            
            return processed_results
    except Exception as e:
        print(f"按条件查询crmapp_ks_auto_bill表数据时发生错误: {e}")
        return []
    finally:
        # 关闭数据库连接
        if connection:
            connection.close()


def get_crmapp_ks_auto_bill_count(target_date_str=None, start_date=None, end_date=None, ks_order_id='', crm_order_id=''):
    """
    根据指定条件获取crmapp_ks_auto_bill表的记录数
    :param target_date_str: 目标日期字符串，格式为 'YYYY-MM-DD'
    :param start_date: 开始日期，格式为 'YYYY-MM-DD'
    :param end_date: 结束日期，格式为 'YYYY-MM-DD'
    :param ks_order_id: 开思订单号搜索条件
    :param crm_order_id: CRM订单号搜索条件
    :return: 记录总数
    """
    connection = None
    try:
        connection = get_db_connection()
        
        with connection.cursor() as cursor:
            # 查询总记录数
            sql = "SELECT COUNT(*) AS total FROM crmapp_ks_auto_bill WHERE "
            
            params = []
            
            # 如果没有指定日期范围也没有目标日期，查询当天日期的数据
            if not start_date and not end_date and not target_date_str:
                from datetime import datetime
                target_date_str = datetime.now().strftime('%Y-%m-%d')
                sql += "DATE(日期) = %s "
                params.append(target_date_str)
            else:
                # 根据是否有日期范围来构建查询条件
                if start_date and end_date:
                    sql += "DATE(日期) BETWEEN %s AND %s "
                    params.extend([start_date, end_date])
                elif target_date_str:
                    sql += "DATE(日期) = %s "
                    params.append(target_date_str)
                else:
                    # 如果没有指定任何日期，查询所有数据
                    sql += "1=1 "
            
            # 添加订单号搜索条件
            if ks_order_id:
                sql += " AND 开思订单号 LIKE %s"
                params.append(f'%{ks_order_id}%')
                
            if crm_order_id:
                sql += " AND crm订单号 LIKE %s"
                params.append(f'%{crm_order_id}%')
            
            cursor.execute(sql, params)
            
            # 获取查询结果
            result = cursor.fetchone()
            
            return result['total'] if result else 0
    except Exception as e:
        print(f"查询crmapp_ks_auto_bill表记录总数时发生错误: {e}")
        return 0
    finally:
        # 关闭数据库连接
        if connection:
            connection.close()