# -*- coding: utf-8 -*-
"""
奔驰报价 OE 替换号自动同步工具包
"""

from .config import (
    TASK_NAME,
    SCHEDULE_HOUR,
    SCHEDULE_MINUTE,
    DEFAULT_COMPANY,
    DATE_OFFSET_DAYS,
    MAX_RETRY_TIMES,
)
from .models import OePair, UpdateRecord

__all__ = [
    'TASK_NAME',
    'SCHEDULE_HOUR',
    'SCHEDULE_MINUTE',
    'DEFAULT_COMPANY',
    'DATE_OFFSET_DAYS',
    'MAX_RETRY_TIMES',
    'OePair',
    'UpdateRecord',
]
