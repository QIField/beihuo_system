#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VIN 车辆信息补全服务
"""

import logging
from bs4 import BeautifulSoup

from app.utils.database_connection import db_cursor
from app.utils.ks_auto_bill_model import COMPANIES, get_company_key
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
    """构建动态 UPDATE 语句，补全到数据时更新 engine/chassis，并始终标记为已查询"""
    fields = []
    values = []

    if parsed.get('engine'):
        fields.append('engine = %s')
        values.append(parsed['engine'])
    if parsed.get('chassis'):
        fields.append('chassis = %s')
        values.append(parsed['chassis'])

    fields.append('status = %s')
    values.append('已查询')

    sql = f"UPDATE vin_vehicle_info SET {', '.join(fields)} WHERE id = %s"
    values.append(record_id)
    return sql, tuple(values)


def _mark_record_queried(cursor, record_id, parsed=None):
    """将记录标记为已查询，用于异常或空结果场景"""
    sql, params = _build_update_sql(record_id, parsed or {})
    cursor.execute(sql, params)
    return cursor.rowcount


def _is_daily_limit_reached(response):
    """判断响应是否表示当日 EPC 查询次数已达上限"""
    if response is None or response.status_code != 200:
        return False
    text = response.text or ''
    return '当天查询EPC次数已达上限' in text or 'var status = "415"' in text


def _validate_vin_full_info(vin_code, engine, chassis):
    """验证 VIN 完整信息字段是否均非空"""
    return bool(vin_code and str(vin_code).strip() and
                engine and str(engine).strip() and
                chassis and str(chassis).strip())


def _fetch_crm_full_vin_records(cursor):
    """
    从 CRM 询价表提取近 5 天 VIN、发动机、底盘均不为空的数据
    """
    sql = """
        SELECT DISTINCT vin AS vin_code, engine, chassis
        FROM crmapp_ks_inquiry_detail
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 5 DAY)
          AND vin IS NOT NULL AND vin != ''
          AND engine IS NOT NULL AND engine != ''
          AND chassis IS NOT NULL AND chassis != ''
    """
    cursor.execute(sql)
    return cursor.fetchall()


def _merge_vin_full_info(cursor, newly_completed=None):
    """
    将 CRM 近 5 天数据与本次同步新补全的 VIN 数据合并去重后，
    插入 vin_vehicle_full_info 表。

    去重规则：以 VIN 为唯一键，CRM 数据优先级高于 vin_vehicle_info。
    插入使用 INSERT IGNORE，遇到重复 VIN 时保留已有记录。

    :param newly_completed: 本次同步中成功补全的 (vin_code, engine, chassis) 集合
    """
    vin_map = {}

    # CRM 数据优先级高，先放入
    crm_records = _fetch_crm_full_vin_records(cursor)
    for row in crm_records:
        vin_code = row['vin_code']
        engine = row['engine']
        chassis = row['chassis']
        if _validate_vin_full_info(vin_code, engine, chassis):
            vin_map[vin_code] = (vin_code, engine, chassis, 'ks_inquiry')

    # 本次同步新补全的数据补充
    for vin_code, engine, chassis in (newly_completed or set()):
        if vin_code not in vin_map and _validate_vin_full_info(vin_code, engine, chassis):
            vin_map[vin_code] = (vin_code, engine, chassis, 'vin_vehicle_info')

    if not vin_map:
        return 0

    values = list(vin_map.values())
    sql = """
        INSERT IGNORE INTO vin_vehicle_full_info (vin_code, engine, chassis, source)
        VALUES (%s, %s, %s, %s)
    """
    cursor.executemany(sql, values)
    return cursor.rowcount


def _fetch_pending_records(cursor, limit=100):
    """查询待补全的记录，按创建时间倒序，跳过已查询过的记录"""
    sql = """
        SELECT id, vin_code FROM vin_vehicle_info
        WHERE (engine IS NULL OR engine = '' OR chassis IS NULL OR chassis = '')
          AND (status IS NULL OR status != '已查询')
        ORDER BY created_at DESC
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
    """从 qpl_quote_result_v2 提取近两天内的 vin_code"""
    sql = """
        SELECT DISTINCT vin_code
        FROM qpl_quote_result_v2
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 2 DAY)
          AND vin_code IS NOT NULL AND vin_code != ''
    """
    cursor.execute(sql)
    return cursor.fetchall()


def _fetch_weixin_vin_records(cursor):
    """从 weixin_decoding_vin 提取近两天内的 vin"""
    sql = """
        SELECT DISTINCT vin
        FROM weixin_decoding_vin
        WHERE creation_date >= DATE_SUB(NOW(), INTERVAL 2 DAY)
          AND vin IS NOT NULL AND vin != ''
    """
    cursor.execute(sql)
    return cursor.fetchall()


