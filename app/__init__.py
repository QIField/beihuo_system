# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 16:52
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm



def expansion_app(app):


    from app.api import api_bp        # 导入接口
    app.register_blueprint(api_bp)     # 注册接口
    
    # 注册页面路由蓝图（根路径访问）
    from app.routes import general_web_bp
    app.register_blueprint(general_web_bp)



    from app.routes.customer_quota_manager_web import customer_quota_manager_web_bp
    app.register_blueprint(customer_quota_manager_web_bp)

    from app.routes.report_wx_quote_data_web import report_wx_quote_data_web_bp
    app.register_blueprint(report_wx_quote_data_web_bp)


    # 注册仓库管理蓝图
    from app.routes.warehouse_manager_web import warehouse_manager_web_bp
    app.register_blueprint(warehouse_manager_web_bp)