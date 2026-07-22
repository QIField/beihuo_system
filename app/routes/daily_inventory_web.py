# -*- coding:utf-8 -*-
# @Time    : 2026/06/07 14:43
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : daily_inventory_web.py
# @Software: trae-cn

from flask import Blueprint, render_template
from app.core.permission.decorators import require_page_login

daily_inventory_web_bp = Blueprint(
    "daily_inventory_web",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径
    static_folder="../static",        # 静态资源路径
    url_prefix='/daily_inventory_web'
)

@daily_inventory_web_bp.route("/daily_inventory")
@require_page_login()
def daily_inventory_web_list():
    """日库存主页面"""
    return render_template("daily_inventory.html")



