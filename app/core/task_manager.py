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
                 replace_existing: bool = True, next_run_time=None, **trigger_args) -> None:
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

        job_kwargs = {
            'func': wrapper,
            'trigger': trig,
            'id': job_id,
            'name': func.__name__,
            'replace_existing': replace_existing
        }
        if next_run_time:
            job_kwargs['next_run_time'] = next_run_time

        self._scheduler.add_job(**job_kwargs)

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


def init_daily_crawl_task():
    """初始化每日爬取任务（凌晨2点执行，不含询价次数同步）"""
    import os

    auto_start = os.environ.get('AUTO_START_DAILY_CRAWL', 'true').lower() != 'false'
    if not auto_start:
        print("[每日爬取] 已禁用")
        return

    try:
        from app.tasks import execute_daily_pipeline

        task_manager.schedule(
            execute_daily_pipeline,
            'cron',
            'daily_crawl_pipeline',
            hour=2,
            minute=0,
            replace_existing=True
        )
        print("[每日爬取] 定时任务已注册（凌晨2点，不含询价次数同步）")

    except Exception as e:
        logger.error(f"[每日爬取] 失败: {e}")


def init_ks_quote_count_task():
    """初始化询价次数同步任务（每天9:15执行）
    
    包含：
    1. 微信询价解析
    2. 开思询价爬取
    3. 合并统计
    """
    import os

    if os.environ.get('AUTO_START_KS_QUOTE_COUNT', 'true').lower() == 'false':
        print("[询价次数同步] 已禁用")
        return

    try:
        # 设置环境变量，自动选择线上数据库（定时任务必须自动选择）
        os.environ['DB_CHOICE'] = 'online'
        print("[询价次数同步] 已自动选择线上数据库")

        def run_quote_count_pipeline():
            """询价次数完整流程"""
            print("\n" + "="*70)
            print("[询价次数同步] 开始执行")
            print("="*70)
            
            # 1. 先解析微信询价（近7天）
            print("\n[1/3] 解析微信询价数据...")
            try:
                from app.services.quote_count_service.weixin_quote_service import WeixinQuoteParserService
                weixin_result = WeixinQuoteParserService().parse_recent_days(days=7)
                print(f"✓ 微信解析完成: {weixin_result.get('saved_count', 0)} 条")
            except Exception as e:
                import traceback
                print(f"✗ 微信解析失败: {e}")
                print(f"详细错误:\n{traceback.format_exc()}")
                weixin_result = {'saved_count': 0}
            
            # 2. 再爬开思询价
            print("\n[2/3] 爬取开思询价数据...")
            from app.services.quote_count_service import QuoteCountSyncService
            ks_result = QuoteCountSyncService().sync_recent_two_months()
            
            # 3. 统计结果
            print("\n[3/3] 询价次数同步完成")
            print(f"  - 微信: {weixin_result.get('saved_count', 0)} 条")
            print(f"  - 开思: {ks_result.get('total_items', 0)} 条")
            print("="*70 + "\n")
            
            return {
                'weixin': weixin_result,
                'ks': ks_result
            }

        task_manager.schedule(
            run_quote_count_pipeline,
            'cron',
            'ks_quote_count_task',
            hour=9,
            minute=15,
            replace_existing=True
        )
        print("[询价次数同步] 定时任务已注册（每天9:15，包含微信+开思）")

    except Exception as e:
        logger.error(f"[询价次数同步] 失败: {e}")


def init_ks_inquiry_monitor_task():
    """初始化开思询价单监控任务（8:30-19:00每5分钟，首次立即执行）"""
    import os
    from datetime import datetime

    auto_start = os.environ.get('AUTO_START_KS_INQUIRY', 'true').lower() != 'false'
    if not auto_start:
        print("[询价单监控] 已禁用")
        return

    try:
        from app.external_services.ks_inquiry_monitor.inquiry_service import get_all_stats
        from app.sockets import notification_manager

        def crawl_and_broadcast():
            """爬取数据并广播"""
            now = datetime.now()
            # 8:30-19:00运行
            if not (8 <= now.hour < 19 or (now.hour == 8 and now.minute >= 30)):
                return

            data = get_all_stats(force_refresh=True)
            notification_manager.send_notification(
                notification_type='info',
                message='询价单数据更新',
                data=data
            )

        task_manager.schedule(
            crawl_and_broadcast,
            'interval',
            'ks_inquiry_monitor_task',
            minutes=5,
            next_run_time=datetime.now(),  # 立即执行第一次
            replace_existing=True
        )
        print("[询价单监控] 定时任务已注册（8:30-19:00每5分钟，首次立即执行）")

    except Exception as e:
        logger.error(f"[询价单监控] 失败: {e}")


def init_ks_merchant_task():
    """初始化开思商家数据同步任务（每10分钟执行一次）"""
    try:
        from app.services.ks_merchant_service.task_registration import register_ks_merchant_tasks
        register_ks_merchant_tasks()
    except Exception as e:
        logger.error(f"[开思商家数据同步] 失败: {e}")
