# -*- coding:utf-8 -*-
# @Time    : 2026/06/15 09:53
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : get_status_orders_tasks.py
# @Software: trae-cn


from app.dao.crm.crm_sales_order_dao import get_pono_list
from app.scripts.spiders.spider_entities.wms_gzbbr import WmsGzbbrSpider
from app.scripts.spiders.pipeline_clean.wms_gzbbr_clear import get_status_orders_clean
from app.utils.orm.session import orm_session
from app.models.orm_models.wms.wms_picking_list import WmsPickingList
from sqlalchemy.dialects.mysql import insert


def get_status_orders_by_page_service(page_num=None, status=None, store='fsbbr', keywd=None, type=3, persist=True, logger=None):
    """
    分页爬取状态订单并清洗（while 循环版本）

    page_num 控制方式：
    - None = 自动爬取到最后一页
    - 数字 = 只爬取指定页数

    流程：
    1. while True 循环，current_page 从 1 开始累加
    2. 调用 get_status_orders 取当前页数据
    3. 无数据直接 break；数据少于 page_limit，也视为最后一页
    4. 指定了 page_num 时，爬够页数就退出
    5. 最后统一调用 get_status_orders_clean 清洗

    :param page_num: 爬取页数，None=自动全部，数字=指定页数，默认 None
    :param type: 订单类型，默认 3
    :param status: 订单状态，默认 2
    :param store: 门店标识，默认 'fsbbr'
    :param keywd: 搜索关键字，默认 None
    :param persist: 是否入库，默认 True；False 时返回清洗后的数据列表
    :param logger: 可选日志器，外部传入则使用外部日志器
    :return: persist=True 返回 bool；persist=False 返回 list[dict]
    """
    import logging
    logger = logger or logging.getLogger('wms_gzbbr')
    spider = WmsGzbbrSpider(logger=logger)

    all_data = []
    current_page = 1
    limit = 20
    while True:
        logger.info("正在爬取第 %s 页", current_page)
        json_data = spider.get_status_orders(type=type, status=status, page=current_page, keywd=keywd).json()  # pyright: ignore[reportOptionalMemberAccess]
        page_data = json_data.get("data", {}).get("data", {}).get("data")

        # 无数据直接退出
        if not page_data:
            logger.info("第 %s 页无数据，爬取结束", current_page)
            break

        page_data_clean = get_status_orders_clean(page_data, store=store)

        if persist and page_data_clean:
            ##入库
            with orm_session() as session:
                insert_stmt = insert(WmsPickingList.__table__).values(page_data_clean)

                # 改为从数据表取字段，避免多余字段KeyError
                skip_cols = {'created_at', 'updated_at', 'data_flag', 'pono'}
                all_cols = WmsPickingList.__table__.columns.keys()
                update_dict = {
                    k: insert_stmt.inserted[k]
                    for k in all_cols
                    if k not in skip_cols
                }

                # MySQL 写法：只传键值对，删除 index_elements、set_
                update_stmt = insert_stmt.on_duplicate_key_update(**update_dict)

                session.execute(update_stmt)
                session.commit()

        all_data.extend(page_data_clean)

        logger.info("第 %s 页获取 %s 条，清洗后 %s 条，累计 %s 条", current_page, len(page_data), len(page_data_clean), len(all_data))

        # 1. 指定了页数：爬够就退出
        if page_num is not None and current_page >= page_num:
            logger.info("已爬取指定的 %s 页，爬取结束", page_num)
            break

        # 2. 自动模式：当前页数量不足 page_limit，视为最后一页
        if len(page_data) < limit:
            logger.info("第 %s 页数量不足 %s 条，已到最后一页，爬取结束", current_page, limit)
            break

        current_page += 1

    spider.close()

    logger.info("清洗后数据共 %s 条", len(all_data))

    if persist:
        return bool(all_data)

    return all_data





def get_wms_picking_list_by_pages5_tasks():
    """
    获取WMS拣货订单列表
    """
    get_status_orders_by_page_service(status=0)
    get_status_orders_by_page_service(status=1)
    get_status_orders_by_page_service(page_num=3, status=None, store='fsbbr')
    


def get_wms_picking_list_by_pages5_register():
    """
    任务函数：获取WMS拣货订单列表
    """
    # orders = get_status_orders_by_page_tasks(page_num=5, status=None, store='fsbbr')

    from app.core.task_enhancer import get_task_manager
    import datetime
    task_manager=get_task_manager()
    try:
        task_manager.schedule(
            func=get_wms_picking_list_by_pages5_tasks,
            trigger='interval',
            job_id='get_wms_picking_list_by_pages5_tasks',
            minutes=5,
            next_run_time=datetime.datetime.now() + datetime.timedelta(minutes=10),
            replace_existing=True
        )
        from app.core.task_enhancer import register_task_config
        register_task_config(
            job_id='get_wms_picking_list_by_pages5_tasks',
            enabled=True,
            demand_driven=True,
            idle_timeout_seconds=30*60,
            description='获取WMS拣货订单列表任务wms_picking_list_task（按需执行，30分钟心跳）'
        )
        print("[任务] 看门狗配置已注册（按需执行模式）")

        # 创建后立即暂停，等待心跳触发
        job = task_manager._scheduler.get_job('get_wms_picking_list_by_pages5_tasks')
        if job:
            job.pause()
            print(f"[任务] 获取WMS拣货订单列表get_wms_picking_list_by_pages5_tasks,任务已暂停，等待心跳触发")


    except Exception as e:
        print(f"[任务] 注册失败: {e}")




