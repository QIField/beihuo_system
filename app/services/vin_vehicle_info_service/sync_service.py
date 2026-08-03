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


def _fetch_crm_inquiry_records(cursor):
    """从 crmapp_ks_inquiry_detail 提取近两天 engine 或 chassis 为空的记录"""
    sql = """
        SELECT DISTINCT vin, engine, chassis
        FROM crmapp_ks_inquiry_detail
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 2 DAY)
          AND vin IS NOT NULL AND vin != ''
          AND (engine IS NULL OR engine = '' OR chassis IS NULL OR chassis = '')
    """
    cursor.execute(sql)
    return cursor.fetchall()


def _fetch_qpl_quote_records(cursor):
    """从 qpl_quote_record 提取近两天内的 vin_code"""
    sql = """
        SELECT DISTINCT vin_code
        FROM qpl_quote_record
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 2 DAY)
          AND vin_code IS NOT NULL AND vin_code != ''
    """
    cursor.execute(sql)
    return cursor.fetchall()


def _merge_into_vin_vehicle_info(cursor, crm_records, qpl_records):
    """将数据整合到 vin_vehicle_info，利用唯一索引 uk_vin_code 去重"""
    vin_map = {}
    for row in crm_records:
        vin = row['vin']
        engine = row.get('engine') or None
        chassis = row.get('chassis') or None
        vin_map[vin] = (vin, engine, chassis)

    for row in qpl_records:
        vin = row['vin_code']
        if vin not in vin_map:
            vin_map[vin] = (vin, None, None)

    if not vin_map:
        return 0

    values = list(vin_map.values())
    sql = "INSERT IGNORE INTO vin_vehicle_info (vin_code, engine, chassis) VALUES (%s, %s, %s)"
    cursor.executemany(sql, values)
    return cursor.rowcount


def run_vin_vehicle_info_sync(limit=50):
    """
    执行 VIN 车辆信息补全

    流程：
      1. 从 crmapp_ks_inquiry_detail 和 qpl_quote_record 提取近两天数据
      2. 整合写入 vin_vehicle_info（利用 uk_vin_code 去重）
      3. 对 engine/chassis 为空的记录执行爬虫补全

    :param limit: 爬虫最多处理条数，默认 50
    :return: dict 统计信息
    """
    client = VinVehicleInfoApiClient()
    stats = {'total': 0, 'updated': 0, 'merged': 0}

    try:
        with db_cursor(dict_cursor=True) as cursor:
            # Step 1: 数据提取与整合
            logger.info("[VIN整合] 开始从数据源提取数据...")
            crm_records = _fetch_crm_inquiry_records(cursor)
            qpl_records = _fetch_qpl_quote_records(cursor)

            merged_count = _merge_into_vin_vehicle_info(cursor, crm_records, qpl_records)
            stats['merged'] = merged_count
            logger.info(
                f"[VIN整合] CRM={len(crm_records)}条, QPL={len(qpl_records)}条, 新增={merged_count}条"
            )

            # Step 2: 爬虫更新
            records = _fetch_pending_records(cursor, limit)

            for record in records:
                stats['total'] += 1
                record_id = record['id']
                vin_code = record['vin_code']

                html = client.fetch_catalog_html(vin_code)
                if html is None:
                    logger.warning(f"[VIN补全] 获取HTML失败，跳过: {vin_code}")
                    continue
                parsed = parse_catalog_html(html)

                sql, params = _build_update_sql(record_id, parsed)
                if sql:
                    cursor.execute(sql, params)
                    stats['updated'] += cursor.rowcount

                logger.info(f"[VIN补全] {vin_code} engine={parsed.get('engine')} chassis={parsed.get('chassis')}")

    finally:
        client.close()

    logger.info(f"[VIN补全完成] 整合={stats['merged']} 处理={stats['total']} 更新={stats['updated']}")
    return stats
