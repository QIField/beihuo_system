# -*- coding:utf-8 -*-
"""
拣货发货模块前端页面路由

职责：
  1. 提供拣货发货页面渲染（待发货 / 已发货两张列表）

说明：
  - 数据接口统一放在 app/api/picking_shipping_api.py
  - 本模块仅做只读查询展示
"""

from flask import Blueprint, render_template

from app.core.permission.decorators import require_page_login


picking_shipping_web_bp = Blueprint(
    "picking_shipping_web_bp",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径
    static_folder="../static",        # 静态资源路径
    url_prefix='/picking_shipping_web'
)


@picking_shipping_web_bp.route("/picking_shipping")
@require_page_login()
def picking_shipping_page():
    """已发货列表页面"""
    return render_template("picking_shipping_web/picking_shipping.html")


@picking_shipping_web_bp.route("/picking_shipping_pending")
@require_page_login()
def picking_shipping_pending_page():
    """待发货列表页面"""
    return render_template("picking_shipping_web/picking_shipping_pending.html")

