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
    
    # 导入接口
    #注册定时业务
    from app.scripts.tasks.wms_get_status_orders_tasks import two_minutes_register
    two_minutes_register(task_manager)

    # 注册合并订单列表定时任务
    from app.scripts.tasks.get_mergeOrderList_tasks import merge_order_list_register
    merge_order_list_register(task_manager)

    # 注册合作伙伴列表定时任务
    from app.scripts.tasks.partnerList_tasks import partner_list_register
    partner_list_register(task_manager)
