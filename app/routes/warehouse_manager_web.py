# -*- coding:utf-8 -*-
# @Time    : 2026/5/5 17:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : warehouse_manager_web.py
# @Software: PyCharm
from flask import render_template, Blueprint

warehouse_manager_web_bp = Blueprint(
    "warehouse_manager",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径
    static_folder="../static",        # 静态资源路径
)


from app.core.permission.decorators import require_page_login

@warehouse_manager_web_bp.route("/wms_upload_site")
@require_page_login()
def wms_upload_site():
    """WMS采购入库单数据管理页面"""
    return render_template("wms_upload_site_web.html")