"""
CRM数据同步定时任务
每月1日 00:00 执行
"""

from app.utils.crm_data_sync.main import main as crm_data_sync_main


def run_crm_data_sync():
    """执行CRM数据同步"""
    print("="*60)
    print("定时任务：开始CRM数据同步")
    print("="*60)
    crm_data_sync_main()
    print("="*60)
    print("定时任务：CRM数据同步完成")
    print("="*60)


def register_crm_data_sync_tasks(task_manager):
    """
    注册CRM数据同步定时任务
    
    Args:
        task_manager: 任务管理器实例
    """
    task_manager.add_job(
        run_crm_data_sync,
        'cron',
        day=1,
        hour=0,
        minute=0,
        id='crm_data_sync',
        name='CRM数据同步'
    )
