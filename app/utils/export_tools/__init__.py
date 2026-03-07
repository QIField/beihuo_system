"""
数据导出工具包

提供统一的数据导出功能，支持复合搜索条件、维度切换

使用示例:
    from app.utils.export_tools import handle_export_request
    
    # 导出备货（全部）
    response = handle_export_request('beihuo', store='fsbbr')
    
    # 导出备货（复合搜索）
    response = handle_export_request('beihuo', store='fsbbr', 
                                     search_params={'oe': '123', 'brand': 'ABC'})
    
    # 导出购物车（产品维度）
    response = handle_export_request('cart', store='fsbbr')
    
    # 导出购物车（供应商维度 + 搜索）
    response = handle_export_request('cart', store='fsbbr', 
                                     search_params={'dimension': 'supplier', 'oe': '123'})
"""

from .export_utils import (
    handle_export_request,
    export_beihuo,
    export_cart,
    export_data_to_excel
)

__all__ = [
    'handle_export_request',
    'export_beihuo',
    'export_cart',
    'export_data_to_excel'
]
