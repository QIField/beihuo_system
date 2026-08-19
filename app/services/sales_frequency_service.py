# -*- coding:utf-8 -*-
# @Time    : 2026/08/19
# @Author  : AI Assistant
# @Project : beihuo_system
# @File    : sales_frequency_service.py
# @Software: trae-cn
# @Description: 销售订单历史频次计算服务

"""
销售订单历史频次计算服务

职责：
1. 根据日期范围从 sales_order_history 表中统计每个物料条码（frey_no）出现的次数
2. 筛选条件：order_type_name = '常规订单'
3. 时间过滤基于 create_date 秒级时间戳
4. 提供进程内缓存，避免重复查询数据库
5. 支持批量查询，提高性能
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from sqlalchemy import func

from app.models.orm_models.crm.sales_order_history import SalesOrderHistory
from app.utils.orm.session import orm_session
from app.core.cache_utils import get_default_cache


# 缓存实例：最大 512 个键，默认 5 分钟过期
_FREQUENCY_CACHE = get_default_cache(maxsize=512, default_ttl=300, thread_safe=True)

# 单次批量查询的条码数量上限，防止 SQL 参数过多
_MAX_BATCH_SIZE = 5000


def _normalize_date(date_str: str) -> str:
    """标准化日期字符串为 yyyy-MM-dd 格式"""
    if not date_str:
        return ''
    date_str = str(date_str).strip()
    # 兼容 yyyy/MM/dd 格式
    date_str = date_str.replace('/', '-')
    return date_str


def _date_to_timestamp(date_str: str, is_end: bool = False) -> Optional[int]:
    """
    将 yyyy-MM-dd 日期字符串转换为秒级时间戳

    :param date_str: 日期字符串
    :param is_end: 是否为结束日期，若是则转换为当天 23:59:59
    :return: 秒级时间戳，转换失败返回 None
    """
    date_str = _normalize_date(date_str)
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        if is_end:
            dt = dt.replace(hour=23, minute=59, second=59)
        else:
            dt = dt.replace(hour=0, minute=0, second=0)
        return int(dt.timestamp())
    except ValueError:
        return None


def _make_cache_key(barcodes: Tuple[str, ...], start_ts: int, end_ts: int) -> str:
    """生成缓存键"""
    # 条码数量可能很多，使用哈希减少 key 长度
    barcodes_key = '|'.join(sorted(set(barcodes))) if barcodes else 'ALL'
    return f"freq:{start_ts}:{end_ts}:{hash(barcodes_key)}"


def get_frequency_map(
    barcodes: List[str],
    start_date: str,
    end_date: str,
    use_cache: bool = True
) -> Tuple[Dict[str, int], Optional[str]]:
    """
    获取指定日期范围内每个物料条码的出现频次

    :param barcodes: 物料条码列表（frey_no 候选值）
    :param start_date: 开始日期 yyyy-MM-dd
    :param end_date: 结束日期 yyyy-MM-dd
    :param use_cache: 是否使用缓存，默认 True
    :return: (频次字典 {barcode: count}, 错误信息)
             错误信息为 None 表示成功
    """
    # 参数校验
    start_ts = _date_to_timestamp(start_date, is_end=False)
    end_ts = _date_to_timestamp(end_date, is_end=True)

    if start_ts is None or end_ts is None:
        return {}, '日期格式错误，请使用 yyyy-MM-dd 格式'

    if start_ts > end_ts:
        return {}, '开始日期不能大于结束日期'

    # 清理空条码
    barcodes = [str(b).strip() for b in barcodes if b and str(b).strip()]
    if not barcodes:
        return {}, None

    unique_barcodes = tuple(sorted(set(barcodes)))

    # 尝试读取缓存
    cache_key = _make_cache_key(unique_barcodes, start_ts, end_ts)
    if use_cache:
        cached = _FREQUENCY_CACHE.get(cache_key)
        if cached is not None:
            return cached, None

    try:
        frequency_map = _query_frequency_from_db(unique_barcodes, start_ts, end_ts)
    except Exception as e:
        return {}, f'查询频次数据失败: {str(e)}'

    # 写入缓存
    if use_cache:
        _FREQUENCY_CACHE.set(cache_key, frequency_map)

    return frequency_map, None


def _query_frequency_from_db(
    barcodes: Tuple[str, ...],
    start_ts: int,
    end_ts: int
) -> Dict[str, int]:
    """
    从数据库查询频次数据

    :param barcodes: 去重后的物料条码元组
    :param start_ts: 开始时间戳（秒）
    :param end_ts: 结束时间戳（秒）
    :return: 频次字典 {barcode: count}
    """
    result = {}

    with orm_session() as session:
        # 分批查询，避免 SQL IN 参数过多
        for i in range(0, len(barcodes), _MAX_BATCH_SIZE):
            batch = barcodes[i:i + _MAX_BATCH_SIZE]

            rows = (
                session.query(
                    SalesOrderHistory.frey_no,
                    func.count(SalesOrderHistory.orders_items_id).label('cnt')
                )
                .filter(
                    SalesOrderHistory.order_type_name == '常规订单',
                    SalesOrderHistory.create_date >= start_ts,
                    SalesOrderHistory.create_date <= end_ts,
                    SalesOrderHistory.frey_no.in_(batch)
                )
                .group_by(SalesOrderHistory.frey_no)
                .all()
            )

            for frey_no, cnt in rows:
                if frey_no:
                    result[frey_no] = result.get(frey_no, 0) + cnt

    # 未匹配到的条码默认频次为 0
    for barcode in barcodes:
        if barcode not in result:
            result[barcode] = 0

    return result


def enrich_data_with_frequency(
    data_list: List[Dict],
    barcode_field: str,
    start_date: str,
    end_date: str,
    frequency_field: str = 'frequency',
    use_cache: bool = True
) -> Tuple[List[Dict], Optional[str]]:
    """
    为数据列表添加频次字段

    :param data_list: 原始数据列表
    :param barcode_field: 物料条码字段名
    :param start_date: 开始日期 yyyy-MM-dd
    :param end_date: 结束日期 yyyy-MM-dd
    :param frequency_field: 频次字段名，默认 'frequency'
    :param use_cache: 是否使用缓存
    :return: (添加频次后的数据列表, 错误信息)
    """
    if not data_list or not start_date or not end_date:
        # 没有数据或没有日期范围，直接返回原数据
        return data_list, None

    barcodes = [item.get(barcode_field) for item in data_list if item.get(barcode_field)]
    if not barcodes:
        # 没有条码，给每条数据设置频次为 0
        for item in data_list:
            item[frequency_field] = 0
        return data_list, None

    frequency_map, error = get_frequency_map(barcodes, start_date, end_date, use_cache)
    if error:
        return data_list, error

    for item in data_list:
        barcode = item.get(barcode_field)
        item[frequency_field] = frequency_map.get(barcode, 0) if barcode else 0

    return data_list, None
