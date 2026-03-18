"""
定时清理任务和销量同步任务
任务已整合到统一的任务管理器中

原独立调度器已移除，所有任务通过 task_manager 调度
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import json
from datetime import datetime, timedelta
from app.utils.database_connection import get_db_connection


def clean_old_import_history():
    """
    清理超过6个月的导入记录
    每天凌晨2点执行
    """
    print(f"[定时任务] 开始清理超过6个月的导入记录... {datetime.now()}")
    
    # 计算6个月前的日期
    six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 查询所有有导入历史的记录
            cursor.execute("""
                SELECT id, oe, supplier, import_history 
                FROM crmapp_price_inquiry 
                WHERE import_history IS NOT NULL
            """)
            records = cursor.fetchall()
            
            cleaned_count = 0
            updated_count = 0
            
            for record in records:
                record_id, oe, supplier, import_history = record
                
                if not import_history:
                    continue
                
                # 解析导入历史
                try:
                    if isinstance(import_history, str):
                        history_list = json.loads(import_history)
                    elif isinstance(import_history, list):
                        history_list = import_history
                    else:
                        continue
                except:
                    continue
                
                # 过滤掉超过6个月的记录
                filtered_history = []
                removed_count = 0
                
                for item in history_list:
                    record_date = item.get('date', '')
                    if record_date and record_date >= six_months_ago:
                        filtered_history.append(item)
                    else:
                        removed_count += 1
                
                # 如果有记录被删除，更新数据库
                if removed_count > 0:
                    if len(filtered_history) == 0:
                        # 如果全部过期，清空 import_history
                        cursor.execute("""
                            UPDATE crmapp_price_inquiry 
                            SET import_history = NULL
                            WHERE id = %s
                        """, (record_id,))
                    else:
                        # 更新过滤后的历史记录
                        cursor.execute("""
                            UPDATE crmapp_price_inquiry 
                            SET import_history = %s
                            WHERE id = %s
                        """, (json.dumps(filtered_history, ensure_ascii=False), record_id))
                    
                    updated_count += 1
                    cleaned_count += removed_count
                    print(f"[定时任务] 清理记录: OE={oe}, 供应商={supplier}, 删除{removed_count}条旧记录")
            
            conn.commit()
            print(f"[定时任务] 清理完成: 更新了{updated_count}条记录，共删除{cleaned_count}条旧记录")
            
    except Exception as e:
        conn.rollback()
        print(f"[定时任务] 清理失败: {e}")
    finally:
        conn.close()


def sales_history_sync_task():
    """
    CRM销量明细同步任务
    每天凌晨2:35执行（在CRM全量爬取完成后）
    """
    from app.services.sales_history_service import SalesHistorySyncService
    
    print(f"[定时任务] 开始CRM销量明细同步... {datetime.now()}")
    
    try:
        service = SalesHistorySyncService()
        result = service.sync_recent_days(days=30)
        
        print(f"[定时任务] CRM销量明细同步完成:")
        print(f"  - 总页数: {result['total_pages']}")
        print(f"  - 总条目: {result['total_items']}")
        print(f"  - 保存记录: {result['saved']}")
        
    except Exception as e:
        print(f"[定时任务] CRM销量明细同步失败: {e}")
        import traceback
        traceback.print_exc()


def register_cleanup_tasks(task_manager):
    """
    注册清理任务到统一的任务管理器
    
    Args:
        task_manager: LightweightTaskManager 实例
    """
    # 注册清理任务：每天凌晨2点
    task_manager.schedule(
        clean_old_import_history,
        'cron',
        'clean_old_import_history',
        hour=2,
        minute=0,
        replace_existing=True
    )
    print("[任务] 导入记录清理: 每天02:00")
    
    # 注意：销量同步任务已改为串行执行
    # 在CRM全量爬取完成后自动调用，不再作为独立定时任务
    print("[任务] CRM销量明细同步: 串行于全量爬取后")


# 兼容旧接口，但不再创建独立调度器
def start_scheduler():
    """
    【已废弃】原独立调度器启动函数
    现在所有任务都通过 task_manager 统一管理
    保留此函数用于兼容旧代码
    """
    print("[警告] cleanup_tasks.start_scheduler() 已废弃")
    print("        所有任务现在通过 task_manager 统一管理")
    print("        请使用 app.core.task_manager 注册新任务")


def stop_scheduler():
    """
    【已废弃】原独立调度器停止函数
    """
    print("[警告] cleanup_tasks.stop_scheduler() 已废弃")


# 如果直接运行此文件，执行一次清理（用于测试）
if __name__ == '__main__':
    print("[测试] 执行一次清理任务...")
    clean_old_import_history()
