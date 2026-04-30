import requests
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# 从统一的数据库连接模块导入 - 使用 DBCursorContext 上下文管理器
from app.utils.database_connection import db_cursor, get_db_connection

# CRM开单接口地址
CRM_API_URL = "http://113.45.176.129:8001/ks_kaidan_api"


def filter_unprocessed_orders(order_ids):
    """
    根据订单ID列表，过滤出需要处理的订单（即CRM状态不是'已自动开单'或'开单失败'或不存在的订单）
    
    参数:
        order_ids: 待处理订单ID列表
    
    返回:
        list: 需要发送到CRM的订单ID列表
    
    说明:
        - '已自动开单'：成功处理的订单，不需要再次处理
        - '开单失败'：已经尝试过但失败的订单，不再重复尝试，避免无限循环
    """
    if not order_ids:
        return []
    
    try:
        # 使用 DBCursorContext 上下文管理器，自动管理连接和事务
        # dict_cursor=True 表示使用字典游标，可以通过列名访问数据
        with db_cursor(dict_cursor=True) as cursor:
            # 计算一周前的时间（从当前时间往前一周）
            one_week_ago = datetime.now() - timedelta(days=7)
            one_week_ago_str = one_week_ago.strftime('%Y-%m-%d %H:%M:%S')
            
            # 构建SQL查询，获取一周内且在提供的订单ID列表中的记录
            placeholders = ','.join(['%s'] * len(order_ids))
            sql = f"""
            SELECT `开思订单号`, `crm订单状态` 
            FROM crmapp_ks_auto_bill 
            WHERE `日期` >= %s 
            AND `开思订单号` IN ({placeholders})
            """
            
            params = [one_week_ago_str] + order_ids
            cursor.execute(sql, params)
            results = cursor.fetchall()
            
            # 使用集合优化：将已处理的订单ID存储到集合中，方便O(1)时间复杂度查找
            # 已处理包括：成功开单 和 开单失败的订单（避免失败订单无限重试）
            processed_orders_set = set()
            for row in results:
                if row['crm订单状态'] in ('已自动开单', '开单失败'):
                    processed_orders_set.add(row['开思订单号'])
            
            # 过滤出需要处理的订单ID
            unprocessed_orders = []
            for order_id in order_ids:
                # 如果订单不在已处理集合中，则需要处理
                if order_id not in processed_orders_set:
                    unprocessed_orders.append(order_id)
            
            return unprocessed_orders
            
    except Exception as e:
        print(f"         ✗ 数据库操作出错: {str(e)}")
        return []


def save_order_result_to_db(order_id, result_data, connection=None, status='已自动开单'):
    """
    将订单结果保存到数据库中
    
    参数:
        order_id: 开思订单号
        result_data: 接口返回的数据
        connection: 可选的数据库连接对象，若为None则创建新连接
        status: 订单状态，默认为'已自动开单'，失败时传入'开单失败'
    """
    # 提取所需字段
    crm_order_number = ''
    crm_order_url = ''
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')

    # 如果有返回数据且status为'已自动开单'，则提取数据
    if result_data and status == '已自动开单':
        crm_order_number = result_data.get('orderNumber', '')
        crm_order_url = result_data.get('url', '')

    try:
        # 使用 db_cursor 上下文管理器，自动管理连接和事务
        # 如果传入了外部连接，则使用外部连接；否则自动创建新连接
        with db_cursor(dict_cursor=False, connection=connection) as cursor:
            sql = """
            UPDATE crmapp_ks_auto_bill 
            SET `crm订单号`=%s, `crm订单链接`=%s, `crm订单状态`=%s, `开单时间`=%s
            WHERE `开思订单号` = %s
            """
            cursor.execute(sql, (crm_order_number, crm_order_url, status, current_time, order_id))
            
            # 检查是否有更新记录，如果没有则插入新记录
            if cursor.rowcount == 0:
                insert_sql = """
                INSERT INTO crmapp_ks_auto_bill (`开思订单号`, `crm订单号`, `crm订单链接`, `crm订单状态`, `开单时间`) 
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_sql, (order_id, crm_order_number, crm_order_url, status, current_time))
                
        print(f"         ✓ 订单 {order_id} 信息已保存到数据库")
    except Exception as e:
        print(f"         ✗ 保存订单 {order_id} 到数据库失败: {str(e)}")


def send_order_to_crm(order_id, connection=None):
    """
    发送单个订单号到CRM开单接口
    
    参数:
        order_id: 开思订单号（如 "S2602210009009"）
        connection: 可选的数据库连接对象，若为None则创建新连接
    
    返回:
        dict: 接口返回的响应数据
        None: 请求失败
    """
    # 由于订单是从数据库查询出来的（满足特定条件），直接发送请求，不再检查状态
    print(f"         ✓ 订单 {order_id} 符合处理条件，发送到CRM系统")
    
    payload = {'orders_no': order_id}
    headers = {}
    
    response = requests.request("POST", CRM_API_URL, headers=headers, data=payload)
    
    # 尝试解析JSON
    data = json.loads(response.text)
    print(f"         响应: {json.dumps(data, ensure_ascii=False)}")
    
    # 保存订单结果到数据库
    save_order_result_to_db(order_id, data, connection)
    
    return data


def send_orders_to_crm(order_ids, connection=None):
    """
    批量发送订单号列表到CRM开单接口
    
    参数:
        order_ids: 订单号列表
        connection: 可选的数据库连接对象，若为None则创建新连接
    
    返回:
        list: 每个订单的响应结果列表
    """
    if not order_ids:
        print("⚠️ 订单号列表为空")
        return []
    
    # 过滤出需要处理的订单
    print(f"\n【过滤】正在过滤需要处理的订单...")
    unprocessed_orders = filter_unprocessed_orders(order_ids)
    
    if not unprocessed_orders:
        print("【过滤】所有订单都已处理过，无需发送请求")
        return []
    
    unprocessed_count = len(unprocessed_orders)
    skipped_count = len(order_ids) - unprocessed_count
    print(f"【过滤】发现 {skipped_count} 个已处理订单，{unprocessed_count} 个待处理订单")
    
    # 如果没有提供连接，则创建一个
    local_connection = connection is None
    conn = connection or get_db_connection()
    
    results = []
    print(f"\n【CRM】开始发送 {len(unprocessed_orders)} 条订单到CRM系统\n")
    
    try:
        for i, order_id in enumerate(unprocessed_orders, 1):
            print(f"【CRM】[{i}/{len(unprocessed_orders)}] 发送订单: {order_id}")
            result = send_order_to_crm(order_id, conn)
            
            if result and not (isinstance(result, dict) and result.get("skipped")):
                results.append({"order_id": order_id, "result": result})
            elif isinstance(result, dict) and result.get("skipped"):
                print(f"         ⚠ 跳过订单 {order_id}，不计入结果")
            else:
                print(f"         ✗ 请求失败")
                results.append({"order_id": order_id, "result": None})
        
        print(f"\n【CRM】✓ 全部发送完成")
    finally:
        # 如果是本地创建的连接，则关闭它
        if local_connection:
            conn.close()
    
    return results
