# -*- coding:utf-8 -*-
"""
reconciliation_web.py —— 开思对账页面路由
"""
from flask import Blueprint, render_template
from app.core.permission.decorators import require_page_login

reconciliation_web_bp = Blueprint(
    "reconciliation_web",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径
    static_folder="../static",        # 静态资源路径
)


@reconciliation_web_bp.route("/reconciliation")
@require_page_login()
def reconciliation():
    """开思对账（开思vs金蝶应收单）页面"""
    return render_template("reconciliation/reconciliation_main.html")
