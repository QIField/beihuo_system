# -*- coding:utf-8 -*-
"""
汽配龙自动报价任务入口锁 单元测试

覆盖目标：
  1. RoundLock 非阻塞获取/释放/幂等/并发竞争（进程内 + 跨进程文件锁）
  2. qpl_auto_quote_task：
     - 锁空闲时正常执行且执行后释放
     - 锁被占用时跳过本轮（不执行业务）
     - 业务异常时锁仍被释放（下一轮可执行）
     - 运行时段窗口（08:00-20:00）外的静默跳过
     - 注册参数正确性

不依赖数据库、网络与真实调度器。
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from app.utils.round_lock import RoundLock

try:
    import fcntl
except ImportError:
    fcntl = None


# ---------------------------------------------------------------------------
# 被测模块加载：独立加载任务文件，避开 app/tasks/__init__.py 的重型导入链
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_TASK_FILE = os.path.join(_PROJECT_ROOT, 'app', 'tasks', 'qpl_auto_quote_task.py')


def _load_task_module():
    spec = importlib.util.spec_from_file_location('qpl_auto_quote_task_test_module', _TASK_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_TASK_MOD = _load_task_module()


class _FakeDateTime(datetime):
    """可控小时的 datetime 替身，用于测试运行时段窗口"""
    fixed_hour = 10

    @classmethod
    def now(cls):
        return datetime(2026, 11, 17, cls.fixed_hour, 0, 0)


@pytest.fixture()
def task_mod(monkeypatch):
    """返回任务模块，并保证每个用例开始时锁处于空闲状态"""
    mod = _TASK_MOD
    mod._round_lock.release()  # 幂等复位，防用例间串扰
    monkeypatch.setattr(mod, 'datetime', _FakeDateTime)
    _FakeDateTime.fixed_hour = 10
    yield mod
    mod._round_lock.release()


# ---------------------------------------------------------------------------
# RoundLock 基础行为
# ---------------------------------------------------------------------------

def test_acquire_once_succeeds():
    lock = RoundLock('qpl_test_basic')
    assert lock.acquire() is True
    lock.release()


def test_reacquire_in_same_thread_fails():
    lock = RoundLock('qpl_test_reacquire')
    assert lock.acquire() is True
    assert lock.acquire() is False  # 非阻塞二次获取必须失败
    lock.release()
    assert lock.acquire() is True  # 释放后可重新获取
    lock.release()


def test_release_without_acquire_is_noop():
    lock = RoundLock('qpl_test_noop')
    lock.release()  # 幂等，不应抛异常
    assert lock.acquire() is True
    lock.release()


def test_invalid_name_raises():
    with pytest.raises(ValueError):
        RoundLock('')
    with pytest.raises(ValueError):
        RoundLock(None)


def test_concurrent_threads_single_winner():
    """多线程并发抢锁：恰好一个赢家，其余全部非阻塞失败"""
    lock = RoundLock('qpl_test_race')
    winners = []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        if lock.acquire():
            winners.append(threading.get_ident())

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(winners) == 1
    lock.release()


# ---------------------------------------------------------------------------
# 跨进程文件锁（仅 Linux 生产环境生效）
# ---------------------------------------------------------------------------

_HOLDER_SCRIPT = (
    "import fcntl, sys, time\n"
    "path, marker = sys.argv[1], sys.argv[2]\n"
    "fd = open(path, 'a')\n"
    "fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
    "open(marker, 'w').write('locked')\n"
    "time.sleep(15)\n"
)


@pytest.mark.skipif(fcntl is None, reason='Windows 无 fcntl，跨进程文件锁不生效')
def test_file_lock_blocks_other_process(tmp_path):
    lock_path = str(tmp_path / 'qpl_test_cross.lock')
    marker = str(tmp_path / 'holder_ready.marker')
    lock = RoundLock('qpl_test_cross')

    holder = subprocess.Popen(
        [sys.executable, '-c', _HOLDER_SCRIPT, lock_path, marker],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        # 等待子进程成功持锁（最多 10 秒）
        for _ in range(100):
            if os.path.exists(marker):
                break
            time.sleep(0.1)
        assert os.path.exists(marker), '子进程未按预期持有文件锁'

        assert lock.acquire() is False  # 跨进程占用期间必须失败

        holder.terminate()
        holder.wait(timeout=10)
        time.sleep(0.2)

        assert lock.acquire() is True  # 持有方退出（内核自动释放 flock）后可获取
        lock.release()
    finally:
        if holder.poll() is None:
            holder.terminate()
            holder.wait(timeout=10)


# ---------------------------------------------------------------------------
# 任务入口行为
# ---------------------------------------------------------------------------

def test_task_runs_and_releases_lock(task_mod, monkeypatch):
    calls = []
    monkeypatch.setattr(task_mod, 'process_and_save_quotes_for_all_companies', lambda: calls.append(1))

    task_mod.qpl_auto_quote_task()

    assert len(calls) == 1
    assert task_mod._round_lock.acquire() is True  # 执行结束后锁必须已释放
    task_mod._round_lock.release()


def test_task_skips_when_lock_held(task_mod, monkeypatch):
    calls = []
    monkeypatch.setattr(task_mod, 'process_and_save_quotes_for_all_companies', lambda: calls.append(1))

    assert task_mod._round_lock.acquire() is True  # 模拟上一轮仍在执行
    try:
        task_mod.qpl_auto_quote_task()
        assert calls == []  # 锁被占用 → 本轮直接跳过，业务不执行
    finally:
        task_mod._round_lock.release()

    task_mod.qpl_auto_quote_task()  # 锁释放后恢复正常执行
    assert calls == [1]


def test_task_releases_lock_on_exception(task_mod, monkeypatch):
    def boom():
        raise RuntimeError('业务异常')

    monkeypatch.setattr(task_mod, 'process_and_save_quotes_for_all_companies', boom)
    task_mod.qpl_auto_quote_task()  # 异常被任务入口捕获，不向外抛

    assert task_mod._round_lock.acquire() is True  # 异常路径锁仍被释放
    task_mod._round_lock.release()


def test_task_silent_outside_window(task_mod, monkeypatch):
    calls = []
    monkeypatch.setattr(task_mod, 'process_and_save_quotes_for_all_companies', lambda: calls.append(1))

    for hour in (7, 20, 23):
        _FakeDateTime.fixed_hour = hour
        task_mod.qpl_auto_quote_task()
    assert calls == []  # 08:00 前与 20:00 后完全静默

    _FakeDateTime.fixed_hour = 8
    task_mod.qpl_auto_quote_task()
    _FakeDateTime.fixed_hour = 19
    task_mod.qpl_auto_quote_task()
    assert calls == [1, 1]  # 08:00 与 19:xx 正常执行


def test_register_params(task_mod):
    class FakeTM:
        def __init__(self):
            self.calls = []

        def schedule(self, func, trigger, job_id, **kwargs):
            self.calls.append({'func': func, 'trigger': trigger, 'job_id': job_id, **kwargs})

    tm = FakeTM()
    task_mod.register_qpl_auto_quote_tasks(tm)

    assert len(tm.calls) == 1
    call = tm.calls[0]
    assert call['func'] is task_mod.qpl_auto_quote_task
    assert call['trigger'] == 'interval'
    assert call['job_id'] == task_mod.TASK_ID == 'qpl_auto_quote'
    assert call['minutes'] == 2
    assert call['replace_existing'] is True


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
