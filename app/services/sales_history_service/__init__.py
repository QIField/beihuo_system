"""
CRM销量明细服务包
用于同步CRM销量数据到本地数据库
"""

from .data_sync_service import SalesHistorySyncService

__all__ = ['SalesHistorySyncService']
