# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 17:01
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm

from flask import Blueprint



# 创建蓝图对象
api_bp = Blueprint('api', __name__, url_prefix='/new/api')

# 导入 user 接口（必须放在下面！）
from . import api_test
from . import dashboard_crm_wms
from .replace_number_api import replace_number_bp
from .system_setting_api import system_setting_bp
from .customer_quota_manager_api import customer_quota_manager_bp
from .data_board_info_api import report_wx_quote_data_bp
from .cookie import cookie_bp
from .wms_upload_site_api import wms_upload_site_bp
from .car_parts_library_api import car_parts_library_bp
from .qpl_quote_api import qpl_quote_bp
from .ks_inquiry_api import ks_inquiry_records_bp
from .user_preference_api import column_preference_bp
from .multi_channel_quote_adjust_api import multi_channel_quote_adjust_bp



# 注册替换号蓝图
api_bp.register_blueprint(replace_number_bp, url_prefix='/replace-number')
api_bp.register_blueprint(qpl_quote_bp)
api_bp.register_blueprint(ks_inquiry_records_bp)
api_bp.register_blueprint(column_preference_bp)
api_bp.register_blueprint(multi_channel_quote_adjust_bp)

# 将 system_setting 子蓝图注册到主蓝图
api_bp.register_blueprint(system_setting_bp)
api_bp.register_blueprint(customer_quota_manager_bp)
api_bp.register_blueprint(report_wx_quote_data_bp)
api_bp.register_blueprint(cookie_bp)
api_bp.register_blueprint(wms_upload_site_bp)
api_bp.register_blueprint(car_parts_library_bp)



# 注册 system_inventory_api 子蓝图
from .daily_inventory_api import daily_inventory_bp
api_bp.register_blueprint(daily_inventory_bp)

# 注册 system_management_api 子蓝图(系统管理)
from .system_management_api import system_management_bp
api_bp.register_blueprint(system_management_bp)

# 注册 wms_kanban_api 子蓝图(看板)
from .wms_kanban_api import wms_kanban_api_bp
api_bp.register_blueprint(wms_kanban_api_bp)

from .task_manager_api import task_manager_bp
api_bp.register_blueprint(task_manager_bp)

from .stock_safe_api import stock_safe_bp
api_bp.register_blueprint(stock_safe_bp)

# 注册开思对账 API
from .reconciliation_api import reconciliation_bp
api_bp.register_blueprint(reconciliation_bp)

# 注册 WMS 库存操作推送管理 API
from .wms_inventory_operation_api import wms_inventory_operation_bp
api_bp.register_blueprint(wms_inventory_operation_bp)


# 注册 CRM 零件品牌别名 API
from . import pp_alias_api



__all__ = ["api_bp"]
