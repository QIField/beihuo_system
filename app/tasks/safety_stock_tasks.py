"""
安全库存定时任务
每小时执行一次安全库存计算（仅fsbbr组织）
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def run_safety_stock_calculation():
    """
    执行安全库存计算任务（仅fsbbr组织）
    每小时运行一次
    """
    print(f"[{datetime.now()}] 开始执行安全库存定时计算（fsbbr）...")
    
    try:
        from app.services.safety_stock_service import execute_calculation_for_company
        
        # 仅执行fsbbr组织的计算
        count = execute_calculation_for_company(company='fsbbr')
        
        print(f"[{datetime.now()}] 安全库存计算完成，共 {count} 条记录")
        return count
        
    except Exception as e:
        print(f"[{datetime.now()}] 安全库存计算失败: {e}")
        logger.error(f"安全库存计算失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


def register_safety_stock_tasks(task_manager):
    """
    注册安全库存定时任务
    
    Args:
        task_manager: 任务管理器实例
    """
    # 每小时执行一次安全库存计算（仅fsbbr）
    task_manager.schedule(
        run_safety_stock_calculation,
        'cron',
        'safety_stock_hourly',
        hour='*',      # 每小时
        minute=0,      # 整点执行
        replace_existing=True
    )
    
    print("[安全库存任务] 已注册每小时计算任务（fsbbr）")
