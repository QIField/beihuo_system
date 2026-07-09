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
    
   
    # #注册wms定时业务（关联旧版仓库看板）
    # from app.scripts.tasks.wms_get_status_orders_tasks import two_minutes_register
    # two_minutes_register(task_manager)

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
