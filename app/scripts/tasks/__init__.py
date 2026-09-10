# -*- coding:utf-8 -*-
# @Time    : 2026/4/10 13:38
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm





def expansion_tasks(task_manager):


    from app.core.task_enhancer import set_task_manager, install_enhancements
    set_task_manager(task_manager)
    install_enhancements()
    
    # 注册测试定时任务
    # from app.scripts.tasks.tasks_test import test
    # test()
    
   

    # 注册合并订单列表定时任务（订单列表爬虫，关联额度管理）
    from app.scripts.tasks.get_mergeOrderList_tasks import merge_order_list_register
    merge_order_list_register(task_manager)

    # 注册合作伙伴列表定时任务
    from app.scripts.tasks.partnerList_tasks import partner_list_register
    partner_list_register(task_manager)


    # 注册crm销售订单表定时任务
    from app.scripts.tasks.crm.get_merge_order_list_tasks import get_merge_order_list_by_time_register
    get_merge_order_list_by_time_register()

    # 注册crm销售订单表定时任务
    from app.scripts.tasks.crm.get_merge_order_list_tasks import get_merge_order_list_by_all_updata_register
    get_merge_order_list_by_all_updata_register()
    
    # 注册wms拣货订单定时任务
    from app.scripts.tasks.wms.get_status_orders_tasks import get_wms_picking_list_by_pages5_register
    get_wms_picking_list_by_pages5_register()
    
    # 注册wms拣货订单定时任务
    from app.scripts.tasks.wms.get_status_orders_tasks import get_wms_picking_list_by_keywd_register
    get_wms_picking_list_by_keywd_register()
    
    # 注册wms拣货订单定时任务
    from app.scripts.tasks.wms.get_status_orders_tasks import get_wms_picking_list_by_keywd_all_time_register
    get_wms_picking_list_by_keywd_all_time_register()


    # 注册区域溯源数据定时任务
    from app.scripts.tasks.region_by_number_query_tasks import query_suyuan_data_register
    query_suyuan_data_register()


    # 注册wms拣货订单定时任务
    from app.scripts.tasks.wms.get_status_orders_tasks import get_wms_picking_list_half_hour_register
    get_wms_picking_list_half_hour_register()

    # 注册库存安全体系每日全流程定时任务（每日凌晨4:00）
    from app.scripts.tasks.stock_safe_tasks import stock_safe_daily_register
    stock_safe_daily_register(task_manager)

    # 注册库存安全体系销售&退货+销量表流程（每月1/10/20号凌晨3:00）
    from app.scripts.tasks.stock_safe_tasks import stock_safe_sales_refund_register
    stock_safe_sales_refund_register(task_manager)

    # 注册每日销售爬取 + 补货清单下载链接生成（每天凌晨3:00，爬虫最先执行）
    from app.scripts.tasks.stock_safe_tasks import stock_safe_crawl_replenish_register
    stock_safe_crawl_replenish_register(task_manager)