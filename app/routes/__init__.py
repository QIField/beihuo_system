# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 17:26
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py.py
# @Software: PyCharm

from flask import Blueprint

from .general_web_bp import general_web_bp
from .customer_quota_manager_web import customer_quota_manager_web_bp
from .report_wx_quote_data_web import report_wx_quote_data_web_bp
from .warehouse_manager_web import warehouse_manager_web_bp
from .qpl_quote_web import qpl_quote_web_bp


common_web_bp = Blueprint(
    "common_web",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径（默认即可）
    static_folder="../static",       # 静态资源路径（默认即可）
    url_prefix="/web"             # 统一前缀（推荐加上）
)
from .car_parts_library import car_parts_library_bp
common_web_bp.register_blueprint(car_parts_library_bp)
common_web_bp.register_blueprint(qpl_quote_web_bp)

from .daily_inventory_web import daily_inventory_web_bp
common_web_bp.register_blueprint(daily_inventory_web_bp)

__all__ = ['general_web_bp','customer_quota_manager_web_bp','report_wx_quote_data_web_bp','warehouse_manager_web_bp','common_web_bp']

