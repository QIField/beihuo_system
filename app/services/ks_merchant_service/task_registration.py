"""
开思商家服务 - 定时任务注册

负责将定时任务注册到全局任务管理器
"""

from datetime import datetime
from app.core.task_manager import task_manager
from app.tasks.ks_merchant_tasks import ks_merchant_sync_task


def register_ks_merchant_tasks():
    """
    注册开思商家数据同步定时任务
    
    每10分钟执行一次，首次立即执行，8:30-19:00运行
    """
    try:
        def sync_with_time_limit():
            """带时间限制的同步任务"""
            now = datetime.now()
            # 8:30-19:00运行
            if not (8 <= now.hour < 19 or (now.hour == 8 and now.minute >= 30)):
                return
            
            # 执行同步
            ks_merchant_sync_task()

        task_manager.schedule(
            sync_with_time_limit,
            'interval',
            'ks_merchant_sync_task',
            minutes=10,
            next_run_time=datetime.now(),  # 立即执行第一次
            replace_existing=True
        )
        print("[开思商家数据同步] 定时任务已注册（8:30-19:00每10分钟，首次立即执行）")
    except Exception as e:
        print(f"[开思商家数据同步] 注册失败: {e}")
        # 注册失败不抛出异常，避免影响其他模块加载