def _filter_existing_full_vins(cursor, vin_codes):
    """
    从 vin_vehicle_full_info 中查询已存在完整信息的 VIN 集合

    :param cursor: 数据库游标
    :param vin_codes: VIN 列表
    :return: 已存在完整信息的 VIN 集合
    """
    if not vin_codes:
        return set()

    placeholders = ', '.join(['%s'] * len(vin_codes))
    sql = f"""
        SELECT DISTINCT vin_code
        FROM vin_vehicle_full_info
        WHERE vin_code IN ({placeholders})
    """
    cursor.execute(sql, tuple(vin_codes))
    return {row['vin_code'] for row in cursor.fetchall()}


def _merge_into_vin_vehicle_info(cursor, crm_records, qpl_records, weixin_records):
    """
    将数据整合到 vin_vehicle_info，利用唯一索引 uk_vin_code 去重。

    整合前会先从 vin_vehicle_full_info 中匹配：
      - 已存在完整信息的 VIN 直接跳过，不再放入待补全表；
      - 不存在的 VIN 才写入 vin_vehicle_info 进行后续补全。
    """
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

    for row in weixin_records:
        vin = row['vin']
        if vin not in vin_map:
            vin_map[vin] = (vin, None, None)

    total_extracted = len(vin_map)
    if not vin_map:
        logger.info("[VIN整合] 三表均无新增VIN，跳过匹配")
        return 0

    # 与 vin_vehicle_full_info 精确匹配，过滤已完整记录
    existing_full_vins = _filter_existing_full_vins(cursor, list(vin_map.keys()))
    for vin in existing_full_vins:
        vin_map.pop(vin, None)

    skipped_count = len(existing_full_vins)
    new_count = len(vin_map)

    logger.info(
        f"[VIN匹配] 三表共提取 {total_extracted} 条 VIN，"
        f"其中 {skipped_count} 条已在 vin_vehicle_full_info 存在完整信息并跳过，"
        f"剩余 {new_count} 条待写入 vin_vehicle_info"
    )

    if not vin_map:
        return 0

    values = list(vin_map.values())
    sql = "INSERT IGNORE INTO vin_vehicle_info (vin_code, engine, chassis) VALUES (%s, %s, %s)"
    cursor.executemany(sql, values)
    inserted_count = cursor.rowcount

    logger.info(f"[VIN整合] 实际新增 {inserted_count} 条到 vin_vehicle_info")
    return inserted_count


def _process_single_record(cursor, client, key, record, stats, newly_completed):
    """
    处理单条 VIN 记录。

    返回值：
      - 'ok'：正常处理并标记为已查询
      - 'limit_reached'：触发 EPC 日查询上限，需要停止当前 key
      - 函数内部已处理异常，不会向外抛错

    若本次成功补全了 VIN、发动机、底盘三者，才会将记录加入 newly_completed。
    """
    stats['total'] += 1
    record_id = record['id']
    vin_code = record['vin_code']

    parsed = {}
    try:
        response = client.fetch_catalog_response(vin_code)
        if response is None:
            logger.warning(f"[VIN补全][{key}] 获取响应失败，仅标记已查询: {vin_code}")
            _mark_record_queried(cursor, record_id)
        elif _is_daily_limit_reached(response):
            logger.warning(
                f"[VIN补全][{key}] 当日EPC查询次数已达上限，停止使用该key，"
                f"当前记录 {vin_code} 不标记为已查询，留给下一个key重试"
            )
            return 'limit_reached'
        elif response.status_code != 200:
            logger.warning(f"[VIN补全][{key}] 响应异常 status={response.status_code}，仅标记已查询: {vin_code}")
            _mark_record_queried(cursor, record_id)
        else:
            parsed = parse_catalog_html(response.text)
            if not parsed:
                body_preview = (response.text or '')[:1000].replace('\n', ' ')
                logger.warning(
                    f"[VIN补全][{key}] {vin_code} 解析为空，"
                    f"status={response.status_code} body_len={len(response.text or '')} "
                    f"body_preview={body_preview!r}"
                )
            else:
                logger.info(
                    f"[VIN补全][{key}] {vin_code} 解析成功，"
                    f"status={response.status_code} body_len={len(response.text or '')} "
                    f"parsed={parsed}"
                )
            _mark_record_queried(cursor, record_id, parsed)

        stats['updated'] += cursor.rowcount

        engine = parsed.get('engine')
        chassis = parsed.get('chassis')
        if _validate_vin_full_info(vin_code, engine, chassis):
            newly_completed.add((vin_code, engine, chassis))
        else:
            logger.info(
                f"[VIN补全][{key}] {vin_code} 信息不完整，不加入完整信息表，"
                f"parsed={parsed}"
            )

        logger.info(f"[VIN补全][{key}] {vin_code} engine={engine} chassis={chassis}")
        return 'ok'
    except Exception as e:
        logger.exception(f"[VIN补全][{key}] 处理异常，标记为已查询: {vin_code}, 错误={e}")
        try:
            _mark_record_queried(cursor, record_id)
            stats['updated'] += cursor.rowcount
        except Exception as inner_e:
            logger.error(f"[VIN补全][{key}] 异常后标记状态失败: {inner_e}")
        return 'ok'


