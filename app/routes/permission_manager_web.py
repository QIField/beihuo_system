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

页面权限与对应 API（app/api/system_management_api/permission_api.py）口径一致：
API 层使用 @require_admin()（super_admin 角色），页面同样要求 super_admin 角色，
未登录→登录页，角色不满足→forbidden 页。
"""

from flask import render_template, Blueprint

from app.core.permission.decorators import require_page_role



permission_manager_web_bp = Blueprint(
    "permission_manager",
    __name__,
    template_folder="../templates",
    static_folder="../static",
    url_prefix='/permission_manager'
)


@permission_manager_web_bp.route("/permission_main")
@require_page_role('super_admin')
def permission_manager_main():
    """权限管理主页面（左侧导航 + 右侧内容区）"""
    return render_template("permission_manager_web/permission_manager_main_web.html")


@permission_manager_web_bp.route("/permission_list")
@require_page_role('super_admin')
def permission_list_page():
    """权限列表页面"""
    return render_template("permission_manager_web/permission_list.html")


@permission_manager_web_bp.route("/role_management")
@require_page_role('super_admin')
def role_management_page():
    """角色管理页面"""
    return render_template("permission_manager_web/role_management.html")


@permission_manager_web_bp.route("/user_role_assignment")
@require_page_role('super_admin')
def user_role_assignment_page():
    """用户角色分配页面"""
    return render_template("permission_manager_web/user_role_assignment.html")
