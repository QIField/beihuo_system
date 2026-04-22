# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 16:52
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm


def expansion_app(app):


    from app.api import api_bp        # 导入接口
    app.register_blueprint(api_bp)     # 注册接口
    
    # 单独注册页面路由蓝图（根路径访问）
    from app.api.diff_replace_number import diff_replace_number_bp
    app.register_blueprint(diff_replace_number_bp)
