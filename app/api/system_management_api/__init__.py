# -*- coding:utf-8 -*-
"""
系统管理 API 模块入口

包含角色管理、权限管理、用户角色管理等接口。

使用方式：
    from app.api.system_management_api import register_system_blueprints
    
    # 在 Flask 应用启动时注册蓝图
    app = Flask(__name__)
    register_system_blueprints(app)

或者单独导入：
    from app.api.system_management_api.role_api import bp as role_bp
    from app.api.system_management_api.permission_api import bp as permission_bp
    from app.api.system_management_api.user_role_api import bp as user_role_bp
    
    app.register_blueprint(role_bp)
    app.register_blueprint(permission_bp)
    app.register_blueprint(user_role_bp)
"""
from flask import Blueprint

system_management_bp = Blueprint('system_management_api_bp', __name__, url_prefix='/system_management')

from . permission_api import permission_bp
system_management_bp.register_blueprint(permission_bp)

from . role_api import role_bp
system_management_bp.register_blueprint(role_bp)

from . user_role_api import user_role_bp
system_management_bp.register_blueprint(user_role_bp)



__all__ = [
    'system_management_bp',
]
