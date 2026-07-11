# -*- coding:utf-8 -*-
# @Time    : 2026/7/10
# @Author  : trae-cn
# @Project : beihuo_system
# @File    : system_manager_web.py

"""
系统管理页面路由

提供系统管理相关页面的访问入口：
- 定时任务列表
"""

from flask import render_template, Blueprint


system_manager_web_bp = Blueprint(
    "system_manager",
    __name__,
    template_folder="../templates",
    static_folder="../static",
    url_prefix='/system_manager'
)


@system_manager_web_bp.route("/task_scheduler_list")
def task_scheduler_list_page():
    """定时任务列表页面"""
    return render_template("system_manager/task_scheduler_list.html")
