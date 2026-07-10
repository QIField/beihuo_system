


from datetime import datetime

from app.utils.common_util_module.server_push import message_push
from app.utils.region_by_number_query.suyuan_service import query_suyuan_data



def information_push(md,e=None):
    """
    信息推送
    """
    time_data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"===【溯源数据定时任务报错】==="+f"\n提醒时间：{time_data}"+f"\n{md}溯源数据查询任务失败"
    if e:
        message += f"\n错误信息：{e}"

    # print(message)



    message_push(type="溯源数据定时任务", message=message)












def query_suyuan_data_task():
    """
    查询溯源数据任务
    """
    try:
        #佛山
        fs = query_suyuan_data('fs', '', '')
        if not fs or fs['success']:
            information_push('佛山')
            return
    except Exception as e:
        information_push('佛山',e)
        return
       
        



    try:
        #中山
        zs = query_suyuan_data('zs', '', '')
        if not zs or zs['success']:
            information_push('中山')
            return
      
    except Exception as e:
        information_push('中山',e)
        return
       
        

    try:
        #珠海
        zh = query_suyuan_data('zh', '', '')
        if not zh or zh['success']:
            information_push('珠海')
            return
    except Exception as e:
        information_push('珠海',e)
        return
       
        



    try:
        #合峰
        hf = query_suyuan_data('hf', '', '')
        if not hf or hf['success']:
            information_push('合峰')
            return
    except Exception as e:
        information_push('合峰',e)
        return
       
        



    try:
        #百业
        by = query_suyuan_data('by', '', '')
        if not by or by['success']:
            information_push('百业')
            return
    except Exception as e:
        information_push('百业',e)
        return
       
        


def query_suyuan_data_register():
    """
    任务函数：查询溯源数据
    """
    from app.core.task_enhancer import get_task_manager
    task_manager=get_task_manager()


    try:
        task_manager.schedule(
            func=query_suyuan_data_task,
            trigger='cron',
            job_id='query_suyuan_data_task',
            hour=19,
            minute=0,
            replace_existing=True
        )
        print("[任务] query_suyuan_data_task 已注册（每天19:00执行）")

    except Exception as e:
        print(f"[任务] 注册失败: {e}")

   

