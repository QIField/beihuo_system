# -*- coding:utf-8 -*-
# @Time    : 2026/4/16 16:45
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : time_conversion_util.py
# @Software: PyCharm
import time
from datetime import datetime, timedelta


def get_month_timestamp(month_str: str) -> tuple[int, int]:
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


def get_day_timestamp(day_str: str) -> tuple[int, int]:
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


# # 测试示例
if __name__ == '__main__':
    # 传入 2026-03
    # start_ts, end_ts = get_month_timestamp("2026-01")
    # print(f"开始时间戳：{start_ts}")
    # print(f"结束时间戳：{end_ts}")

    # start_ts, end_ts = get_day_timestamp("2026-01-20")
    # print(f"开始时间戳：{start_ts}")
    # print(f"结束时间戳：{end_ts}")

    # 测试你之前的时间戳
    print(timestamp_to_str(1769097600))  # 2026-01-23 00:00:00
    print(timestamp_to_str(1769183999))  # 2026-01-23 23:59:59
    print(timestamp_to_str(1772294400))  # 2026-03-01 00:00:00
    print(timestamp_to_str(1774972799))  # 2026-03-31 23:59:59

    # 只需要日期
    print(timestamp_to_str(1769097600, "%Y-%m-%d"))  # 2026-01-23