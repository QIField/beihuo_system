


from datetime import datetime

from app.utils.common_util_module.server_push import message_push
from app.utils.region_by_number_query.suyuan_service import is_source_code, query_suyuan_data



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

    store_list=[
        {'md':'fs','name':'佛山'},
        {'md':'zs','name':'中山'},
        {'md':'zh','name':'珠海'},
        {'md':'hf','name':'合峰'},
        {'md':'by','name':'百业'}
    ]

    
       
    for store in store_list:
        md=store['md']
        name=store['name']
        try:
            data = query_suyuan_data(md, '', '')
            if not data or data['success']:
                information_push(name)
                continue
             
        except Exception as e:
            information_push(name,e)
            continue
     






    for store in store_list:
        md=store['md']
        name=store['name']
        is_source_code(md,name)
     


    

    







        


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

   

