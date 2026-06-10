# -*- coding:utf-8 -*-
# @Time    : 2026/4/16 16:45
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : time_conversion_util.py
# @Software: PyCharm
import time
from datetime import datetime, timedelta
from typing import Tuple


def get_month_timestamp(month_str: str) -> Tuple[int, int]:
    """
    传入月份字符串（格式：YYYY-MM），返回该月的开始和结束时间戳（北京时间）

    Args:
        month_str: 月份字符串，例如 "2026-03"

    Returns:
        tuple: (开始时间戳, 结束时间戳)
    """
    # 解析年份和月份
    year, month = map(int, month_str.split("-"))

    # ===================== 开始时间戳 =====================
    # 当月1号 00:00:00（北京时间）
    start_dt = datetime(year, month, 1, 0, 0, 0)
    start_timestamp = int(time.mktime(start_dt.timetuple()))

    # ===================== 结束时间戳 =====================
    # 计算下个月1号，再减1秒，得到当月最后1秒 23:59:59
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    # 下个月1号 00:00:00
    next_month_start = datetime(next_year, next_month, 1)
    # 减去1秒，得到当月最后一秒
    end_dt = next_month_start.replace(microsecond=0)
    end_timestamp = int(time.mktime(end_dt.timetuple())) - 1

    return start_timestamp, end_timestamp


def get_day_timestamp(day_str: str) -> Tuple[int, int]:
    """
    传入日期字符串（格式：YYYY-MM-DD），返回当天的开始和结束时间戳（北京时间）

    Args:
        day_str: 日期字符串，例如 "2026-01-23"

    Returns:
        tuple: (开始时间戳, 结束时间戳)
    """
    # 解析日期
    dt = datetime.strptime(day_str, "%Y-%m-%d")

    # 当天 00:00:00 时间戳
    start_timestamp = int(time.mktime(dt.timetuple()))

    # 当天 23:59:59 时间戳 = 明天 00:00:00 - 1秒
    next_day = dt + timedelta(days=1)
    end_timestamp = int(time.mktime(next_day.timetuple())) - 1

    return start_timestamp, end_timestamp


def get_timestamp_from_str(time_str: str) -> int:
    """
    传入时间字符串（格式：YYYY-MM-DD），返回该时间的毫米秒级时间戳（北京时间）

    Args:
        time_str: 时间字符串，例如 "2026-01-23"

    Returns:
        毫秒秒级时间戳（如 1769097600000）
    """
    # 解析日期字符串
    dt = datetime.strptime(time_str, "%Y-%m-%d")
    # 转换为秒级时间戳，再乘以1000得到毫秒级时间戳
    timestamp_seconds = int(time.mktime(dt.timetuple()))
    return timestamp_seconds * 1000


def timestamp_to_str(ts: int, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    秒级时间戳 转 北京时间字符串

    Args:
        ts: 秒级时间戳（如 1769097600）
        fmt: 输出格式，默认：年-月-日 时:分:秒

    Returns:
        格式化后的时间字符串
    """
    # 转换为北京时间（本地时区，和你之前的工具统一）
    dt = datetime.fromtimestamp(ts)
    return dt.strftime(fmt)


def get_relative_month_timestamp(step: int) -> Tuple[int, int]:
    """
    新增方法：获取相对当前时间的月份时间戳
    参数规则：1=本月, 2=上月, 3=上上月, ..., 12=前11个月

    Args:
        step: 偏移步数，范围 1~12

    Returns:
        tuple: (开始时间戳, 结束时间戳)
    """
    # # 参数校验
    # if not isinstance(step, int) or step < 1 or step > 12:
    #     raise ValueError("参数必须是 1~12 之间的整数")

    # 获取当前北京时间
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    # 计算目标月份：step=1 → 当月，step=2 → 上月，以此类推
    target_month = current_month - (step - 1)
    target_year = current_year

    # 处理跨年场景（例如 1月 - 1 → 去年12月）
    while target_month < 1:
        target_year -= 1
        target_month += 12

    # 拼接月份字符串，调用原有方法
    month_str = f"{target_year}-{target_month:02d}"
    return get_month_timestamp(month_str)


def get_border_month_timestamp(month_pair: Tuple[int, int]) -> Tuple[int, int]:
    """
    获取两个月份的边界时间戳
    参数格式 (a, b):
        返回 => ( a月的最后一秒时间戳, b月的第一秒时间戳 )

    月份规则：
        1 = 本月
        2 = 上月
        3 = 上上月
        ...
        12 = 前11个月
    """
    a_month, b_month = month_pair

    # 获取 a 月的结束时间
    _, a_end = get_relative_month_timestamp(a_month)

    # 获取 b 月的开始时间
    b_start, _ = get_relative_month_timestamp(b_month)

    return b_start,a_end
# if __name__ == '__main__':
#     # t1=get_relative_month_timestamp(1)  # 2026-04 → (1774972800000, 1776700799000)
#     # t2=get_relative_month_timestamp(2)  # 2026-03 → (1772294400000, 1774972799000)
#     # t3=get_relative_month_timestamp(30)  # 2026-02 → (1769875200000, 1772294399000)
#     # print(t1,t2,t3)
#
#     print(get_border_month_timestamp((1,3)))
#     print(get_relative_month_timestamp(3))