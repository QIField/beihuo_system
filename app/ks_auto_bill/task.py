"""
开思自动对单 - 简化版任务模块
直接接入统一任务管理器，无需额外的进程/线程管理

核心功能：
1. 单次执行完整开单流程
2. 由统一任务管理器调度（每分钟一次）
3. 自带单实例锁，防止重复执行
4. 异常隔离，不影响主进程
"""

import os
import time
import threading
import queue
import tempfile
from datetime import datetime
from typing import Optional, Tuple, List

# 导入开思自动对单的核心模块
from app.ks_auto_bill.ks_login import login
from app.ks_auto_bill.ks_orders import get_orders, extract_and_save_order_info
from app.ks_auto_bill.crm_auto_bill import send_orders_to_crm
from app.ks_auto_bill.main import (
    init_database_table,
    check_login_status,
    is_running_time
)


# 简单文件锁类（内联定义，避免导入问题）
class SimpleFileLock:
    """简单文件锁，用于防止任务重复执行"""
    
    def __init__(self, lock_name: str, lock_dir: str = None):
        self.lock_name = lock_name
        # 使用系统临时目录（兼容 Windows 和 Linux）
        if lock_dir is None:
            lock_dir = tempfile.gettempdir()
        self.lock_path = os.path.join(lock_dir, f"{lock_name}.lock")
        self._acquired = False
    
    def acquire(self) -> bool:
        """获取锁"""
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            self._acquired = True
            return True
        except FileExistsError:
            return False
        except Exception:
            return False
    
    def release(self):
        """释放锁"""
        if self._acquired:
            try:
                if os.path.exists(self.lock_path):
                    os.unlink(self.lock_path)
                self._acquired = False
            except Exception:
                pass
    
    def __enter__(self):
        return self.acquire()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


# 全局状态：保持登录 session，避免重复登录
_session: Optional[object] = None
_session_lock = threading.Lock()

# 全局状态：记录上次执行时间
_last_run_time: Optional[datetime] = None
_last_run_lock = threading.Lock()

# 单实例锁
_task_lock = SimpleFileLock("ks_auto_bill_task")


def get_session() -> Optional[object]:
    """获取当前 session（线程安全）"""
    with _session_lock:
        return _session


def set_session(session: Optional[object]):
    """设置 session（线程安全）"""
    with _session_lock:
        global _session
        _session = session


def get_last_run_time() -> Optional[datetime]:
    """获取上次执行时间"""
    with _last_run_lock:
        return _last_run_time


def set_last_run_time(t: datetime):
    """设置上次执行时间"""
    with _last_run_lock:
        global _last_run_time
        _last_run_time = t


def process_orders_once():
    """
    单次执行开单流程

    返回: (success: bool, message: str)
    """
    current_time = datetime.now()
    set_last_run_time(current_time)

    print(f"\n{'=' * 60}")
    print(f"[开思自动对单] 开始执行: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")

    # 1. 检查是否在运行时间内（早上7点到晚上24点）
    if not is_running_time():
        print(f"[开思自动对单] 当前时间 {current_time.hour} 点，不在运行时间段内，跳过")
        return True, "不在运行时间段"

    # 2. 初始化数据库表（只在第一次运行时需要）
    try:
        init_database_table()
    except Exception as e:
        print(f"[开思自动对单] 初始化数据库表失败: {e}")

    # 3. 检查登录状态
    session = get_session()
    print("\n[开思自动对单] 检查登录状态...")

    if not check_login_status(session):
        print("[开思自动对单] 登录已过期或未登录，重新登录...")
        session = login()

        if session is None:
            error_msg = "登录失败"
            print(f"[开思自动对单] {error_msg}")
            return False, error_msg

        set_session(session)
        print("[开思自动对单] 登录成功")
    else:
        print("[开思自动对单] 登录状态有效")

    # 4. 获取订单并保存到数据库
    print("\n[开思自动对单] 获取开思订单并保存到数据库...")
    try:
        all_order_info_list, pending_confirmation_orders = extract_and_save_order_info(session)
        print(f"[开思自动对单] 成功获取并保存 {len(all_order_info_list)} 条订单信息")
        print(f"[开思自动对单] 找到 {len(pending_confirmation_orders)} 条待处理订单")
    except Exception as e:
        error_msg = f"获取订单信息失败: {str(e)}"
        print(f"[开思自动对单] {error_msg}")
        return False, error_msg

    # 5. 发送订单到 CRM
    if pending_confirmation_orders:
        print(f"\n[开思自动对单] 开始处理 {len(pending_confirmation_orders)} 条待处理订单...")
        try:
            results = send_orders_to_crm(pending_confirmation_orders)
            success_count = sum(1 for r in results if r.get("result") is not None)
            print(f"[开思自动对单] 处理完成: {success_count}/{len(results)} 成功")
        except Exception as e:
            error_msg = f"发送订单到 CRM 失败: {str(e)}"
            print(f"[开思自动对单] {error_msg}")
            return False, error_msg
    else:
        print("\n[开思自动对单] 没有待处理订单，跳过 CRM 开单")

    print(f"\n[开思自动对单] 执行完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}\n")
    return True, "执行成功"


def ks_auto_bill_task():
    """
    开思自动对单任务（供统一任务管理器调用）

    特点：
    1. 单次执行，不循环（由调度器负责每分钟调用）
    2. 自带单实例锁，防止重复执行
    3. 异常隔离，不影响主进程
    """
    # 1. 获取单实例锁
    if not _task_lock.acquire():
        print("[开思自动对单] 任务已在运行中，跳过本次执行")
        return

    try:
        # 2. 执行任务
        success, message = process_orders_once()

        if not success:
            print(f"[开思自动对单] 任务执行失败: {message}")
        else:
            print(f"[开思自动对单] 任务执行成功")

    except Exception as e:
        # 捕获所有异常，防止传播到主进程
        import traceback
        error_traceback = traceback.format_exc()
        print(f"[开思自动对单] 任务异常（已捕获）: {type(e).__name__}: {str(e)}")
        print(f"[开思自动对单] 堆栈:\n{error_traceback}")

    finally:
        # 3. 释放锁
        _task_lock.release()


def get_ks_auto_bill_task_status() -> dict:
    """
    获取开思自动对单任务状态

    返回: 状态字典
    """
    session = get_session()
    last_run = get_last_run_time()

    return {
        'status': 'ready',
        'type': 'unified_task',
        'session_valid': check_login_status(session) if session else False,
        'last_run_time': last_run.isoformat() if last_run else None,
        'lock_acquired': _task_lock._acquired if hasattr(_task_lock, '_acquired') else False
    }
