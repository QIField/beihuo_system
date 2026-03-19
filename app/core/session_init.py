"""
全局 Session 统一初始化模块
在整个应用启动时只调用一次
"""

from app.utils.session_manager import SessionManager
from config import create_crm_session


def init_session_manager():
    """初始化 SessionManager，设置 CRM session 工厂"""
    if SessionManager._session_factory is None:
        SessionManager.set_session_factory(create_crm_session)
