"""
询价单报警状态管理器
用于跟踪报警确认状态，防止重复报警
"""
from datetime import datetime, timedelta
from typing import Dict

# 内存存储：已确认报警的用户（生产环境可改为Redis）
_alert_confirmed_users: Dict[str, datetime] = {}

# 报警确认有效期（分钟）
CONFIRMATION_EXPIRY_MINUTES = 30


def confirm_alert(user_id: str) -> bool:
    """
    用户确认报警
    :param user_id: 用户标识（session_id 或 user_id）
    :return: 是否确认成功
    """
    _alert_confirmed_users[user_id] = datetime.now()
    return True


def is_alert_confirmed(user_id: str) -> bool:
    """
    检查用户是否已确认报警（在有效期内）
    :param user_id: 用户标识
    :return: 是否已确认
    """
    if user_id not in _alert_confirmed_users:
        return False
    
    confirmed_at = _alert_confirmed_users[user_id]
    expiry_time = confirmed_at + timedelta(minutes=CONFIRMATION_EXPIRY_MINUTES)
    
    # 如果已过期，清除记录
    if datetime.now() > expiry_time:
        del _alert_confirmed_users[user_id]
        return False
    
    return True


def clear_expired_confirmations():
    """清理过期的确认记录"""
    now = datetime.now()
    expired_users = [
        user_id for user_id, confirmed_at in _alert_confirmed_users.items()
        if now > confirmed_at + timedelta(minutes=CONFIRMATION_EXPIRY_MINUTES)
    ]
    for user_id in expired_users:
        del _alert_confirmed_users[user_id]


def reset_alert_confirmation(user_id: str):
    """重置用户的报警确认状态（用于测试）"""
    if user_id in _alert_confirmed_users:
        del _alert_confirmed_users[user_id]
