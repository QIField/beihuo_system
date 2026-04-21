# -*- coding:utf-8 -*-
# @Time    : 2026/4/18 18:36
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm

from flask import Blueprint

# 创建 system_setting 子蓝图，URL前缀为 /system_setting
system_setting_bp = Blueprint('system_setting', __name__, url_prefix='/system_setting')

# 导入并注册路由
from . import beihuo_system_config_api
