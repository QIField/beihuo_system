"""
统一任务管理器
整合 APScheduler 和 ThreadPoolExecutor，提供单一入口管理所有任务

核心设计：
- APScheduler 负责任务调度（何时执行）
- 单一全局线程池负责任务执行（限制总线程数）
- 统一监控和异常处理
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

# 配置日志
logger = logging.getLogger(__name__)


class UnifiedTaskManager:
    """
    统一任务管理器
    
    使用示例：
        # 1. 即时任务
        task_manager.submit(fetch_orders)
        
        # 2. 定时任务
        task_manager.schedule(fetch_orders, 'cron', 'daily_fetch', hour=13, minute=0)
        
        # 3. 延迟任务
        task_manager.schedule(send_notify, 'date', 'notify', run_date=datetime.now() + timedelta(minutes=5))
        
        # 4. 间隔任务
        task_manager.schedule(sync_data, 'interval', 'sync', minutes=15)
    """
    
    def __init__(self, max_workers: int = 50):
        """
        初始化任务管理器
        
        :param max_workers: 全局最大线程数，默认50
        """
        self.max_workers = max_workers
        
        # 单一全局线程池（核心）- 所有任务都使用这个线程池
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix='task_worker_'
        )
        
        # APScheduler 配置 - 使用统一的线程池执行器
        from apscheduler.executors.pool import ThreadPoolExecutor as APThreadPool
        
        executors = {
            'default': APThreadPool(max_workers=2)  # 调度器只需要少量线程来触发任务
        }
        
        job_defaults = {
            'coalesce': True,           # 合并错过的任务
            'max_instances': 1,         # 同一任务只能有一个实例运行
            'misfire_grace_time': 3600  # 错过任务的宽限时间（秒）
        }
        
        self._scheduler = BackgroundScheduler(
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Shanghai'
        )
        
        # 统计信息
        self._stats = {
            'submitted': 0,      # 提交的任务数
            'running': 0,        # 正在运行的任务数
            'completed': 0,      # 完成的任务数
            'failed': 0,         # 失败的任务数
            'scheduled': 0       # 定时任务数
        }
        self._stats_lock = threading.Lock()
        
        # 任务执行历史（保留最近100条）
        self._history = []
        self._history_lock = threading.Lock()
        self._max_history = 100
        
        # 注册事件监听
        self._scheduler.add_listener(
            self._on_job_event,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
        
        # 启动调度器
        self._scheduler.start()
        logger.info(f"任务管理器已启动，最大线程数: {max_workers}")
    
    def submit(self, func: Callable, *args, **kwargs) -> Any:
        """
        提交即时任务到线程池
        
        :param func: 要执行的函数
        :param args, kwargs: 函数参数
        :return: Future 对象，可通过 .result() 获取结果
        
        示例：
            future = task_manager.submit(fetch_page, 1)
            result = future.result()  # 阻塞等待结果
        """
        with self._stats_lock:
            self._stats['submitted'] += 1
            self._stats['running'] += 1
        
        # 包装任务，添加统计和异常处理
        def wrapped_task():
            task_name = func.__name__
            start_time = datetime.now()
            
            try:
                logger.debug(f"任务开始执行: {task_name}")
                result = func(*args, **kwargs)
                
                with self._stats_lock:
                    self._stats['completed'] += 1
                
                self._add_history(task_name, start_time, 'success', None)
                logger.debug(f"任务执行成功: {task_name}")
                return result
                
            except Exception as e:
                with self._stats_lock:
                    self._stats['failed'] += 1
                
                self._add_history(task_name, start_time, 'failed', str(e))
                logger.error(f"任务执行失败 [{task_name}]: {e}", exc_info=True)
                raise
                
            finally:
                with self._stats_lock:
                    self._stats['running'] -= 1
        
        return self._executor.submit(wrapped_task)
    
    def schedule(self, func: Callable, trigger: str, job_id: str, 
                 replace_existing: bool = True, **trigger_args) -> None:
        """
        添加定时任务
        
        :param func: 要执行的函数
        :param trigger: 触发器类型 ('cron', 'interval', 'date')
        :param job_id: 任务唯一标识
        :param replace_existing: 是否替换已存在的同名任务
        :param trigger_args: 触发器参数
        
        示例：
            # 每天13:00执行
            task_manager.schedule(fetch_orders, 'cron', 'daily_fetch', hour=13, minute=0)
            
            # 每15分钟执行
            task_manager.schedule(sync_data, 'interval', 'sync', minutes=15)
            
            # 5分钟后执行一次
            task_manager.schedule(notify, 'date', 'notify', run_date=datetime.now() + timedelta(minutes=5))
        """
        # 包装函数：调度器触发后，实际执行提交到线程池
        def wrapper():
            self.submit(func)
        
        # 根据触发器类型创建触发器
        if trigger == 'cron':
            trig = CronTrigger(**trigger_args)
        elif trigger == 'interval':
            trig = IntervalTrigger(**trigger_args)
        elif trigger == 'date':
            trig = DateTrigger(**trigger_args)
        else:
            raise ValueError(f"不支持的触发器类型: {trigger}")
        
        # 添加任务到调度器
        self._scheduler.add_job(
            wrapper,
            trigger=trig,
            id=job_id,
            name=func.__name__,
            replace_existing=replace_existing
        )
        
        with self._stats_lock:
            self._stats['scheduled'] = len(self._scheduler.get_jobs())
        
        logger.info(f"定时任务已添加 [{job_id}]: {func.__name__}, 触发器: {trigger}")
    
    def unschedule(self, job_id: str) -> bool:
        """
        移除定时任务
        
        :param job_id: 任务ID
        :return: 是否成功移除
        """
        try:
            self._scheduler.remove_job(job_id)
            with self._stats_lock:
                self._stats['scheduled'] = len(self._scheduler.get_jobs())
            logger.info(f"定时任务已移除: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"移除任务失败 [{job_id}]: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """暂停定时任务"""
        try:
            self._scheduler.pause_job(job_id)
            logger.info(f"定时任务已暂停: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"暂停任务失败 [{job_id}]: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """恢复定时任务"""
        try:
            self._scheduler.resume_job(job_id)
            logger.info(f"定时任务已恢复: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"恢复任务失败 [{job_id}]: {e}")
            return False
    
    def get_jobs(self):
        """获取所有定时任务列表"""
        return [
            {
                'id': job.id,
                'name': job.name,
                'next_run_time': str(job.next_run_time) if job.next_run_time else None,
                'trigger': str(job.trigger)
            }
            for job in self._scheduler.get_jobs()
        ]
    
    def get_stats(self) -> dict:
        """获取任务统计信息"""
        with self._stats_lock:
            stats = self._stats.copy()
        stats['active_threads'] = len(self._executor._threads)
        return stats
    
    def get_history(self, limit: int = 20) -> list:
        """获取任务执行历史"""
        with self._history_lock:
            return list(self._history[-limit:])
    
    def _add_history(self, task_name: str, start_time: datetime, 
                     status: str, error: Optional[str]):
        """添加执行历史"""
        with self._history_lock:
            self._history.append({
                'task': task_name,
                'start_time': start_time.isoformat(),
                'status': status,
                'error': error
            })
            # 限制历史记录数量
            if len(self._history) > self._max_history:
                self._history.pop(0)
    
    def _on_job_event(self, event: JobExecutionEvent):
        """调度器事件监听"""
        if event.exception:
            logger.error(f"调度任务异常 [{event.job_id}]: {event.exception}")
    
    def shutdown(self, wait: bool = True):
        """
        优雅关闭任务管理器
        
        :param wait: 是否等待所有任务完成
        """
        logger.info("正在关闭任务管理器...")
        
        # 关闭调度器
        self._scheduler.shutdown(wait=wait)
        
        # 关闭线程池
        self._executor.shutdown(wait=wait)
        
        logger.info("任务管理器已关闭")


def init_ks_bill_monitor():
    """
    初始化开思自动对单子进程监控
    
    功能：
    1. 每分钟检查子进程状态
    2. 默认自动重启崩溃的子进程
    3. 记录监控日志
    
    使用环境变量 AUTO_START_KS_BILL 控制是否自动重启（默认启用）
    如需禁用，设置 AUTO_START_KS_BILL=false
    """
    import os
    
    def monitor_ks_bill_process():
        """监控任务：检查子进程状态并在需要时重启"""
        try:
            # 延迟导入，避免循环依赖
            from backend.ks_auto_bill_api import (
                get_ks_auto_bill_status,
                start_ks_auto_bill_process
            )
            from app.core.process_manager import ks_bill_process_manager
            from datetime import datetime
            
            status = get_ks_auto_bill_status()
            current_hour = datetime.now().hour
            
            # 检查是否禁用自动重启（默认启用）
            auto_start = os.environ.get('AUTO_START_KS_BILL', 'true').lower() != 'false'
            
            # 在7点运行时间段开始时，强制重置计数器并启动子进程
            if current_hour == 7 and status.get('status') != 'running':
                logger.info("[子进程监控] 早上7点，进入开思自动对单运行时间，强制启动子进程...")
                # 重置计数器，确保可以启动
                ks_bill_process_manager.reset_restart_count()
                success = start_ks_auto_bill_process()
                if success:
                    logger.info("[子进程监控] 早上7点子进程启动成功")
                else:
                    logger.error("[子进程监控] 早上7点子进程启动失败")
            elif auto_start and status.get('status') != 'running':
                logger.info(f"[子进程监控] 检测到开思自动对单进程未运行，状态: {status}")
                logger.info("[子进程监控] 尝试自动重启...")
                
                success = start_ks_auto_bill_process()
                
                if success:
                    logger.info("[子进程监控] 子进程重启成功")
                else:
                    logger.warning("[子进程监控] 子进程重启失败")
            
        except Exception as e:
            logger.error(f"[子进程监控] 监控任务执行出错: {e}")
    
    # 注册监控任务：每分钟执行一次
    task_manager.schedule(
        monitor_ks_bill_process,
        'interval',
        'ks_bill_process_monitor',
        minutes=1,
        replace_existing=True
    )
    
    # 注册每天0点重置重启计数器的任务
    def reset_restart_counter():
        """每天0点重置子进程重启计数器"""
        try:
            from app.core.process_manager import ks_bill_process_manager
            ks_bill_process_manager.reset_restart_count()
            logger.info("[子进程监控] 每天0点已重置子进程重启计数器")
        except Exception as e:
            logger.error(f"[子进程监控] 重置重启计数器失败: {e}")
    
    task_manager.schedule(
        reset_restart_counter,
        'cron',
        'ks_bill_reset_counter',
        hour=0,
        minute=0,
        replace_existing=True
    )
    
    logger.info("[子进程监控] 开思自动对单子进程监控已启动（每分钟检查一次）")
    logger.info("[子进程监控] 已添加每天0点重置重启计数器任务")
    print("[子进程监控] 开思自动对单子进程监控已启动（每分钟检查一次）")
    print("[子进程监控] 已添加每天0点重置重启计数器任务")
    print("[子进程监控] 已添加早上7点强制启动子进程任务")


# 全局任务管理器实例
# 在应用启动时创建，全局共享
task_manager = UnifiedTaskManager(max_workers=50)
