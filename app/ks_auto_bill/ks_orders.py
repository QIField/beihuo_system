from datetime import datetime
import os
import pymysql
from pathlib import Path
from datetime import datetime, timedelta
import requests  # 新增导入request库用于发送HTTP请求
import sys
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from app.utils.audio_player import play_notification_sound
from app.utils.database_connection import get_db_connection


def get_orders(session, status="", page_num=1, page_size=20):
    """
    获取单页订单列表
    
    参数:
        session: 登录后的会话对象
        status: 订单状态ID，默认为空（获取所有状态的订单）
        page_num: 页码，默认 1
        page_size: 每页数量，默认 20
    
    返回:
        dict: 订单接口返回的完整数据（包含 code, data, list 等）
        None: 请求失败
    
    说明:
        - 本地环境（E:\work download\project\BBR）使用固定日期 2026-03-01
        - 其他环境使用最近一周的日期
    """
    if session is None:
        print("✗ session 为空，请先登录")
        return None
    
    # 判断运行环境，设置日期
    current_path = os.getcwd()
    if r"E:\work download\project\BBR" in current_path:
        today = "2026-03-01"
        print(f"【本地环境】使用固定日期: {today}")
        start_date = f"{today} 00:00:00"
        end_date = f"{today} 23:59:59"
    else:
        # 线上环境使用最近一周的日期
        end_date = datetime.now().strftime("%Y-%m-%d") + " 23:59:59"
        start_date = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d") + " 00:00:00"
        print(f"【生产环境】查询日期范围: {start_date} 至 {end_date}")
    
    resp = session.post(
        "https://www.cassmall.com/order-api/order/seller/list",
        json={"orderTimeBegin": start_date, "orderTimeEnd": end_date, "orderStatusId": status, "pageNum": page_num, "pageSize": page_size},
        headers={"Content-Type": "application/json;charset=UTF-8", "Referer": "https://www.cassmall.com/seller"}
    )
    
    if resp.status_code != 200:
        print(f"✗ 请求失败，状态码: {resp.status_code}")
        return None
    
    return resp.json()


def get_all_orders(session, status="", page_size=20):
    """
    获取所有页面的订单（自动分页）
    
    参数:
        session: 登录后的会话对象
        status: 订单状态ID，默认为空（获取所有状态的订单）
        page_size: 每页数量，默认 20
    
    返回:
        list: 所有订单的列表
    
    流程:
        1. 获取第1页，得到总订单数和总页数
        2. 判断是否需要获取更多页
        3. 并发获取剩余页面
        4. 合并所有订单返回
    """
    import concurrent.futures
    import threading
    
    if session is None:
        print("✗ session 为空，请先登录")
        return []
    
    all_orders = []
    
    # 获取第1页
    print("【订单】获取第 1 页...")
    first_result = get_orders(session, status=status, page_num=1, page_size=page_size)
    
    if first_result is None:
        return []
    
    data = first_result.get("data", {})
    total = data.get("total", 0)
    total_pages = (total + page_size - 1) // page_size  # 向上取整
    
    print(f"【订单】总共 {total} 条订单，共 {total_pages} 页")
    
    all_orders.extend(data.get("list", []))
    
    # 只有1页，直接返回
    if total_pages <= 1:
        print("【订单】✓ 只有1页，获取完成")
        return all_orders
    
    # 使用线程池并发获取剩余页面
    max_workers = min(5, total_pages - 1)  # 限制最大线程数，避免过于频繁的请求
    failed_pages = []
    
    def fetch_page(page):
        thread_id = threading.current_thread().ident
        print(f"【订单】线程 {thread_id}: 获取第 {page}/{total_pages} 页...")
        result = get_orders(session, status=status, page_num=page, page_size=page_size)
        if result is None:
            print(f"【订单】线程 {thread_id}: 第 {page} 页获取失败")
            return None
        return result.get("data", {}).get("list", [])
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 创建任务列表
        pages_to_fetch = list(range(2, total_pages + 1))
        futures = {executor.submit(fetch_page, page): page for page in pages_to_fetch}
        
        for future in concurrent.futures.as_completed(futures):
            page = futures[future]
            try:
                orders_list = future.result()
                if orders_list is not None:
                    all_orders.extend(orders_list)
                else:
                    failed_pages.append(page)
            except Exception as exc:
                print(f"✗ 页面 {page} 获取时发生异常: {exc}")
                failed_pages.append(page)
    
    # 如果有失败的页面，尝试重新获取
    if failed_pages:
        print(f"【订单】正在重试 {len(failed_pages)} 个失败的页面...")
        for page in failed_pages[:]:  # 使用副本迭代，因为可能修改原列表
            result = get_orders(session, status=status, page_num=page, page_size=page_size)
            if result is not None:
                orders_list = result.get("data", {}).get("list", [])
                all_orders.extend(orders_list)
                failed_pages.remove(page)
    
    if failed_pages:
        print(f"✗ 最终仍有 {len(failed_pages)} 个页面获取失败: {failed_pages}")
    
    print(f"【订单】✓ 全部获取完成，共 {len(all_orders)} 条订单")
    return all_orders

