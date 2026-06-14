"""
开思自动对单 - 简化版任务模块 (多公司版本)
直接接入统一任务管理器，无需额外的进程/线程管理

核心功能：
1. 单次执行完整开单流程（处理五个公司）
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
from app.ks_auto_bill.ks_login import login, COMPANIES
from app.ks_auto_bill.ks_orders import get_orders, extract_and_save_order_info, print_date_range
from app.ks_auto_bill.crm_auto_bill import send_orders_to_crm
from app.utils.ks_auto_bill_model import COMPANY_CONFIG
from app.utils.common_util_module.server_push import message_push


# 简单文件锁类（内联定义，避免导入问题）
class SimpleFileLock:
    """
    简单文件锁，用于防止任务重复执行
    
    特性：
    1. 支持 PID 检测 - 如果锁文件中的进程已不存在，自动清理僵尸锁
    2. 支持超时机制 - 锁文件超过指定时间自动视为失效（默认10分钟）
    """
    
    def __init__(self, lock_name: str, lock_dir: str = None, timeout_seconds: int = 600):
        self.lock_name = lock_name
        self.timeout_seconds = timeout_seconds  # 锁超时时间，默认10分钟
        # 使用系统临时目录（兼容 Windows 和 Linux）
        if lock_dir is None:
            lock_dir = tempfile.gettempdir()
        self.lock_path = os.path.join(lock_dir, f"{lock_name}.lock")
        self._acquired = False
    
    def _is_process_running(self, pid: int) -> bool:
        """检查指定 PID 的进程是否仍在运行"""
        try:
            if os.name == 'nt':  # Windows
                import ctypes
                kernel32 = ctypes.windll.kernel32
                # 使用 PROCESS_QUERY_INFORMATION (0x0400) 权限，更可靠地查询进程状态
                # 替代原来的 PROCESS_TERMINATE (1)，避免权限不足导致误判
                PROCESS_QUERY_INFORMATION = 0x0400
                handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
                return False
            else:  # Linux/Mac
                os.kill(pid, 0)
                return True
        except (OSError, ImportError):
            return False
    
    def _is_lock_expired(self) -> bool:
        """检查锁是否已过期（超时）"""
        try:
            stat = os.stat(self.lock_path)
            file_age = time.time() - stat.st_mtime
            return file_age > self.timeout_seconds
        except Exception:
            return True  # 如果无法获取文件信息，视为已过期
    
    def _read_lock_pid(self) -> int:
        """读取锁文件中的 PID"""
        try:
            with open(self.lock_path, 'r') as f:
                return int(f.read().strip())
        except Exception:
            return -1
    
    def _break_stale_lock(self) -> bool:
        """尝试打破僵尸锁，返回是否成功"""
        try:
            lock_pid = self._read_lock_pid()
            current_pid = os.getpid()
            
            # 情况1: 锁是我们自己持有的（当前进程）
            if lock_pid == current_pid:
                print(f"[SimpleFileLock] 检测到本进程持有的旧锁，清理中...")
                os.unlink(self.lock_path)
                return True
            
            # 情况2: 持有锁的进程已不存在
            if lock_pid > 0 and not self._is_process_running(lock_pid):
                print(f"[SimpleFileLock] 检测到僵尸锁 (PID {lock_pid} 已不存在)，清理中...")
                os.unlink(self.lock_path)
                return True
            
            # 情况3: 锁已超时
            if self._is_lock_expired():
                print(f"[SimpleFileLock] 检测到超时锁，清理中...")
                os.unlink(self.lock_path)
                return True
            
            return False
        except Exception as e:
            print(f"[SimpleFileLock] 清理僵尸锁失败: {e}")
            return False
    
    def acquire(self) -> bool:
        """
        获取锁
        
        逻辑：
        1. 先尝试创建锁文件
        2. 如果失败，检查是否是僵尸锁（进程不存在或已超时）
        3. 如果是僵尸锁，清理后重试
        """
        # 第一次尝试获取锁
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            self._acquired = True
            return True
        except FileExistsError:
            # 锁文件已存在，检查是否是僵尸锁
            pass
        except Exception:
            return False
        
        # 尝试清理僵尸锁
        if self._break_stale_lock():
            # 清理成功后，再次尝试获取锁
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self._acquired = True
                return True
            except Exception:
                return False
        
        # 锁确实被其他活跃进程持有
        return False
    
    def release(self):
        """释放锁"""
        if self._acquired:
            try:
                if os.path.exists(self.lock_path):
                    # 安全检查：确保只删除自己创建的锁
                    lock_pid = self._read_lock_pid()
                    if lock_pid == os.getpid():
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
_sessions = {}  # 改为字典，存储各公司的 session
_session_lock = threading.Lock()

# 全局状态：记录上次执行时间
_last_run_time: Optional[datetime] = None
_last_run_lock = threading.Lock()

# 单实例锁
_task_lock = SimpleFileLock("ks_auto_bill_task")


def get_session(company='fsbbr') -> Optional[object]:
    """获取当前 session（线程安全）"""
    with _session_lock:
        return _sessions.get(company)


def set_session(session: Optional[object], company='fsbbr'):
    """设置 session（线程安全）"""
    with _session_lock:
        global _sessions
        _sessions[company] = session


def get_last_run_time() -> Optional[datetime]:
    """获取上次执行时间"""
    with _last_run_lock:
        return _last_run_time


def set_last_run_time(t: datetime):
    """设置上次执行时间"""
    with _last_run_lock:
        global _last_run_time
        _last_run_time = t


def check_login_status(session):
    """检查登录状态是否有效"""
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


def push_cookie_invalid_warning(company):
    """推送开思 cookie 失效预警"""
    organization = COMPANY_CONFIG.get(company, {}).get('name', company)
    remind_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = (
        "===【开思业务预警】===\n"
        f"组织：{organization}\n"
        "开思cookie失效！\n"
        f"提醒时间：{remind_time}\n"
        "请及时核对处理！"
    )
    try:
        message_push("开思", message)
        print(f"[开思自动对单][{company}] 已推送 cookie 失效预警")
    except Exception as e:
        print(f"[开思自动对单][{company}] 推送 cookie 失效预警失败: {e}")


def is_running_time():
    """检查是否在运行时间段内（8:30-19:00）"""
    now = datetime.now()
    return (8 <= now.hour < 19) or (now.hour == 8 and now.minute >= 30)


def process_company_once(company):
    """
    处理单个公司的订单

    参数:
        company: 公司代码

    返回:
        tuple: (success: bool, message: str, total_count: int, success_count: int, fail_count: int)
    """
    print(f"\n{'='*60}")
    print(f"[开思自动对单][{company}] 开始处理")
    print(f"{'='*60}")

    # 检查登录状态
    session = get_session(company)
    had_session = session is not None
    print(f"\n[开思自动对单][{company}] 检查登录状态...")

    if not check_login_status(session):
        print(f"[开思自动对单][{company}] 登录已过期或未登录，重新登录...")
        session = login(company)

        if not check_login_status(session):
            set_session(None, company)
            if had_session:
                push_cookie_invalid_warning(company)
            error_msg = "登录失败或 cookie 已失效"
            print(f"[开思自动对单][{company}] {error_msg}")
            return False, error_msg, 0, 0, 0

        set_session(session, company)
        print(f"[开思自动对单][{company}] 登录成功")
    else:
        print(f"[开思自动对单][{company}] 登录状态有效")

    # 获取订单并保存到数据库
    print(f"\n[开思自动对单][{company}] 获取开思订单并保存到数据库...")
    # 打印本次爬取的时间范围（只打印一次）
    print_date_range()

    try:
        all_order_info_list, pending_confirmation_orders = extract_and_save_order_info(session, company=company)
        print(f"[开思自动对单][{company}] 成功获取并保存 {len(all_order_info_list)} 条订单信息")
        print(f"[开思自动对单][{company}] 找到 {len(pending_confirmation_orders)} 条待处理订单")
    except Exception as e:
        error_msg = f"获取订单信息失败: {str(e)}"
        print(f"[开思自动对单][{company}] {error_msg}")
        return False, error_msg, 0, 0, 0

    # 发送订单到 CRM
    if pending_confirmation_orders:
        print(f"\n[开思自动对单][{company}] 开始处理 {len(pending_confirmation_orders)} 条待处理订单...")
        try:
            results = send_orders_to_crm(pending_confirmation_orders, company=company)
            success_count = sum(1 for r in results if r.get("result") is not None)
            fail_count = len(results) - success_count
            total_count = len(results)
            print(f"[开思自动对单][{company}] 处理完成: {success_count}/{len(results)} 成功")
            return True, f"成功 {success_count}/{len(results)}", total_count, success_count, fail_count
        except Exception as e:
            error_msg = f"发送订单到 CRM 失败: {str(e)}"
            print(f"[开思自动对单][{company}] {error_msg}")
            return False, error_msg, 0, 0, 0
    else:
        print(f"\n[开思自动对单][{company}] 没有待处理订单，跳过 CRM 开单")
        return True, "没有待处理订单", 0, 0, 0


def process_orders_once():
    """
    单次执行开单流程（处理所有公司）

    返回: (success: bool, message: str, details: dict)
    """
    current_time = datetime.now()
    set_last_run_time(current_time)

    print(f"\n{'=' * 60}")
    print(f"[开思自动对单] 开始执行: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[开思自动对单] 处理公司: {', '.join(COMPANIES)}")
    print(f"{'=' * 60}")

    # 1. 检查是否在运行时间内（早上7点到晚上24点）
    if not is_running_time():
        print(f"[开思自动对单] 当前时间 {current_time.hour} 点，不在运行时间段内，跳过")
        return True, "不在运行时间段", {}

    # 2. 处理所有公司
    results = {}
    total_success = 0
    total_count = 0
    total_success_count = 0
    total_fail_count = 0

    for company in COMPANIES:
        success, message, count, success_count, fail_count = process_company_once(company)
        results[company] = {
            'success': success,
            'message': message,
            'count': count,
            'success_count': success_count,
            'fail_count': fail_count
        }
        if success:
            total_success += 1
        total_count += count
        total_success_count += success_count
        total_fail_count += fail_count

        # 短暂休眠，避免请求过于频繁
        time.sleep(2)

    print(f"\n{'='*60}")
    print("[开思自动对单] 汇总结果:")
    for company, result in results.items():
        print(f"  [{company}] 成功 {result['success_count']} 条，失败 {result['fail_count']} 条")
    print(f"{'='*60}")
    
    print(f"\n[开思自动对单] 执行完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}\n")
    
    all_success = total_success == len(COMPANIES)
    return all_success, f"成功 {total_success}/{len(COMPANIES)} 家公司，共 {total_count} 条订单", results


def ks_auto_bill_task():
    """
    开思自动对单任务（供统一任务管理器调用）

    特点：
    1. 单次执行，不循环（由调度器负责每分钟调用）
    2. 自带单实例锁，防止重复执行
    """
    # 1. 获取单实例锁
    if not _task_lock.acquire():
        print("[开思自动对单] 任务已在运行中，跳过本次执行")
        return

    try:
        # 2. 执行任务
        success, message, details = process_orders_once()

        if not success:
            print(f"[开思自动对单] 任务执行失败: {message}")
        else:
            print(f"[开思自动对单] 任务执行成功: {message}")

    finally:
        # 3. 释放锁
        _task_lock.release()


def get_ks_auto_bill_task_status() -> dict:
    """
    获取开思自动对单任务状态

    返回: 状态字典
    """
    sessions_status = {}
    for company in COMPANIES:
        session = get_session(company)
        sessions_status[company] = check_login_status(session) if session else False
    
    last_run = get_last_run_time()

    return {
        'status': 'ready',
        'type': 'unified_task',
        'companies': COMPANIES,
        'sessions_valid': sessions_status,
        'last_run_time': last_run.isoformat() if last_run else None,
        'lock_acquired': _task_lock._acquired if hasattr(_task_lock, '_acquired') else False
    }
