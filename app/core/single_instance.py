"""
单实例任务装饰器
用于防止 uWSGI 多 worker 重复启动相同任务

核心功能：
1. uWSGI worker 检测 - 只在第一个 worker 启动任务（主要方案）
2. 简单文件锁 - 作为补充保护
3. 健康检查 - 检测锁是否过期（防止崩溃后锁残留）

设计思路：
- 主要依赖 uwsgi.worker_id() == 1 来判断
- 文件锁作为双重保险
"""

import os
import time
import threading
import atexit
from typing import Callable, Optional
from datetime import datetime, timedelta


def is_first_uwsgi_worker() -> bool:
    """
    检测是否是 uWSGI 的第一个 worker

    在 uWSGI 多 worker 环境下，只让第一个 worker 启动定时任务
    注意：uwsgi.worker_id() 返回 0, 1, 2...（从0开始）
          但 uWSGI 日志显示 worker 1, 2, 3...（从1开始）

    :return: True 表示是第一个 worker 或不在 uWSGI 环境
    """
    try:
        import uwsgi
        worker_id = uwsgi.worker_id()
        print(f"[Worker检测] 当前 worker_id: {worker_id}")
        # worker_id 从 0 开始，所以第一个 worker 是 0
        return worker_id == 0
    except ImportError:
        print("[Worker检测] 无法导入 uwsgi 模块，假设为单进程环境")
        return True
    except Exception as e:
        print(f"[Worker检测] 检测失败: {e}，假设为单进程环境")
        return True


class SimpleFileLock:
    """
    简单文件锁（跨平台，无需额外依赖）

    使用文件存在性检查 + 时间戳来实现
    """

    def __init__(self, lock_name: str, lock_dir: Optional[str] = None):
        self.lock_name = lock_name
        if lock_dir is None:
            lock_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'locks')
        self.lock_dir = os.path.abspath(lock_dir)
        os.makedirs(self.lock_dir, exist_ok=True)

        self.lock_path = os.path.join(self.lock_dir, f"{lock_name}.lock")
        self._acquired = False

        self.lock_timeout = 300

    def acquire(self) -> bool:
        """获取锁"""
        try:
            if self._is_lock_expired():
                print(f"[单实例锁] {self.lock_name} 锁已过期，强制释放旧锁")
                self._force_release()

            if os.path.exists(self.lock_path):
                print(f"[单实例锁] {self.lock_name} 已被其他进程持有，跳过任务")
                return False

            with open(self.lock_path, 'w') as f:
                f.write(f"{os.getpid()}\n{datetime.now().isoformat()}\n")

            self._acquired = True
            print(f"[单实例锁] {self.lock_name} 获取成功")

            atexit.register(self.release)

            return True

        except Exception as e:
            print(f"[单实例锁] {self.lock_name} 获取锁失败: {e}")
            return False

    def release(self):
        """释放锁"""
        if self._acquired:
            try:
                if os.path.exists(self.lock_path):
                    os.unlink(self.lock_path)
                self._acquired = False
                print(f"[单实例锁] {self.lock_name} 已释放")
            except Exception as e:
                print(f"[单实例锁] {self.lock_name} 释放锁失败: {e}")

    def _is_lock_expired(self) -> bool:
        """检查锁是否过期"""
        if not os.path.exists(self.lock_path):
            return False

        try:
            with open(self.lock_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    return True

                lines = content.split('\n')
                if len(lines) >= 2:
                    try:
                        lock_time = datetime.fromisoformat(lines[1])
                        elapsed = (datetime.now() - lock_time).total_seconds()
                        return elapsed > self.lock_timeout
                    except (ValueError, IndexError):
                        return True
                return True
        except Exception:
            return True

    def _force_release(self):
        """强制释放过期锁"""
        try:
            if os.path.exists(self.lock_path):
                os.unlink(self.lock_path)
                print(f"[单实例锁] {self.lock_name} 过期锁已强制删除")
        except Exception as e:
            print(f"[单实例锁] {self.lock_name} 强制释放失败: {e}")


def single_instance_task(lock_name: str):
    """
    单实例任务装饰器（备用，主要靠 worker 检测）

    使用方法：
        @single_instance_task("my_task")
        def my_task():
            pass
    """

    def decorator(func: Callable):
        lock = SimpleFileLock(lock_name)

        def wrapper(*args, **kwargs):
            if not lock.acquire():
                return None

            try:
                return func(*args, **kwargs)
            finally:
                lock.release()

        return wrapper

    return decorator


# 全局锁，用于开思自动对单
ks_bill_lock = SimpleFileLock("ks_auto_bill_task")
