# -*- coding:utf-8 -*-
# @Time    : 2026/4/20 20:01
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py.py
# @Software: PyCharm

from flask import Blueprint

# 创建 system_setting 子蓝图，URL前缀为 /system_setting
customer_quota_manager_bp = Blueprint('customer_quota_manager', __name__, url_prefix='/customer_quota_manager')

# 导入并注册路由
from . import transaction_amount_api
