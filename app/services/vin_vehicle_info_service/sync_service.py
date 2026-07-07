#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VIN 车辆信息补全服务
"""

import logging
from bs4 import BeautifulSoup

from app.utils.database_connection import db_cursor
from .api_client import VinVehicleInfoApiClient


logger = logging.getLogger('vin_vehicle_info_sync')


# label → (目标字段, 是否仅作为备选)
_LABEL_HANDLERS = {
    '发动机': ('engine', False),
    '发动机编码': ('engine', True),
    '发动机编号': ('engine', True),
    '底盘': ('chassis', False),
    '车型编码': ('chassis', True),
}


def parse_catalog_html(html):
    """
    解析 catalog HTML，提取发动机和底盘信息
    优先级：发动机 > 发动机编码；底盘 > 车型编码
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = {}

    for row in soup.find_all('tr'):
        tds = row.find_all('td')
        if len(tds) < 2:
            continue

        label = tds[0].get_text(strip=True)
        value = tds[1].get_text(strip=True)

        handler = _LABEL_HANDLERS.get(label)
        if handler:
            key, fallback = handler
            if not fallback or key not in result:
                result[key] = value

    return result


def _build_update_sql(record_id, parsed):
    """构建动态 UPDATE 语句"""
    fields = []
    values = []

    if parsed.get('engine'):
        fields.append('engine = %s')
        values.append(parsed['engine'])
    if parsed.get('chassis'):
        fields.append('chassis = %s')
        values.append(parsed['chassis'])

    if not fields:
        return None, None

    sql = f"UPDATE vin_vehicle_info SET {', '.join(fields)} WHERE id = %s"
    values.append(record_id)
    return sql, tuple(values)


def _fetch_pending_records(cursor, limit=50):
    """查询待补全的记录"""
    sql = """
        SELECT id, vin_code FROM vin_vehicle_info
        WHERE engine IS NULL OR engine = '' OR chassis IS NULL OR chassis = ''
        LIMIT %s
    """
    cursor.execute(sql, (limit,))
    return cursor.fetchall()


def run_vin_vehicle_info_sync(limit=50):
    """
    执行 VIN 车辆信息补全

    :param limit: 最多处理条数，默认 50
    :return: dict 统计信息
    """
    client = VinVehicleInfoApiClient()
    stats = {'total': 0, 'updated': 0}

    try:
        with db_cursor(dict_cursor=True) as cursor:
            records = _fetch_pending_records(cursor, limit)

            for record in records:
                stats['total'] += 1
                record_id = record['id']
                vin_code = record['vin_code']

                html = client.fetch_catalog_html(vin_code)
                parsed = parse_catalog_html(html)

                sql, params = _build_update_sql(record_id, parsed)
                if sql:
                    cursor.execute(sql, params)
                    stats['updated'] += cursor.rowcount

                logger.info(f"[VIN补全] {vin_code} engine={parsed.get('engine')} chassis={parsed.get('chassis')}")

    finally:
        client.close()

    logger.info(f"[VIN补全完成] 处理={stats['total']} 更新={stats['updated']}")
    return stats
