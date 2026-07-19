"""
Excel异步任务状态存储模块
使用线程安全的共享存储，管理任务状态和进度
"""
import uuid
import threading
from datetime import datetime
from typing import Optional, Callable

# 线程内共享的任务存储（任务在线程池中执行，无需跨进程共享）
_task_store = {}
_task_lock = threading.Lock()


def submit_excel_task(func: Callable, *args, **kwargs) -> str:
    """
    提交Excel异步任务

    Args:
        func: 业务处理函数，需接收 progress_callback 参数
        *args, **kwargs: 传递给业务函数的参数

    Returns:
        task_id: 任务ID，用于查询状态和下载结果
    """
    task_id = f"excel_{uuid.uuid4().hex[:12]}"

    with _task_lock:
        _task_store[task_id] = {
            'id': task_id,
            'status': 'pending',
            'progress': 0,
            'total': 0,
            'message': '等待处理',
            'result_file': None,
            'result_data': None,
            'error': None,
            'created_at': datetime.now().isoformat(),
            'completed_at': None
        }

    # 提交到线程池执行
    from app.core.task_manager import task_manager
    task_manager.submit(_execute_wrapper, task_id, func, *args, **kwargs)

    return task_id


def _execute_wrapper(task_id: str, func: Callable, *args, **kwargs):
    """任务执行包装器"""
    # 更新为运行中
    with _task_lock:
        task = dict(_task_store[task_id])
        task['status'] = 'running'
        task['message'] = '处理中...'
        _task_store[task_id] = task

    # 定义进度回调函数
    def progress_callback(current: int, total: int, message: str = ""):
        with _task_lock:
            task = dict(_task_store[task_id])
            task['progress'] = current
            task['total'] = total
            if message:
                task['message'] = message
            _task_store[task_id] = task

    try:
        # 执行业务函数
        result = func(progress_callback=progress_callback, *args, **kwargs)

        # 更新完成状态
        with _task_lock:
            task = dict(_task_store[task_id])
            task['status'] = 'completed'
            task['progress'] = task['total']
            task['message'] = '处理完成'
            # 兼容返回字典（包含 result_file 和 result_data）的旧函数
            if isinstance(result, dict) and 'result_file' in result:
                task['result_file'] = result.get('result_file')
                task['result_data'] = result.get('result_data')
            else:
                task['result_file'] = result
            task['completed_at'] = datetime.now().isoformat()
            _task_store[task_id] = task
    except Exception as e:
        # 更新失败状态并抛出异常
        with _task_lock:
            task = dict(_task_store[task_id])
            task['status'] = 'failed'
            task['message'] = f'处理失败: {str(e)}'
            task['error'] = str(e)
            task['completed_at'] = datetime.now().isoformat()
            _task_store[task_id] = task
        raise


def get_task_status(task_id: str) -> Optional[dict]:
    """获取任务状态"""
    with _task_lock:
        task = _task_store.get(task_id)
        if task:
            # 返回普通字典的副本
            return dict(task)
        return None


def cleanup_old_tasks(max_age_hours: int = 24):
    """清理过期任务（可选调用）"""
    import time
    cutoff = time.time() - (max_age_hours * 3600)

    with _task_lock:
        expired = []
        for tid in list(_task_store.keys()):
            task = _task_store[tid]
            completed_at = task.get('completed_at')
            if completed_at:
                task_time = datetime.fromisoformat(completed_at).timestamp()
                if task_time < cutoff:
                    expired.append(tid)

        for tid in expired:
            del _task_store[tid]
