# -*- coding:utf-8 -*-
# @Time    : 2026/05/27 16:42
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software : trae-cn

"""
汽车配件库API模块
包含奔驰汽车配件库、收藏功能、奔驰大库配置、华晨宝马配件库、华晨宝马配置五个子模块
"""

from flask import Blueprint

# 创建汽车配件库主蓝图（保持与原文件相同的名称，确保API地址不变）
car_parts_library_bp = Blueprint('car_parts_library', __name__, url_prefix='/car-parts')

# 导入并注册子模块蓝图
from . import benz_parts_api
from . import favorites_api
from . import favorites_bmw_api
from . import bmw_import_api
from . import mercedes_config_api
from . import bmw_parts_api
from . import bmw_config_api

# 注册子蓝图到主蓝图（保持API地址不变）
car_parts_library_bp.register_blueprint(benz_parts_api.benz_parts_bp)
car_parts_library_bp.register_blueprint(favorites_api.favorites_bp)
car_parts_library_bp.register_blueprint(favorites_bmw_api.favorites_bmw_bp)
car_parts_library_bp.register_blueprint(bmw_import_api.bmw_import_bp)
car_parts_library_bp.register_blueprint(mercedes_config_api.mercedes_config_bp)
car_parts_library_bp.register_blueprint(bmw_parts_api.bmw_parts_bp)
car_parts_library_bp.register_blueprint(bmw_config_api.bmw_config_bp)

__all__ = ['car_parts_library_bp']
