"""
开思订单自动开单系统 - 主程序

功能:
    1. 登录开思平台
    2. 获取符合条件的订单（等待商家确认）
    3. 批量发送到CRM开单接口
    4. 循环运行（每分钟一次）
    5. 登录过期后自动重新登录

使用:
    python main.py

文件说明:
    - ks_login.py: 登录模块
    - ks_orders.py: 订单获取模块
    - crm_auto_bill.py: CRM开单接口模块
    - main.py: 主程序入口

修改说明:
    - 添加信号处理，支持优雅退出
    - 添加全局退出标志，避免强制终止导致内存损坏
"""

import time
from pathlib import Path
import pymysql
import sys
import os
import signal
from datetime import datetime
import threading
import queue

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

# 全局退出标志，用于优雅退出
_should_exit = False
_exit_event = threading.Event()


def signal_handler(signum, frame):
    """
    信号处理函数
    当收到 SIGTERM 或 SIGINT 信号时，设置退出标志
    """
    global _should_exit
    signal_name = signal.Signals(signum).name
    print(f"\n[{datetime.now()}] [开思自动开单] 收到信号 {signal_name}({signum})，准备优雅退出...")
    _should_exit = True
    _exit_event.set()  # 唤醒正在等待的线程


# 注册信号处理器
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

from app.ks_auto_bill.ks_login import login
from app.ks_auto_bill.ks_orders import get_orders, extract_and_save_order_info
from app.ks_auto_bill.crm_auto_bill import send_orders_to_crm
from app.utils.database_connection import get_db_connection


