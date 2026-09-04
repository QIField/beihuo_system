# -*- coding:utf-8 -*-
"""
开思对账 API 模块
"""
from flask import Blueprint

# 创建对账子蓝图，URL前缀为 /reconciliation
reconciliation_bp = Blueprint('reconciliation', __name__, url_prefix='/reconciliation')

# 导入并注册路由
from . import reconciliation_api
