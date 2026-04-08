"""
定时任务调度模块
所有任务已整合到统一的任务管理器中

使用方式:
    from app.utils.scheduler import register_cleanup_tasks
    from app.core.task_manager import task_manager

    register_cleanup_tasks(task_manager)
"""

from .cleanup_tasks import (
    register_cleanup_tasks,
    start_scheduler,  # 已废弃，保留兼容
    stop_scheduler    # 已废弃，保留兼容
)

__all__ = [
    'register_cleanup_tasks',
    'start_scheduler',  # 已废弃
    'stop_scheduler'    # 已废弃
]
