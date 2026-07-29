# -*- coding:utf-8 -*-
"""
CRM 零件品牌别名管理页面路由
"""

from flask import render_template, Blueprint
from app.core.permission.decorators import require_page_login


pp_alias_manager_web_bp = Blueprint(
    "pp_alias_manager",
    __name__,
    template_folder="../templates",
    static_folder="../static",
    url_prefix='/pp_alias_manager'
)


@pp_alias_manager_web_bp.route("/")
@require_page_login()
def pp_alias_manager_page():
    """CRM 零件品牌别名管理页面"""
    return render_template("pp_alias_manager/pp_alias_manager.html")
