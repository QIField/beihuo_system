"""
轻量级任务管理器 - 极简版
单 worker 环境下直接初始化，无需复杂检测
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class LightweightTaskManager:
    """轻量级任务管理器"""
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self._initialized = False
        self._scheduler = None
        self._executor = None
        self._init_lock = threading.Lock()
    
    def initialize(self):
        """初始化任务管理器"""
        with self._init_lock:
            if self._initialized:
                return
            
            logger.info("[TaskManager] 正在初始化...")
            
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix='task_worker_'
            )
            
            self._scheduler = BackgroundScheduler(
                job_defaults={
                    'coalesce': True,
                    'max_instances': 1,
                    'misfire_grace_time': 3600
                },
                timezone='Asia/Shanghai'
            )
            
            self._scheduler.start()
            self._initialized = True
            logger.info(f"[TaskManager] 初始化完成")
    
    def _ensure_initialized(self):
        if not self._initialized:
            raise RuntimeError("TaskManager 未初始化")
    
    def submit(self, func: Callable, *args, **kwargs) -> Any:
        """提交即时任务"""
        self._ensure_initialized()
        
        def wrapped_task():
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"任务失败 [{func.__name__}]: {e}")
                raise
        
        return self._executor.submit(wrapped_task)
    
    def schedule(self, func: Callable, trigger: str, job_id: str, 
                 replace_existing: bool = True, **trigger_args) -> None:
        """添加定时任务"""
        self._ensure_initialized()
        
        def wrapper():
            self.submit(func)
        
        if trigger == 'cron':
            trig = CronTrigger(**trigger_args)
        elif trigger == 'interval':
            trig = IntervalTrigger(**trigger_args)
        else:
            raise ValueError(f"不支持的触发器: {trigger}")
        
        self._scheduler.add_job(
            wrapper,
            trigger=trig,
            id=job_id,
            name=func.__name__,
            replace_existing=replace_existing
        )
        
        logger.info(f"[TaskManager] 任务已添加 [{job_id}]")
    
    def get_jobs(self):
        self._ensure_initialized()
        return [
            {
                'id': job.id,
                'name': job.name,
                'next_run_time': str(job.next_run_time) if job.next_run_time else None
            }
            for job in self._scheduler.get_jobs()
        ]
    
    def shutdown(self, wait: bool = True):
        """关闭"""
        if not self._initialized:
            return
        if self._scheduler:
            self._scheduler.shutdown(wait=wait)
        if self._executor:
            self._executor.shutdown(wait=wait)
        self._initialized = False


# 全局实例
task_manager = LightweightTaskManager(max_workers=10)


def init_ks_bill_monitor():
    """初始化开思自动对单任务"""
    import os

    auto_start = os.environ.get('AUTO_START_KS_BILL', 'true').lower() != 'false'
    if not auto_start:
        print("[开思自动对单] 已禁用")
        return

    try:
        from app.ks_auto_bill.task import ks_auto_bill_task

        task_manager.schedule(
            ks_auto_bill_task,
            'interval',
            'ks_auto_bill_task',
            minutes=1,
            replace_existing=True
        )

    except Exception as e:
        logger.error(f"[开思自动对单] 失败: {e}")


def init_zhuozhixing_sync():
    """初始化卓之星每日同步任务（每晚23:00执行）"""
    import os

    auto_start = os.environ.get('AUTO_START_ZHUOZHIXING', 'true').lower() != 'false'
    if not auto_start:
        print("[卓之星同步] 已禁用")
        return

    try:
        from app.external_services.zhuozhixing_sync.sync_service import zhuozhixing_daily_sync

        task_manager.schedule(
            zhuozhixing_daily_sync,
            'cron',
            'zhuozhixing_daily_sync',
            hour=23,
            minute=0,
            replace_existing=True
        )
        print("[卓之星同步] 定时任务已注册（每晚23:00）")

    except Exception as e:
        logger.error(f"[卓之星同步] 失败: {e}")
