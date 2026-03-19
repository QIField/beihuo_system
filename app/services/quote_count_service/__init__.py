"""
开思询价次数统计服务包
用于从开思平台爬取询价数据并统计询价次数
"""

from .quote_count_service import QuoteCountSyncService

__all__ = ['QuoteCountSyncService']