def init_database_table():
    """初始化数据库表，检查是否存在crmapp_ks_auto_bill表，不存在则创建"""
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor: 
            # 检查表是否已存在
            check_table_sql = """
            SELECT COUNT(*) AS count 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'crmapp_ks_auto_bill'
            """
            cursor.execute(check_table_sql)
            result = cursor.fetchone()
            
            if result['count'] == 0:
                # 创建表
                create_table_sql = """
                CREATE TABLE crmapp_ks_auto_bill (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    日期 DATETIME,
                    开思订单号 VARCHAR(255),
                    crm订单号 VARCHAR(255),
                    crm订单链接 VARCHAR(500),
                    客户 VARCHAR(255),
                    执行日志 VARCHAR(255),
                    crm订单状态 VARCHAR(100),
                    开单时间 DATETIME,
                    数量 INT DEFAULT NULL,
                    金额 DECIMAL(10,2) DEFAULT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
                cursor.execute(create_table_sql)
                print("[OK] 成功创建表 crmapp_ks_auto_bill")
                
                # 为所有字段添加索引
                create_index_date = "CREATE INDEX idx_date ON crmapp_ks_auto_bill(日期);"
                create_index_kaisi_order = "CREATE INDEX idx_kaisi_order ON crmapp_ks_auto_bill(开思订单号);"
                create_index_crm_order = "CREATE INDEX idx_crm_order ON crmapp_ks_auto_bill(crm订单号);"
                create_index_crm_link = "CREATE INDEX idx_crm_link ON crmapp_ks_auto_bill(crm订单链接);"
                create_index_customer = "CREATE INDEX idx_customer ON crmapp_ks_auto_bill(客户);"
                create_index_log = "CREATE INDEX idx_log ON crmapp_ks_auto_bill(执行日志);"
                create_index_status = "CREATE INDEX idx_status ON crmapp_ks_auto_bill(crm订单状态);"
                create_index_submit_time = "CREATE INDEX idx_submit_time ON crmapp_ks_auto_bill(开单时间);"
                create_index_quantity = "CREATE INDEX idx_quantity ON crmapp_ks_auto_bill(数量);"
                create_index_amount = "CREATE INDEX idx_amount ON crmapp_ks_auto_bill(金额);"
                
                cursor.execute(create_index_date)
                print("[OK] 为 日期 字段创建索引完成")
                cursor.execute(create_index_kaisi_order)
                print("[OK] 为 开思订单号 字段创建索引完成")
                cursor.execute(create_index_crm_order)
                print("[OK] 为 crm订单号 字段创建索引完成")
                cursor.execute(create_index_crm_link)
                print("[OK] 为 crm订单链接 字段创建索引完成")
                cursor.execute(create_index_customer)
                print("[OK] 为 客户 字段创建索引完成")
                cursor.execute(create_index_log)
                print("[OK] 为 执行日志 字段创建索引完成")
                cursor.execute(create_index_status)
                print("[OK] 为 crm订单状态 字段创建索引完成")
                cursor.execute(create_index_submit_time)
                print("[OK] 为 开单时间 字段创建索引完成")
                cursor.execute(create_index_quantity)
                print("[OK] 为 数量 字段创建索引完成")
                cursor.execute(create_index_amount)
                print("[OK] 为 金额 字段创建索引完成")
            else:
                print("[OK] 表 crmapp_ks_auto_bill 已存在，正在检查是否需要添加额外字段...")
                
                # 检查并添加'客户'、'数量'、'金额'字段（如果不存在）
                columns_to_check = [
                    ('客户', 'VARCHAR(255)', '开思订单号'),  # 在开思订单号之后
                    ('数量', 'INT DEFAULT NULL', '开单时间'),  # 在开单时间之后
                    ('金额', 'DECIMAL(10,2) DEFAULT NULL', '数量')  # 在数量之后
                ]
                
                for col_name, col_type, after_col in columns_to_check:
                    # 检查表中是否已存在该字段
                    check_column_sql = f"""
                    SELECT COUNT(*) AS count
                    FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                    AND table_name = 'crmapp_ks_auto_bill'
                    AND column_name = '{col_name}'
                    """
                    cursor.execute(check_column_sql)
                    column_exists = cursor.fetchone()['count']
                    
                    if column_exists == 0:
                        # 添加字段
                        alter_table_sql = f"ALTER TABLE crmapp_ks_auto_bill ADD COLUMN `{col_name}` {col_type} AFTER `{after_col}`"
                        cursor.execute(alter_table_sql)
                        print(f"[OK] 已成功为表 crmapp_ks_auto_bill 添加'{col_name}'字段")
                        
                        # 为新字段创建索引
                        create_index_sql = f"CREATE INDEX idx_{col_name} ON crmapp_ks_auto_bill(`{col_name}`);"
                        cursor.execute(create_index_sql)
                        print(f"[OK] 已成功为'{col_name}'字段创建索引")
                    else:
                        pass
                
        connection.commit()
    except Exception as e:
        print(f"[ERROR] 初始化数据库表时出错: {str(e)}")
        connection.rollback()
    finally:
        connection.close()


def check_login_status(session):
    """
    检查登录状态是否有效
    
    参数:
        session: 当前会话对象
    
    返回:
        bool: True 表示登录有效，False 表示已过期
    
    说明:
        通过尝试访问订单接口来判断登录是否过期
    """
    if session is None:
        return False
    
    try:
        result = get_orders(session, page_num=1, page_size=1)
        if result and result.get("code") == 200:
            return True
        else:
            return False
    except Exception:
        return False


def is_running_time():
    """
    检查当前时间是否在运行时间段内（早上7点到晚上24点）
    
    返回:
        bool: True 表示在运行时间段内，False 表示不在
    """
    current_hour = datetime.now().hour
    return 7 <= current_hour < 24


def process_order_batch(pending_confirmation_orders):
    """
    处理一批订单
    
    参数:
        pending_confirmation_orders: 待处理订单列表
    
    返回:
        处理结果
    """
    if not pending_confirmation_orders:
        print("[WARN] 没有待处理的订单")
        return
        
    print(f"[OK] 获取到 {len(pending_confirmation_orders)} 条待处理订单")
    
    # 发送订单到CRM
    results = send_orders_to_crm(pending_confirmation_orders)
    
    # 统计结果
    success_count = sum(1 for r in results if r.get("result") is not None)
    print(f"\n【统计】成功: {success_count}/{len(results)}")


def order_processing_worker(order_queue):
    """
    订单处理工作线程函数
    持续监听队列，只要有订单就立即处理
    
    修改：添加退出标志检查，支持优雅退出
    """
    global _should_exit
    print("[开单模块] 订单处理工作线程已启动")
    
    while not _should_exit:
        try:
            # 从队列中获取订单批次，添加超时以便检查退出标志
            batch = order_queue.get(timeout=1)
            
            # 如果获取到None，则表示需要退出线程
            if batch is None:
                print("[开单模块] 收到退出信号，处理线程即将退出")
                order_queue.task_done()
                break
            
            print(f"[开单模块] 开始处理队列中的订单批次，包含 {len(batch)} 个订单...")
            process_order_batch(batch)
            
            # 标记任务已完成
            order_queue.task_done()
            
            # 短暂休眠，确保系统资源释放
            time.sleep(1)
            
        except queue.Empty:
            # 队列为空，继续循环（检查退出标志）
            continue
        except Exception as e:
            print(f"[开单模块] 处理订单时出错: {e}")
            continue
    
    print("[开单模块] 订单处理工作线程已退出")


def main():
    """
    主函数：执行完整的自动开单流程（循环运行）
    
    流程:
        1. 登录开思平台
        2. 检查登录状态（过期则重新登录）
        3. 检查是否在运行时间内
        4. 获取开思订单并保存到数据库
        5. 将待处理订单加入队列
        6. 等待1分钟后循环或直到非运行时间
    
    修改：添加退出标志检查，支持优雅退出
    """
    global _should_exit
    
    print("=" * 60)
    print("开思订单自动开单系统（循环模式）")
    print("=" * 60)
    print(f"[主进程] PID: {os.getpid()}")
    
    # 在程序启动时检查并创建数据库表
    print("【初始化】正在检查数据库表...")
    init_database_table()
    print("【初始化】数据库表检查完成")
    
    session = None
    
    # 创建订单队列
    order_queue = queue.Queue()
    
    # 启动订单处理工作线程
    processing_thread = threading.Thread(target=order_processing_worker, args=(order_queue,))
    processing_thread.start()
    
    print(f"[爬取模块] 系统启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        while not _should_exit:
            current_time = datetime.now()
            
            # 检查是否在运行时间内
            if not is_running_time():
                print(f"\n[爬取模块] 当前时间 {current_time.hour} 点，不在运行时间段内，等待至运行时间...")
                
                # 等待直到进入运行时间，但每秒检查退出标志
                while not is_running_time() and not _should_exit:
                    # 使用 _exit_event 等待，可以被信号唤醒
                    _exit_event.wait(timeout=60)
                    current_time = datetime.now()
                    if current_time.hour == 7:  # 如果是早上7点，跳出等待
                        break
                
                if _should_exit:
                    break
                
                print(f"[爬取模块] 进入运行时间段，继续执行...")
            else:
                # 显示当前时间
                print(f"\n{'=' * 60}")
                print(f"[爬取模块] {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'=' * 60}")
                
                # 检查登录状态，过期则重新登录
                print("\n[爬取模块] 检查登录状态...")
                if not check_login_status(session):
                    print("[爬取模块] 登录已过期或未登录，重新登录...")
                    session = login()
                    
                    if session is None:
                        print("[爬取模块] 登录失败，1分钟后重试")
                        # 分段等待，检查退出标志
                        for _ in range(60):
                            if _should_exit:
                                break
                            time.sleep(1)
                        continue
                    
                    print("[爬取模块] 登录成功")
                else:
                    print("[爬取模块] 登录状态有效")
            
            # 获取开思订单并将信息保存到数据库
            print("\n[爬取模块] 获取开思订单并保存到数据库...")
            try:
                # 获取订单信息和待处理订单ID列表
                all_order_info_list, pending_confirmation_orders = extract_and_save_order_info(session)
                print(f"[爬取模块] 成功获取并保存 {len(all_order_info_list)} 条订单信息到数据库")
                print(f"[爬取模块] 找到 {len(pending_confirmation_orders)} 条待处理订单（等待商家确认）")
            except Exception as e:
                print(f"[爬取模块] 获取订单信息失败: {str(e)}")
                # 分段等待，检查退出标志
                for _ in range(60):
                    if _should_exit:
                        break
                    time.sleep(1)
                continue
            
            # 将待处理订单加入队列
            print("\n[爬取模块] 将待处理订单加入队列...")
            if pending_confirmation_orders:
                order_queue.put(pending_confirmation_orders)
                print(f"[爬取模块] 添加 {len(pending_confirmation_orders)} 条订单到处理队列，当前队列中共有 {order_queue.qsize()} 批订单")
            else:
                print("[爬取模块] 没有待处理的订单，跳过添加到队列")
            
            # 等待1分钟后继续爬取，但每秒检查退出标志
            print(f"\n[爬取模块] 1分钟后进行下一次爬取...")
            for _ in range(60):
                if _should_exit:
                    break
                time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n[主进程] 收到键盘中断信号")
    finally:
        # 优雅退出流程
        print("\n" + "=" * 60)
        print("[主进程] 开始优雅退出...")
        print("=" * 60)
        
        # 设置退出标志
        _should_exit = True
        _exit_event.set()
        
        # 发送 None 到队列，通知处理线程退出
        print("[主进程] 通知处理线程退出...")
        order_queue.put(None)
        
        # 等待处理线程完成
        print("[主进程] 等待处理线程完成...")
        processing_thread.join(timeout=30)
        
        if processing_thread.is_alive():
            print("[主进程] 处理线程未在30秒内退出，强制结束")
        else:
            print("[主进程] 处理线程已正常退出")
        
        # 清空队列
        while not order_queue.empty():
            try:
                order_queue.get_nowait()
            except queue.Empty:
                break
        
        print("[主进程] 资源清理完成")
        print(f"[{datetime.now()}] [开思自动开单] 已优雅退出")
        print("=" * 60)


if __name__ == "__main__":
    main()