def extract_order_info(session, status=""):
    """
    获取所有订单并提取订单ID、状态描述和日期
    
    参数:
        session: 登录后的会话对象
        status: 订单状态ID，默认为空（获取所有状态的订单）
    
    返回:
        list: 包含字典的列表，每个字典有 'orderId' 和 'orderStatusDesc' 两个键
    
    说明:
        - 自动调用 get_all_orders 获取所有订单
        - 提取每个订单的 orderId、orderStatusDesc 和 orderDate 字段
    """
    orders = get_all_orders(session, status=status)
    order_info_list = []
    
    for order in orders:
        order_id = order.get('orderId')
        status_desc = order.get('orderStatusDesc')
        order_date = order.get('orderDate')
        buyer_company_name = order.get('buyerCompanyName')  
        
        order_info = {
            'orderId': order_id,
            'orderStatusDesc': status_desc,
            'orderDate': order_date,
            'buyerCompanyName': buyer_company_name 
        }
        order_info_list.append(order_info)
    
    return order_info_list


def save_order_info_to_db(order_info_list, order_details_map=None):
    """
    将订单信息保存到数据库，如果订单号已存在则检查其他字段是否不同，不同则更新，相同则跳过；不存在的订单则插入新数据
    
    参数:
        order_info_list: 订单信息列表，每个元素包含 'orderId', 'orderStatusDesc', 'orderDate'
        order_details_map: 订单详情映射，key为订单号，value为包含数量和金额的字典（可选）
    
    优化说明:
        - 批量查询现有记录，减少数据库交互次数
        - 分类处理：收集需要插入和更新的记录
        - 使用 executemany 进行批量操作
        - 统一提交事务，提高性能
    """
    if not order_info_list:
        print("没有订单信息需要保存")
        return
    
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:  # 修改为使用DictCursor
            # 首先获取所有现有的订单号及其相关信息
            order_ids = [info['orderId'] for info in order_info_list]
            placeholders = ','.join(['%s'] * len(order_ids))
            
            select_sql = f"""
            SELECT `开思订单号`, `日期`, `执行日志`, `客户` 
            FROM crmapp_ks_auto_bill 
            WHERE `开思订单号` IN ({placeholders})
            """
            cursor.execute(select_sql, order_ids)
            existing_records = cursor.fetchall()
            
            # 将现有记录转换为以订单号为键的字典，便于快速查找
            existing_dict = {record['开思订单号']: record for record in existing_records}
            
            # 分类订单：需要插入的、需要更新的、以及相同的（跳过的）
            to_insert = []
            to_update = []
            
            for info in order_info_list:
                order_id = info['orderId']
                order_date = info['orderDate']
                order_status_desc = info['orderStatusDesc']
                buyer_company_name = info.get('buyerCompanyName', '')  # 获取买家公司名称
                
                if order_id in existing_dict:
                    # 订单已存在，检查字段是否不同
                    existing_record = existing_dict[order_id]
                    existing_date = existing_record['日期']
                    existing_log = existing_record['执行日志']
                    existing_customer = existing_record.get('客户', '')
                    
                    # 处理日期比较，兼容datetime对象和字符串
                    if hasattr(existing_date, 'strftime'):
                        formatted_existing_date = existing_date.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        formatted_existing_date = str(existing_date) if existing_date else None
                        
                    if hasattr(order_date, 'strftime'):
                        formatted_new_date = order_date.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        formatted_new_date = str(order_date) if order_date else None
                    
                    # 检查日期、日志或客户信息是否不同
                    if (formatted_existing_date != formatted_new_date or 
                        existing_log != order_status_desc or 
                        existing_customer != buyer_company_name):
                        # 字段不同，需要更新
                        to_update.append((order_date, order_status_desc, buyer_company_name, order_id))
                    else:
                        # 字段相同，跳过
                        pass
                else:
                    # 订单不存在，需要插入
                    if order_details_map and order_id in order_details_map:
                        # 如果提供了详情映射且当前订单有详情，则使用详情数据
                        detail = order_details_map[order_id]
                        quantity = detail.get('total_quantity', None)
                        amount = detail.get('total_amount', None)
                        to_insert.append((order_date, order_id, order_status_desc, buyer_company_name, quantity, amount))
                    else:
                        # 不包含数量和金额字段的插入
                        to_insert.append((order_date, order_id, order_status_desc, buyer_company_name))
            
            # 批量插入新订单
            inserted_count = 0
            if to_insert:
                # 检查是否包含数量和金额字段
                if to_insert and len(to_insert[0]) == 6:  # 包含数量和金额
                    insert_sql = """
                    INSERT INTO crmapp_ks_auto_bill (`日期`, `开思订单号`, `执行日志`, `客户`, `数量`, `金额`)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
                else:  # 不包含数量和金额
                    insert_sql = """
                    INSERT INTO crmapp_ks_auto_bill (`日期`, `开思订单号`, `执行日志`, `客户`)
                    VALUES (%s, %s, %s, %s)
                    """
                cursor.executemany(insert_sql, to_insert)
                inserted_count = len(to_insert)
            
            # 批量更新已存在的订单
            updated_count = 0
            if to_update:
                update_sql = """
                UPDATE crmapp_ks_auto_bill 
                SET `日期` = %s, `执行日志` = %s, `客户` = %s
                WHERE `开思订单号` = %s
                """
                cursor.executemany(update_sql, to_update)
                updated_count = len(to_update)
            
            connection.commit()
            
            total_processed = len(order_info_list)
            skipped_count = total_processed - inserted_count - updated_count
            
            print(f"✓ 数据库批量操作完成: {inserted_count} 条新增, {updated_count} 条更新, {skipped_count} 条跳过")
            
            # 如果有新订单插入，播放提示音
            if inserted_count > 0:
                print(f"检测到 {inserted_count} 个新订单，播放提示音...")
                play_notification_sound("new_order_sound.wav")
                
    except Exception as e:
        print(f"✗ 保存订单信息到数据库时出错: {str(e)}")
        connection.rollback()
    finally:
        connection.close()


def get_order_details(session, order_id):
    """
    获取指定订单的详细信息，包括商品数量和金额信息
    
    参数:
        session: 登录后的会话对象
        order_id: 订单ID，如 S2602110010348
    
    返回:
        dict: 包含订单详情中计算出的总量和总金额
              {'total_quantity': int, 'total_amount': float}
    """
    if session is None:
        print("✗ session 为空，请先登录")
        return None

    url = f"https://www.cassmall.com/orders/seller/order/{order_id}/shipgroups"
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/json;charset=UTF-8", 
        "Referer": f"https://www.cassmall.com/orders/seller/order/detail/{order_id}",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        response = session.get(url, headers=headers)
        if response.status_code != 200:
            print(f"✗ 请求失败，状态码: {response.status_code}, 订单号: {order_id}")
            return None

        data = response.json()

        total_quantity = 0
        total_amount = 0.0

        # 遍历响应数据中的items数组
        if 'data' in data and isinstance(data['data'], list):
            for ship_group in data['data']:
                if 'items' in ship_group and isinstance(ship_group['items'], list):
                    for item in ship_group['items']:
                        # 提取quantity和orderItemPayment.buyerActualAmount
                        quantity = item.get('quantity', 0)
                        
                        # 从orderItemPayment中提取buyerActualAmount
                        payment_info = item.get('orderItemPayment', {})
                        amount = payment_info.get('buyerActualAmount', 0.0)
                        
                        total_quantity += quantity
                        total_amount += amount

        # 格式化金额为两位小数
        total_amount = round(total_amount, 2)

        print(f"订单 {order_id} 详情: 总数量={total_quantity}, 总金额={total_amount}")

        return {
            'total_quantity': total_quantity,
            'total_amount': total_amount
        }

    except requests.exceptions.RequestException as e:
        print(f"✗ 获取订单详情时网络请求异常: {str(e)}, 订单号: {order_id}")
        return None
    except Exception as e:
        print(f"✗ 解析订单详情时发生错误: {str(e)}, 订单号: {order_id}")
        return None


def extract_and_save_order_info(session, status=""):
    """
    获取订单信息、保存到数据库，并对新增的订单获取详细信息
    
    参数:
        session: 登录后的会话对象
        status: 订单状态ID，默认为空（获取所有状态的订单）
    
    返回:
        tuple: (所有订单信息列表, 状态为'等待商家确认'的订单ID列表)
    """
    order_info_list = extract_order_info(session, status)
    
    # 获取当前数据库中的订单号列表
    connection = get_db_connection()
    existing_order_ids = set()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:  # 修改为使用DictCursor
            select_sql = "SELECT `开思订单号` FROM crmapp_ks_auto_bill"
            cursor.execute(select_sql)
            existing_records = cursor.fetchall()
            existing_order_ids = {record['开思订单号'] for record in existing_records}
    except Exception as e:
        print(f"✗ 查询现有订单号时出错: {str(e)}")
    finally:
        connection.close()
    
    # 筛选新增的订单
    new_order_info_list = [info for info in order_info_list if info['orderId'] not in existing_order_ids]
    print(f"发现 {len(new_order_info_list)} 个新订单需要获取详情")
    
    # 获取新订单的详细信息
    order_details_map = {}
    for order_info in new_order_info_list:
        order_id = order_info['orderId']
        print(f"正在获取新订单 {order_id} 的详细信息...")
        order_details = get_order_details(session, order_id)
        if order_details:
            order_details_map[order_id] = order_details
            print(f"订单 {order_id} 详情获取成功: 数量={order_details['total_quantity']}, 金额={order_details['total_amount']}")
        else:
            print(f"订单 {order_id} 详情获取失败")
    
    # 保存订单信息到数据库（包括新订单的详情）
    save_order_info_to_db(order_info_list, order_details_map)
    
    # 筛选出状态为'等待商家确认'的订单ID
    pending_confirmation_orders = [
        info['orderId'] for info in order_info_list 
        if info.get('orderStatusDesc') == '等待商家确认'
    ]
    
    return order_info_list, pending_confirmation_orders