def get_wms_picking_list_by_keywd_tasks(flag=False):
    """
    根据订单号爬取WMS拣货订单并标记已爬取
    
    :param keywd: 订单号 (pono)
    :return: True 爬取成功并标记, False 爬取失败或无数据
    """

    from datetime import datetime, timezone

    # 获取UTC今天凌晨0点的整数时间戳，完全不受服务器时区影响
    start_date = int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()-28800)
    
    end_date = start_date + 863990

    if flag:
        start_date = 1572434342
        end_date = 1992444342

    

    pono_list = get_pono_list(start_date, end_date)

    print(f"共 {len(pono_list)} 条订单")
    for pono in pono_list:
        
        print(f"[{pono['pono']}]")             


    for pono in pono_list:
        
        keywd=pono['pono']
        print(f"[{keywd}] 开始爬取")
               



        try:
            flag_data = get_status_orders_by_page_service(
                page_num=1, 
                status=None, 
                store='fsbbr', 
                keywd=keywd
            )
            
            if not flag_data:
                print(f"[{keywd}] 爬取失败，准备标记")
                # 把 wms_picking_list 表中 data_flag 字段设置为 1，使用 upsert 确保数据库中不存在时也能插入
                print(flag_data)
                with orm_session() as session:
                    insert_stmt = insert(WmsPickingList.__table__).values(
                        pono=keywd,
                        data_flag=1,
                    )
                    update_stmt = insert_stmt.on_duplicate_key_update(
                        data_flag=1,
                    )
                    session.execute(update_stmt)
                    session.commit()
                
                
            else:
                print(f"[{keywd}] 有数据返回")
                
                
        except Exception as e:
            print(f"[{keywd}] 爬取或标记失败: {e}")
            




def get_wms_picking_list_by_keywd_register():
    """
    任务函数：根据订单号爬取WMS拣货订单并标记已爬取
    """
    from app.core.task_enhancer import get_task_manager
    import datetime
    task_manager=get_task_manager()
    try:
        task_manager.schedule(
            func=get_wms_picking_list_by_keywd_tasks,
            trigger='interval',
            job_id='get_wms_picking_list_by_keywd_tasks',
            minutes=5,
            next_run_time=datetime.datetime.now() + datetime.timedelta(minutes=10),
            replace_existing=True
        )
        from app.core.task_enhancer import register_task_config
        register_task_config(
            job_id='get_wms_picking_list_by_keywd_tasks',
            enabled=True,
            demand_driven=True,
            idle_timeout_seconds=30*60,
            description='根据订单号爬取WMS拣货订单并标记已爬取任务get_wms_picking_list_by_keywd_tasks（按需执行，30分钟心跳）'
        )
        print("[任务] 看门狗配置已注册（按需执行模式）")

        # 创建后立即暂停，等待心跳触发
        job = task_manager._scheduler.get_job('get_wms_picking_list_by_keywd_tasks')
        if job:
            job.pause()
            print(f"[任务] 根据订单号爬取WMS拣货订单并标记已爬取get_wms_picking_list_by_keywd_tasks,任务已暂停，等待心跳触发")


    except Exception as e:
        print(f"[任务] 注册失败: {e}")





def get_wms_picking_list_by_keywd_all_time_register():
    """
    任务函数：根据订单号爬取WMS拣货订单并标记已爬取(查看所有订单)
    """
    from app.core.task_enhancer import get_task_manager
    task_manager=get_task_manager()

    def get_wms_picking_list_by_all_updata_tasks():
        """
        任务函数：根据订单号爬取WMS拣货订单并标记已爬取(查看所有订单)
        """
        try:
            get_status_orders_by_page_service(50)
        except Exception as e:
            print(f"[get_status_orders_by_page_service] 执行失败: {e}")
        
        try:
            get_wms_picking_list_by_keywd_tasks(flag=True)
        except Exception as e:
            print(f"[get_wms_picking_list_by_keywd_tasks] 执行失败: {e}")


    try:
        task_manager.schedule(
            func=get_wms_picking_list_by_all_updata_tasks,
            trigger='cron',
            job_id='get_wms_picking_list_by_all_updata_tasks',
            hour=2,
            minute=0,
            replace_existing=True
        )
        print("[任务] get_wms_picking_list_by_all_updata_tasks 已注册（每天凌晨2:00执行）")

    except Exception as e:
        print(f"[任务] 注册失败: {e}")



def get_wms_picking_list_half_hour_register():
    """
    任务函数：根据爬取WMS拣货订单（每半小时执行）
    """
    def get_wms_picking_list_by_half_hour_tasks():
        """
        任务函数：爬取WMS拣货订单和crm销售订单表（每半小时执行）
        """
        from app.scripts.tasks.crm.get_merge_order_list_tasks import get_merge_order_list_by_time_tasks
        get_merge_order_list_by_time_tasks()
        get_status_orders_by_page_service(status=0)
        get_status_orders_by_page_service(status=1)
        get_status_orders_by_page_service(page_num=10, status=None, store='fsbbr')

    from app.core.task_enhancer import get_task_manager
    task_manager=get_task_manager()
    try:
        task_manager.schedule(
            func=get_wms_picking_list_by_half_hour_tasks,
            trigger='interval',
            job_id='get_wms_picking_list_by_half_hour_tasks',
            minutes=30,
            replace_existing=True
        )
        print("[任务] get_wms_picking_list_by_half_hour_tasks 已注册（每半小时执行）")
    except Exception as e:
        print(f"[任务get_wms_picking_list_by_half_hour_tasks] 注册失败: {e}")

