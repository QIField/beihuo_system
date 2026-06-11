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
from . import compare_api
from .compare_api import bp as compare_bp
from .system_setting_api import system_setting_bp
from .customer_quota_manager_api import customer_quota_manager_bp
from .data_board_info_api import report_wx_quote_data_bp
from .cookie import cookie_bp
from .wms_upload_site_api import wms_upload_site_bp
from .car_parts_library_api import car_parts_library_bp
from .qpl_quote_api import qpl_quote_bp
from .ks_inquiry_api import ks_inquiry_records_bp

# 注册比价数据对比蓝图（设置正确的 url_prefix）
api_bp.register_blueprint(compare_bp, url_prefix='/compare')
api_bp.register_blueprint(qpl_quote_bp)
api_bp.register_blueprint(ks_inquiry_records_bp)

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



__all__ = ["api_bp"]
