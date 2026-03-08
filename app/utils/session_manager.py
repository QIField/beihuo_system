"""
线程安全的 Session 管理器
解决 uWSGI 多线程环境下 requests.Session 共享导致的段错误问题
"""

import threading
import requests
from functools import wraps

# 线程本地存储
_thread_local = threading.local()


class SessionManager:
    """
    线程安全的 Session 管理器
    
    使用方式:
        1. 直接获取线程本地 session:
           session = SessionManager.get_session()
           
        2. 使用装饰器自动注入 session:
           @SessionManager.with_session
           def my_func(session, arg1, arg2):
               session.get(...)
    """
    
    _session_factory = None
    
    @classmethod
    def set_session_factory(cls, factory_func):
        """
        设置 session 工厂函数
        
        Args:
            factory_func: 创建 session 的函数，如 create_crm_session
        """
        cls._session_factory = factory_func
    
    @classmethod
    def get_session(cls):
        """
        获取线程本地的 session
        每个线程有独立的 session，避免多线程冲突
        
        Returns:
            requests.Session: 线程独立的 session 对象
        """
        if not hasattr(_thread_local, 'session'):
            if cls._session_factory is None:
                # 默认创建一个基本 session
                _thread_local.session = requests.Session()
            else:
                # 使用工厂函数创建 session
                _thread_local.session = cls._session_factory()
        return _thread_local.session
    
    @classmethod
    def clear_session(cls):
        """
        清除当前线程的 session
        在请求结束时调用，避免资源泄漏
        """
        if hasattr(_thread_local, 'session'):
            try:
                _thread_local.session.close()
            except:
                pass
            delattr(_thread_local, 'session')
    
    @classmethod
    def with_session(cls, func):
        """
        装饰器：自动注入 session 到函数的第一个参数
        
        使用示例:
            @SessionManager.with_session
            def process_data(session, data):
                session.post(...)
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            session = cls.get_session()
            return func(session, *args, **kwargs)
        return wrapper


# 便捷函数
def get_session():
    """获取线程本地 session 的便捷函数"""
    return SessionManager.get_session()


def clear_session():
    """清除当前线程 session 的便捷函数"""
    return SessionManager.clear_session()
