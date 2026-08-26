# -*- coding:utf-8 -*-
"""
开思询价 API 层
"""

from .ks_inquiry_records_api import bp as ks_inquiry_records_bp
from .ks_inquiry_export_api import bp as ks_inquiry_export_bp

# 将导出路由注册到开思询价 records 蓝图下，统一前缀 /new/api/ks_inquiry
ks_inquiry_records_bp.register_blueprint(ks_inquiry_export_bp)

__all__ = ['ks_inquiry_records_bp']
