"""
Excel异步任务状态存储模块
复用 task_manager 的线程池，管理任务状态和进度
"""
import uuid
import threading
from datetime import datetime
from typing import Optional, Callable

# 任务状态存储（内存）
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
    try:
        # 更新为运行中
        with _task_lock:
            _task_store[task_id]['status'] = 'running'
            _task_store[task_id]['message'] = '处理中...'
        
        # 定义进度回调函数
        def progress_callback(current: int, total: int, message: str = ""):
            with _task_lock:
                _task_store[task_id]['progress'] = current
                _task_store[task_id]['total'] = total
                if message:
                    _task_store[task_id]['message'] = message
        
        # 执行业务函数
        result = func(progress_callback=progress_callback, *args, **kwargs)
        
        # 更新完成状态
        with _task_lock:
            _task_store[task_id]['status'] = 'completed'
            _task_store[task_id]['progress'] = _task_store[task_id]['total']
            _task_store[task_id]['message'] = '处理完成'
            _task_store[task_id]['result_file'] = result
            _task_store[task_id]['completed_at'] = datetime.now().isoformat()
            
    except Exception as e:
        # 更新失败状态
        with _task_lock:
            _task_store[task_id]['status'] = 'failed'
            _task_store[task_id]['message'] = f'处理失败: {str(e)}'
            _task_store[task_id]['error'] = str(e)
            _task_store[task_id]['completed_at'] = datetime.now().isoformat()


def get_task_status(task_id: str) -> Optional[dict]:
    """获取任务状态"""
    return _task_store.get(task_id)


def cleanup_old_tasks(max_age_hours: int = 24):
    """清理过期任务（可选调用）"""
    import time
    cutoff = time.time() - (max_age_hours * 3600)
    
    with _task_lock:
        expired = []
        for tid, task in _task_store.items():
            completed_at = task.get('completed_at')
            if completed_at:
                task_time = datetime.fromisoformat(completed_at).timestamp()
                if task_time < cutoff:
                    expired.append(tid)
        
        for tid in expired:
            del _task_store[tid]
