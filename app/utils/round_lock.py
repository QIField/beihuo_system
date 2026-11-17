#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""非阻塞轮次互斥锁

用于防止同一个任务在上一轮尚未结束时被再次触发执行：

  1. 进程内锁：threading.Lock（非阻塞）
     - 防止同进程内任务并行重叠（如 APScheduler 异步提交到线程池导致
       max_instances=1 失效，任务每 2 分钟被重复触发一次）
  2. 跨进程锁：文件锁（fcntl，Linux 生产环境生效）
     - 防止多 worker / 多实例同时执行同一轮任务

任一层未抢到锁，调用方应跳过本轮（非阻塞，绝不等待）。
"""

import os
import tempfile
import threading

try:
    import fcntl
except ImportError:  # Windows 开发环境无 fcntl，仅启用进程内锁
    fcntl = None


class RoundLock:
    """轮次互斥锁：进程内 threading.Lock + 跨进程文件锁，均为非阻塞获取"""

    def __init__(self, name):
        if not name or not isinstance(name, str):
            raise ValueError("RoundLock 需要非空字符串 name")
        self._name = name
        self._thread_lock = threading.Lock()
        self._lock_path = os.path.join(tempfile.gettempdir(), f"{name}.lock")
        self._fd = None

    @property
    def name(self):
        return self._name

    def acquire(self):
        """非阻塞获取锁，成功返回 True；任何一层被占用立即返回 False"""
        if not self._thread_lock.acquire(blocking=False):
            return False
        if self._acquire_file_lock():
            return True
        self._thread_lock.release()
        return False

    def _acquire_file_lock(self):
        if fcntl is None:
            return True
        fd = None
        try:
            fd = open(self._lock_path, 'a')
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fd.seek(0)
            fd.truncate()
            fd.write(f"{os.getpid()}\n")
            fd.flush()
            self._fd = fd
            return True
        except OSError:
            if fd is not None:
                try:
                    fd.close()
                except OSError:
                    pass
            return False

    def release(self):
        """释放锁；未持有时重复释放为幂等空操作"""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
            finally:
                try:
                    self._fd.close()
                except OSError:
                    pass
                self._fd = None
        if self._thread_lock.locked():
            self._thread_lock.release()
