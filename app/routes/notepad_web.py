# -*- coding:utf-8 -*-
"""
notepad_web.py —— 个人记事本页面路由
"""
from flask import Blueprint, render_template
from app.core.permission.decorators import require_page_login

notepad_web_bp = Blueprint(
    "notepad_web",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径
    static_folder="../static",        # 静态资源路径
)


@notepad_web_bp.route("/notepad/")
@require_page_login()
def notepad():
    """个人记事本页面"""
    return render_template("notepad/notepad.html")
