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
from .system_setting_api import system_setting_bp
from .customer_quota_manager_api import customer_quota_manager_bp

# 将 system_setting 子蓝图注册到主蓝图
api_bp.register_blueprint(system_setting_bp)
api_bp.register_blueprint(customer_quota_manager_bp)

__all__ = ["api_bp"]