# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 17:26
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py.py
# @Software: PyCharm

from .general_web_bp import general_web_bp
from .customer_quota_manager_web import customer_quota_manager_web_bp


__all__ = ['general_web_bp','customer_quota_manager_web_bp']