# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 16:52
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm


def expansion_app(app):


    from app.api import api_bp        # 导入接口
    app.register_blueprint(api_bp)     # 注册接口


    # ======================
    from app.routes import general_web_bp  # 新增1：导入页面蓝图
    app.register_blueprint(general_web_bp) # 新增2：注册页面路由
