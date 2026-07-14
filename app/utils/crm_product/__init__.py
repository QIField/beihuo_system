"""
CRM Product Package - CRM产品处理包
包含CRM产品新建、处理等相关功能
"""

from .crm_productAdd.api_wrappers import process_excel_async_wrapper
from .crm_productAdd.database_mode import process_database_mode_api

__version__ = "2.0.0"
__author__ = "BBR Team"
__all__ = [
    'process_excel_async_wrapper',
    'process_database_mode_api',
]