def _process_key_records(key, records, stats):
    """
    使用单个 key 处理一批待补全记录，单独一个事务。

    事务边界：本函数内部自行创建并提交/回滚 db_cursor。

    返回本次成功补全的 (vin_code, engine, chassis) 集合。
    """
    newly_completed = set()
    if not records:
        logger.info(f"[VIN补全][{key}] 没有待补全记录，跳过")
        return newly_completed

    with db_cursor(dict_cursor=True) as cursor:
        client = VinVehicleInfoApiClient(key=key)
        try:
            logger.info(f"[VIN补全][{key}] 开始处理 {len(records)} 条")
            for record in records:
                result = _process_single_record(cursor, client, key, record, stats, newly_completed)
                if result == 'limit_reached':
                    break
        finally:
            client.close()

    return newly_completed


def run_vin_vehicle_info_sync(limit=100):
    """
    执行 VIN 车辆信息补全

    流程：
      1. 从 crmapp_ks_inquiry_detail、qpl_quote_result_v2 和 weixin_decoding_vin 提取近两天数据
      2. 整合写入 vin_vehicle_info（利用 uk_vin_code 去重）
      3. 使用所有配置的公司 key 轮流爬虫补全
      4. 每个 key 按 created_at 倒序处理 limit 条未查询记录
      5. 无论是否补全到数据，都将记录标记为 status = '已查询'
      6. 当某个 key 触发 EPC 日查询上限时，自动跳过该 key，使用下一个 key

    事务说明：
      - Step 1、Step 2（每个 key）、Step 3 各自拥有独立事务；
      - Step 2 中每条记录异常被隔离，不会影响同 key 其他记录；
      - 单个 key 失败不会导致其他 key 已处理数据回滚。

    性能说明：
      - Step 3 只合并 CRM 近 5 天完整数据 + 本次同步新补全的 VIN，避免全量扫描 vin_vehicle_info。

    :param limit: 每个 key 最多处理的条数，默认 100
    :return: dict 统计信息
    """
    stats = {'total': 0, 'updated': 0, 'merged': 0, 'full_info_merged': 0}

    # Step 1: 数据提取与整合（独立事务）
    with db_cursor(dict_cursor=True) as cursor:
        logger.info("[VIN整合] 开始从数据源提取数据...")
        crm_records = _fetch_crm_inquiry_records(cursor)
        qpl_records = _fetch_qpl_quote_records(cursor)
        weixin_records = _fetch_weixin_vin_records(cursor)

        merged_count = _merge_into_vin_vehicle_info(cursor, crm_records, qpl_records, weixin_records)
        stats['merged'] = merged_count
        logger.info(
            f"[VIN整合] CRM={len(crm_records)}条, QPL={len(qpl_records)}条, 微信={len(weixin_records)}条, 新增={merged_count}条"
        )

    # Step 2: 使用所有配置 key 轮流爬虫补全（每个 key 独立事务）
    keys = [get_company_key(c) for c in COMPANIES]
    newly_completed_all = set()
    for key in keys:
        with db_cursor(dict_cursor=True) as cursor:
            records = _fetch_pending_records(cursor, limit)
            newly_completed = _process_key_records(key, records, stats)
            newly_completed_all.update(newly_completed)

    # Step 3: 合并完整 VIN 信息到 vin_vehicle_full_info（独立事务）
    with db_cursor(dict_cursor=True) as cursor:
        try:
            logger.info(
                f"[VIN完整信息] 开始合并 CRM 近5天数据与本次新补全 {len(newly_completed_all)} 条数据..."
            )
            full_info_count = _merge_vin_full_info(cursor, newly_completed_all)
            stats['full_info_merged'] = full_info_count
            logger.info(f"[VIN完整信息] 合并完成，新增={full_info_count}条")
        except Exception as e:
            logger.error(f"[VIN完整信息] 合并失败: {e}")
            raise

    logger.info(
        f"[VIN补全完成] 整合={stats['merged']} 处理={stats['total']} "
        f"更新={stats['updated']} 完整信息合并={stats['full_info_merged']}"
    )

    return stats
