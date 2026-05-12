# -*- coding:utf-8 -*-
# @Time    : 2026/5/5 16:48
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm

from flask import Blueprint

# 创建 wms_upload_site 子蓝图，URL前缀为 /wms_upload_site
wms_upload_site_bp = Blueprint('wms_upload_site', __name__, url_prefix='/wms_upload_site')

# 导入并注册路由
from . import wms_inbound_push_api
