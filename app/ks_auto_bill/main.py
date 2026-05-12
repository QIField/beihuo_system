"""
开思订单自动开单系统 - 主程序 (多公司版本)

功能:
    1. 登录开思平台 (支持五个公司)
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
    - 支持五个公司：fsbbr, zsbbr, zhbbr, dghf, dgby
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

from app.ks_auto_bill.ks_login import login, COMPANIES
from app.ks_auto_bill.ks_orders import get_orders, extract_and_save_order_info, print_date_range
from app.ks_auto_bill.crm_auto_bill import send_orders_to_crm
from app.utils.database_connection import get_db_connection
from app.utils.database.table_manager import init_ks_auto_bill_table


def init_database_table():
    """初始化数据库表，调用统一的表管理工具"""
    try:
        init_ks_auto_bill_table()
        print("[OK] 成功初始化 crmapp_ks_auto_bill 表")
    except Exception as e:
        print(f"[ERROR] 初始化数据库表时出错: {str(e)}")


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
    """检查是否在运行时间段内（8:30-19:00）"""
    now = datetime.now()
    return (8 <= now.hour < 19) or (now.hour == 8 and now.minute >= 30)


def process_company_orders(company, session, order_queue):
    """
    处理单个公司的订单
    
    参数:
        company: 公司代码
        session: 登录会话
        order_queue: 订单处理队列
    
    返回:
        bool: 是否成功处理
    """
    print(f"\n{'='*60}")
    print(f"[{company}] 开始处理订单")
    print(f"{'='*60}")
    
    try:
        # 打印本次爬取的时间范围（只打印一次）
        print_date_range()
        
        # 获取订单信息和待处理订单ID列表
        all_order_info_list, pending_confirmation_orders = extract_and_save_order_info(session, company=company)
        print(f"[{company}] 成功获取并保存 {len(all_order_info_list)} 条订单信息到数据库")
        print(f"[{company}] 找到 {len(pending_confirmation_orders)} 条待处理订单（等待商家确认）")
        
        # 将待处理订单加入队列
        if pending_confirmation_orders:
            order_queue.put((company, pending_confirmation_orders))
            print(f"[{company}] 添加 {len(pending_confirmation_orders)} 条订单到处理队列")
        else:
            print(f"[{company}] 没有待处理的订单，跳过")
        
        return True
        
    except Exception as e:
        print(f"[{company}] 处理订单时出错: {str(e)}")
        return False


def process_order_batch(company, pending_confirmation_orders):
    """
    处理一批订单
    
    参数:
        company: 公司代码
        pending_confirmation_orders: 待处理订单列表
    
    返回:
        处理结果
    """
    if not pending_confirmation_orders:
        print(f"[{company}] 没有待处理的订单")
        return
        
    print(f"[{company}] 获取到 {len(pending_confirmation_orders)} 条待处理订单")
    
    # 发送订单到CRM
    results = send_orders_to_crm(pending_confirmation_orders, company=company)
    
    # 统计结果
    success_count = sum(1 for r in results if r.get("result") is not None)
    print(f"[{company}] 开单完成: 成功 {success_count}/{len(results)}")


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
            
            company, orders = batch
            print(f"[开单模块] 开始处理 [{company}] 的订单，包含 {len(orders)} 个订单...")
            process_order_batch(company, orders)
            
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


def process_all_companies(order_queue):
    """
    处理所有公司的订单
    
    参数:
        order_queue: 订单处理队列
    
    返回:
        dict: 各公司的处理结果
    """
    results = {}
    
    for company in COMPANIES:
        if _should_exit:
            print(f"[主线程] 收到退出信号，停止处理后续公司")
            break
        
        print(f"\n[主线程] 开始处理 [{company}] ...")
        
        # 登录
        session = None
        for attempt in range(3):
            try:
                session = login(company)
                if session:
                    break
            except Exception as e:
                print(f"[{company}] 登录尝试 {attempt+1} 失败: {e}")
                time.sleep(2)
        
        if session is None:
            print(f"[{company}] 登录失败，跳过该公司")
            results[company] = {'success': False, 'error': '登录失败'}
            continue
        
        # 检查登录状态
        if not check_login_status(session):
            print(f"[{company}] 登录状态无效，跳过该公司")
            results[company] = {'success': False, 'error': '登录状态无效'}
            continue
        
        # 处理订单
        success = process_company_orders(company, session, order_queue)
        results[company] = {'success': success}
        
        # 短暂休眠，避免请求过于频繁
        time.sleep(2)
    
    return results


def main(stop_event=None, heartbeat_func=None):
    """
    主函数：执行完整的自动开单流程（循环运行）

    参数:
        stop_event: 外部传入的停止事件，用于接收停止信号
        heartbeat_func: 外部传入的心跳函数，用于报告任务存活

    流程:
        1. 检查是否在运行时间内
        2. 依次处理五个公司的订单
        3. 等待1分钟后循环或直到非运行时间

    修改：支持外部 stop_event 和 heartbeat_func，支持多公司
    """
    global _should_exit

    # 使用外部传入的 stop_event，如果没有则使用内部的全局变量
    use_external_stop = stop_event is not None

    print("=" * 60)
    print("开思订单自动开单系统（多公司循环模式）")
    print("=" * 60)
    print(f"[主线程] 使用外部停止事件: {use_external_stop}")
    print(f"[主线程] 处理公司列表: {', '.join(COMPANIES)}")

    # 在程序启动时检查并创建数据库表
    print("\n【初始化】正在检查数据库表...")
    init_database_table()
    print("【初始化】数据库表检查完成")

    # 创建订单队列
    order_queue = queue.Queue()

    # 启动订单处理工作线程
    processing_thread = threading.Thread(target=order_processing_worker, args=(order_queue,))
    processing_thread.start()

    print(f"\n[爬取模块] 系统启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def should_stop():
        """检查是否应该停止"""
        if use_external_stop:
            return stop_event.is_set()
        return _should_exit

    def wait_with_stop_check(seconds):
        """等待指定秒数，但每秒检查停止标志"""
        for _ in range(seconds):
            if should_stop():
                return False  # 被中断
            # 报告心跳
            if heartbeat_func:
                heartbeat_func()
            time.sleep(1)
        return True  # 正常完成

    try:
        while not should_stop():
            current_time = datetime.now()

            # 报告心跳
            if heartbeat_func:
                heartbeat_func()

            # 检查是否在运行时间内
            if not is_running_time():
                print(f"\n[爬取模块] 当前时间 {current_time.hour} 点，不在运行时间段内，等待至运行时间...")

                # 等待直到进入运行时间，但每秒检查停止标志
                while not is_running_time() and not should_stop():
                    if heartbeat_func:
                        heartbeat_func()
                    # 使用外部事件或内部事件等待
                    if use_external_stop:
                        stop_event.wait(timeout=60)
                    else:
                        _exit_event.wait(timeout=60)
                    current_time = datetime.now()
                    if current_time.hour == 7:  # 如果是早上7点，跳出等待
                        break

                if should_stop():
                    break

                print(f"[爬取模块] 进入运行时间段，继续执行...")
            else:
                # 显示当前时间
                print(f"\n{'=' * 60}")
                print(f"[爬取模块] {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'=' * 60}")

                # 处理所有公司的订单
                results = process_all_companies(order_queue)
                
                # 打印汇总结果
                print(f"\n{'='*60}")
                print("[汇总] 各公司处理结果:")
                for company, result in results.items():
                    status = "✓ 成功" if result.get('success') else f"✗ 失败 ({result.get('error', '未知错误')})"
                    print(f"  [{company}] {status}")
                print(f"{'='*60}")

            # 等待1分钟后继续爬取，但每秒检查停止标志
            print(f"\n[爬取模块] 1分钟后进行下一次爬取...")
            if not wait_with_stop_check(60):
                break

    except KeyboardInterrupt:
        print("\n[主线程] 收到键盘中断信号")
    finally:
        # 优雅退出流程
        print("\n" + "=" * 60)
        print("[主线程] 开始优雅退出...")
        print("=" * 60)

        # 设置退出标志
        _should_exit = True
        _exit_event.set()

        # 发送 None 到队列，通知处理线程退出
        print("[主线程] 通知处理线程退出...")
        order_queue.put(None)

        # 等待处理线程完成
        print("[主线程] 等待处理线程完成...")
        processing_thread.join(timeout=30)

        if processing_thread.is_alive():
            print("[主线程] 处理线程未在30秒内退出，强制结束")
        else:
            print("[主线程] 处理线程已正常退出")

        # 清空队列
        while not order_queue.empty():
            try:
                order_queue.get_nowait()
            except queue.Empty:
                break

        print("[主线程] 资源清理完成")
        print(f"[{datetime.now()}] [开思自动开单] 已优雅退出")
        print("=" * 60)


if __name__ == "__main__":
    main()
