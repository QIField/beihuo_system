# -*- coding:utf-8 -*-
# @Time    : 2026/4/28 16:33
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm

from flask import Blueprint

# 创建 report_wx_quote_data 子蓝图，URL前缀为 /report_wx_quote_data
report_wx_quote_data_bp = Blueprint('report_wx_quote_data', __name__, url_prefix='/report_wx_quote_data')

# 导入并注册路由
from . import report_wx_quote_data_api
