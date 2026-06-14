# -*- coding:utf-8 -*-
# @Time    : 2026/6/10 16:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : permission_manager_web.py
# @Software : trae-cn

"""
权限管理页面路由

提供权限管理相关页面的访问入口：
- 主页面（导航容器）
- 权限列表
- 角色管理
- 用户角色分配
"""

from flask import render_template, Blueprint


permission_manager_web_bp = Blueprint(
    "permission_manager",
    __name__,
    template_folder="../templates",
    static_folder="../static",
    url_prefix='/permission_manager'
)


@permission_manager_web_bp.route("/permission_main")
def permission_manager_main():
    """权限管理主页面（左侧导航 + 右侧内容区）"""
    return render_template("permission_manager_web/permission_manager_main_web.html")


@permission_manager_web_bp.route("/permission_list")
def permission_list_page():
    """权限列表页面"""
    return render_template("permission_manager_web/permission_list.html")


@permission_manager_web_bp.route("/role_management")
def role_management_page():
    """角色管理页面"""
    return render_template("permission_manager_web/role_management.html")


@permission_manager_web_bp.route("/user_role_assignment")
def user_role_assignment_page():
    """用户角色分配页面"""
    return render_template("permission_manager_web/user_role_assignment.html")
