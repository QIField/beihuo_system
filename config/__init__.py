"""
配置模块
提供 CRM 和数据库配置信息
"""

from .crm_config import get_crm_cookies
from .db_config import get_mysql_config, is_local_environment
from .cookie_config import create_crm_session, get_auth_headers, create_authenticated_headers

__all__ = [
    'get_crm_cookies',
    'get_mysql_config',
    'is_local_environment',
    'create_crm_session',
    'get_auth_headers',
    'create_authenticated_headers'
]
