# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 16:52
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm



def expansion_app(app):

    # 初始化任务日志（按任务拆分日志文件）
    from app.utils.logger_config import init_loggers
    init_loggers()

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

    # 注册新的主蓝图
    from app.routes import common_web_bp
    app.register_blueprint(common_web_bp)

    # 注册订单分享公开页面蓝图（扫码/直接输入网址访问，无需登录）
    from app.routes.order_share_web import order_share_web_bp
    app.register_blueprint(order_share_web_bp)

    # 初始化权限检查器：将 PermissionService 的方法注册到 PermissionCheckerRegistry
    # 注册完成后，接口上就可以使用 @require_permission、@require_role 等装饰器
    from app.services.permission_service import init_permission_checkers
    init_permission_checkers()