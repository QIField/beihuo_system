"""
配置模块
提供 CRM 和数据库配置信息
"""

from .crm_config import get_crm_cookies
from .db_config import get_mysql_config, is_local_environment

__all__ = [
    'get_crm_cookies',
    'get_mysql_config',
    'is_local_environment'
]
