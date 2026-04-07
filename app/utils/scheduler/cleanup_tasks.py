"""
定时清理任务
任务已整合到统一的任务管理器中

原独立调度器已移除，所有任务通过 task_manager 调度
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def register_cleanup_tasks(task_manager):
    """
    注册清理任务到统一的任务管理器

    Args:
        task_manager: LightweightTaskManager 实例
    """
    pass


# 兼容旧接口，但不再创建独立调度器
def start_scheduler():
    """【已废弃】原独立调度器启动函数"""
    pass


def stop_scheduler():
    """【已废弃】原独立调度器停止函数"""
    pass
