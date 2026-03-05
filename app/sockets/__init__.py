"""
WebSocket通信模块
提供实时通知和双向通信功能
"""

from .notification_manager import (
    NotificationManager,
    notification_manager,
    send_websocket_notification
)
from .event_handlers import register_socket_events

# 导出主要组件
__all__ = [
    'NotificationManager',
    'notification_manager', 
    'send_websocket_notification',
    'register_socket_events'
]
