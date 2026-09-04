# -*- coding:utf-8 -*-
"""
WMS 库存操作推送 - 页面路由
"""

from flask import Blueprint, render_template

from app.core.permission.decorators import require_page_login


wms_inventory_operation_web_bp = Blueprint(
    "wms_inventory_operation_web",
    __name__,
    template_folder="../templates",
    static_folder="../static",
    url_prefix='/wms_inventory_operation'
)


@wms_inventory_operation_web_bp.route("/")
@require_page_login()
def index_page():
    """WMS 采购入库/移除推送管理页面"""
    return render_template("wms_inventory_operation_web/index.html")
