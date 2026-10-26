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
from .excel_download import excel_download_bp
from .reconciliation_web import reconciliation_web_bp


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
from .permission_manager_web import permission_manager_web_bp
common_web_bp.register_blueprint(permission_manager_web_bp)

common_web_bp.register_blueprint(excel_download_bp)


from .wms_kanban import wms_kanban_web_bp
common_web_bp.register_blueprint(wms_kanban_web_bp)

from .system_manager_web import system_manager_web_bp
common_web_bp.register_blueprint(system_manager_web_bp)

from .pp_alias_manager_web import pp_alias_manager_web_bp
common_web_bp.register_blueprint(pp_alias_manager_web_bp)

from .stock_safe_web import stock_safe_web_bp
common_web_bp.register_blueprint(stock_safe_web_bp)

from .reconciliation_web import reconciliation_web_bp
common_web_bp.register_blueprint(reconciliation_web_bp)

from .wms_inventory_operation_web import wms_inventory_operation_web_bp
common_web_bp.register_blueprint(wms_inventory_operation_web_bp)

from .niche_web import niche_web_bp
common_web_bp.register_blueprint(niche_web_bp)


from .picking_shipping_web import picking_shipping_web_bp
common_web_bp.register_blueprint(picking_shipping_web_bp)

from .notepad_web import notepad_web_bp
common_web_bp.register_blueprint(notepad_web_bp)

from .visit_manage_web import visit_manage_web_bp
common_web_bp.register_blueprint(visit_manage_web_bp)



__all__ = ['general_web_bp','customer_quota_manager_web_bp','report_wx_quote_data_web_bp','warehouse_manager_web_bp','common_web_bp','excel_download_bp','pp_alias_manager_web_bp','niche_web_bp']

