"""
虚拟库存统计日志服务模块
"""
from .stats_log_service import (
    save_daily_statistics,
    save_recent_statistics,
    get_stats_log_list,
)

__all__ = [
    'save_daily_statistics',
    'save_recent_statistics',
    'get_stats_log_list',
]
