"""
询价单报警状态管理器
已简化：移除确认机制，每次数据更新都会重新报警
"""


def confirm_alert(user_id: str) -> bool:
    """
    用户确认报警（已废弃，保留函数兼容）
    """
    return True


def is_alert_confirmed(user_id: str) -> bool:
    """
    检查用户是否已确认报警（已废弃，始终返回False）
    """
    return False


def reset_alert_confirmation(user_id: str):
    """
    重置用户的报警确认状态（已废弃，保留函数兼容）
    """
    pass
