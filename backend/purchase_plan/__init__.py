"""
采购计划模块 - 统一注册路由
包含询价模块和比价模块的API
"""
from flask import Blueprint
from .inquiry_api import inquiry_bp
from .compare_api import compare_bp
from .purchase_history_compare_api import bp as purchase_history_compare_bp

# 创建主蓝图
purchase_plan_bp = Blueprint('purchase_plan', __name__)

# 注册子蓝图
purchase_plan_bp.register_blueprint(inquiry_bp, url_prefix='/inquiry')
purchase_plan_bp.register_blueprint(compare_bp, url_prefix='/compare')
purchase_plan_bp.register_blueprint(purchase_history_compare_bp, url_prefix='/purchase_history_compare')

# 导出注册函数供主应用使用
def register_purchase_plan_routes(app):
    """
    注册采购计划模块路由到主应用
    使用方式: register_purchase_plan_routes(app)
    """
    app.register_blueprint(purchase_plan_bp, url_prefix='/api/purchase_plan')
