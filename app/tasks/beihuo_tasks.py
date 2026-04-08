"""
备货数据定时任务

提供自动更新和自动拉取的定时任务入口。
"""

from datetime import datetime

from app.services.beihuo_service import (
    update_then_fetch_all,
    update_all_companies,
    fetch_all_companies,
)


def auto_update_and_fetch_task():
    """
    自动更新+延迟拉取任务
    
    由定时任务管理器调用，每30分钟执行一次
    执行流程：更新所有门店 → 延迟15分钟 → 拉取所有门店
    """
    print(f"\n[定时任务] 备货数据自动更新+拉取任务开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    update_then_fetch_all()
    print(f"[定时任务] 备货数据自动更新+拉取任务结束\n")


def auto_update_task():
    """
    自动更新任务
    
    仅触发所有门店的数据更新
    """
    print(f"\n[定时任务] 备货数据自动更新任务开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    result = update_all_companies()
    print(f"[定时任务] 备货数据自动更新任务结束，成功: {result['success_count']}/{result['total']}\n")


def auto_fetch_task():
    """
    自动拉取任务
    
    仅拉取所有门店的数据
    """
    print(f"\n[定时任务] 备货数据自动拉取任务开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    result = fetch_all_companies()
    print(f"[定时任务] 备货数据自动拉取任务结束，成功: {result['success_count']}/{result['total']}，共 {result['total_records']} 条\n")


def register_beihuo_tasks(task_manager):
    """
    注册备货数据定时任务
    
    Args:
        task_manager: 任务管理器实例
    """
    import os
    
    # 检查是否启用自动任务
    auto_start = os.environ.get('AUTO_START_BEIHUO', 'true').lower() != 'false'
    if not auto_start:
        print("[备货数据同步] 自动任务已禁用")
        return
    
    try:
        # 注册自动更新+拉取任务（每30分钟执行一次：每小时的00分和30分）
        task_manager.schedule(
            auto_update_and_fetch_task,
            'cron',
            'beihuo_auto_update_fetch',
            minute='0,30',  # 每小时的00分和30分
            replace_existing=True
        )
        print("[备货数据同步] 自动更新+拉取任务已注册（每30分钟执行）")
        
    except Exception as e:
        print(f"[备货数据同步] 注册定时任务失败: {e}")
