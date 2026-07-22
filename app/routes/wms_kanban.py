# -*- coding:utf-8 -*-
# @Time    : 2026/06/26 14:52
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crm_kanban.py
# @Software: trae-cn



from flask import Blueprint, render_template

from app.core.permission.decorators import require_page_login


wms_kanban_web_bp = Blueprint(
    "crmwms_kanban_web",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径
    static_folder="../static",        # 静态资源路径
    url_prefix='/wms_kanban'
)


@wms_kanban_web_bp.route("/screen")
@require_page_login()
def wms_kanban_screen():
    """看板页面"""
    return render_template("wms_kanban.html")

