# -*- coding:utf-8 -*-
# @Time    : 2026/06/25 18:01
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : get_merge_order_list_tasks.py
# @Software: trae-cn

from app.models.orm_models.crm.crm_sales_order import CrmSalesOrder
from app.scripts.spiders.pipeline_clean.crm_gzbbr_clean import crm_sales_order_clear
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.scripts.spiders.pipeline_clean.get_mergeOrderList_clean import remove_duplicate

from app.utils.orm.session import orm_session
from config.config_list_manager.config_cache import get_config_value
from sqlalchemy.dialects.mysql import insert


# 分页爬取订单列表服务
def get_merge_order_list_by_page_service(page_num=None,
                        level_id=None,
                        orderdate_start=None,
                        orderdate_end=None,
                        status=None,
                        order_type_id=None,
                        is_wms=None,
                        order_source_type=None,
                        store="fsbbr"
                        ):
    """
    分页爬取订单列表
    :param token: 认证token
    :param level_id: 层级ID
    :param page_num: 要爬取的页数，None=自动爬取全部，数字=指定爬取N页
    :return: 所有爬取到的订单列表
    """
    spider = CrmGzbbrSpider()
    limit = 200
    data_total_count = 0  # 存储所有订单数据总计
    current_page = 1

    # # 初始化去重管道
    # deduplication_pipeline = DeduplicationPipeline(
    #     pool_name=f"mergeOrderList_{level_id}",
    #     unique_key_fields=["d_sap_no"]
    # )

    while True:
        # 请求接口
        json_data = spider.get_mergeOrderList(
            page=current_page,
            limit=limit,
            level_id=level_id,
            orderdate_start=orderdate_start,
            orderdate_end=orderdate_end,
            status=status,
            order_type_id=order_type_id,
            is_wms=is_wms,
            order_source_type=order_source_type

        ).json()  # pyright: ignore[reportOptionalMemberAccess]



        # 无数据直接退出
        if not json_data.get("data", {}):
            print(json_data)
            print(f"第{current_page}页无数据，爬取结束")
            break

        # 获取当前页订单
        order_list = json_data.get("data", {}).get("list", {}).get("data", [])

        # 进行数据清洗和字段过滤
        print(f"第{current_page}页原始订单数量: {len(order_list)}")
        filtered_data_list = crm_sales_order_clear(data_list=order_list,store=store,level_id=level_id)  # pyright: ignore[reportArgumentType]
        print(f"第{current_page}页清洗后订单数量: {len(filtered_data_list)}")
        
        # 进行入库操作（插入或更新）
        if filtered_data_list:
            print(f"开始入库第{current_page}页数据...")
            with orm_session() as session:
                insert_stmt = insert(CrmSalesOrder.__table__).values(filtered_data_list)
                
                # 改为从数据表取字段，避免多余字段KeyError
                skip_cols = {'created_at', 'updated_at','orders_id'}
                all_cols = CrmSalesOrder.__table__.columns.keys()
                update_dict = {
                    k: insert_stmt.inserted[k]
                    for k in all_cols
                    if k not in skip_cols
                }
                # MySQL 写法：只传键值对，删除 index_elements、set_
                update_stmt = insert_stmt.on_duplicate_key_update(**update_dict)
        
                session.execute(update_stmt)
                session.commit()

        
        # 累加数据
        data_total_count += len(filtered_data_list)
        print(f"第{current_page}页订单数量: {len(order_list)}, 累计: {data_total_count}")

        # ===================== 核心退出逻辑 =====================
        # 1. 指定了页数：爬够页数就退出
        if page_num is not None and current_page >= page_num:
            print(f"已爬取指定的{page_num}页，爬取结束")
            break

        # 2. 爬取全部模式：当前页数量不足limit，说明是最后一页
        if len(order_list) < limit and not json_data.get("data", {}):
            print(json_data)
            print("当前页数量不足限制，已到最后一页，爬取结束")

        # 3. 继续下一页
        current_page += 1

    # return total_item_count



# 时间范围爬取订单列表任务
def get_merge_order_list_by_time_tasks():


    from datetime import datetime, timezone

    # 获取UTC今天凌晨0点的整数时间戳，完全不受服务器时区影响
    today_start = int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()-28800)*1000
    
    today_end = today_start + 86399000


    get_merge_order_list_by_page_service(
        orderdate_start=today_start,
        orderdate_end=today_end
    )
 
# if __name__ == '__main__':
#     get_merge_order_list_by_page_service(
#         orderdate_start=1782835200000,
#         orderdate_end=1783526399000
#     )


def get_merge_order_list_by_time_register():
    """
    任务函数：获取crm销售订单表
    """
    # orders = get_status_orders_by_page_tasks(page_num=5, status=None, store='fsbbr')

    from app.core.task_enhancer import get_task_manager
    import datetime
    task_manager=get_task_manager()
    try:
        task_manager.schedule(
            func=get_merge_order_list_by_time_tasks,
            trigger='interval',
            job_id='get_merge_order_list_by_time_tasks',
            minutes=5,
            next_run_time=datetime.datetime.now() + datetime.timedelta(minutes=10),
            replace_existing=True
        )
        from app.core.task_enhancer import register_task_config
        register_task_config(
            job_id='get_merge_order_list_by_time_tasks',
            enabled=True,
            demand_driven=True,
            idle_timeout_seconds=30*60,
            description='获取crm销售订单表任务get_merge_order_list_by_time_tasks（按需执行，30分钟心跳）'
        )
        print("[任务] 看门狗配置已注册（按需执行模式）")

        # 创建后立即暂停，等待心跳触发
        job = task_manager._scheduler.get_job('get_merge_order_list_by_time_tasks')
        if job:
            job.pause()
            print(f"[任务] 获取crm销售订单表get_merge_order_list_by_time_tasks,任务已暂停，等待心跳触发")





    except Exception as e:
        print(f"[任务] 注册失败: {e}")


def get_merge_order_list_by_all_updata_register():
    """
    任务函数：获取crm销售订单表
    """
    from app.core.task_enhancer import get_task_manager
    task_manager=get_task_manager()

    def get_merge_order_list_by_all_updata_tasks():
        """
        任务函数：获取crm销售订单表
        """
        from datetime import datetime, timezone
        # 获取UTC今天凌晨0点的整数时间戳，完全不受服务器时区影响
        today_start = int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()-115200)*1000
    
        today_end = today_start + 86399000

        get_merge_order_list_by_page_service(
            orderdate_start=today_start,
            orderdate_end=today_end
        )

    try:
        task_manager.schedule(
            func=get_merge_order_list_by_all_updata_tasks,
            trigger='cron',
            job_id='get_merge_order_list_by_all_updata',
            hour=2,
            minute=0,
            replace_existing=True
        )
        print("[任务] get_merge_order_list_by_all_updata 已注册（每天凌晨2:00执行）")

    except Exception as e:
        print(f"[任务] 注册失败: {e}")






# if __name__ == '__main__':
#     get_merge_order_list_by_time_tasks()
    