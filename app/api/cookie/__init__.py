# -*- coding:utf-8 -*-
# @Time    : 2026/4/29 11:37
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm
from flask import Blueprint

# 创建 cookie 蓝图
cookie_bp = Blueprint('cookie', __name__, url_prefix='/cookie')

# 导入接口
from . import data_gzbbr_api

__all__ = ['cookie_bp']
