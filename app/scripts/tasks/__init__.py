# -*- coding:utf-8 -*-
# @Time    : 2026/4/10 13:38
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py.py
# @Software: PyCharm


def expansion_tasks(task_manager):




    # 导入接口
    #注册定时业务
    from app.scripts.tasks.wms_get_status_orders_tasks import two_minutes_register
    two_minutes_register(task_manager)
