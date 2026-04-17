# -*- coding:utf-8 -*-
# @Time    : 2026/4/11 18:18
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : __init__.py
# @Software: PyCharm

"""
SQLAlchemy ORM 隔离层模块

这个模块提供完全独立于旧系统的 SQLAlchemy ORM 功能：
- 不依赖 db_config.py（使用 .env 配置）
- 不依赖 database_connection.py（独立连接池）
- 不修改任何现有代码

使用示例:
    from app.utils.orm import orm_session
    from app.models.orm_models import WmsOrders
    
    with orm_session() as session:
        order = session.query(WmsOrders).filter_by(id=1).first()
"""

from config.orm_config import ORMConfig
# from app.models.orm_models.base import Base
from .session import orm_session, get_engine, get_session_factory

# 导出公共 API，方便外部使用
__all__ = ["ORMConfig","orm_session", "get_engine", "get_session_factory"]