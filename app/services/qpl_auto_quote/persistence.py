#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价 · 落库层（三层表）

qpl_order         订单 upsert
qpl_order_item    明细 upsert（不触碰状态字段）+ 状态机更新 + 手动重试重置
qpl_quote_attempt 尝试流水 append-only

设计要点：
1. upsert_items 重复入库同一明细时只更新基础信息，绝不重置状态机字段，
   避免 P1 每轮拉详情把已报价/已失败明细打回 pending
2. mark_item_failed 的冷却与重试耗尽在 SQL 内用 IF 判定，单条 SQL 原子完成
3. record_attempt 只插不改，保留每步请求/响应快照供追溯
"""

import json
from datetime import datetime, timedelta

from app.utils.database_connection import get_db_connection, get_dict_cursor
from app.utils.qpl_auto_bill.qpl_config import qpl_log
from app.services.qpl_auto_quote.constants import (
    STATUS_PENDING,
    COOLING_HOURS,
    MAX_RETRY,
)


# ============================================================================
# 订单表
# ============================================================================

def upsert_order(company, order):
    """
    订单 upsert（uk: company + supplier_enquiry_no）。

    Args:
        order: dict，键与 qpl_order 列名一致（不含 id/created_at/updated_at）
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO qpl_order (
                    company, supplier_enquiry_no, qpl_enquiry_no, tid, car_brand,
                    car_type5, vin_code, shop_name, trader_name, user_name, user_phone,
                    demand_status, accept_status, multi_quote_gray,
                    enquiry_time, first_handle_time, last_handle_time
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    qpl_enquiry_no = VALUES(qpl_enquiry_no),
                    tid = VALUES(tid),
                    car_brand = VALUES(car_brand),
                    car_type5 = VALUES(car_type5),
                    vin_code = VALUES(vin_code),
                    shop_name = VALUES(shop_name),
                    trader_name = VALUES(trader_name),
                    user_name = VALUES(user_name),
                    user_phone = VALUES(user_phone),
                    demand_status = VALUES(demand_status),
                    accept_status = VALUES(accept_status),
                    multi_quote_gray = VALUES(multi_quote_gray),
                    enquiry_time = VALUES(enquiry_time),
                    last_handle_time = VALUES(last_handle_time)
            """, (
                company,
                order.get('supplier_enquiry_no'),
                order.get('qpl_enquiry_no'),
                order.get('tid'),
                order.get('car_brand'),
                order.get('car_type5'),
                order.get('vin_code'),
                order.get('shop_name'),
                order.get('trader_name'),
                order.get('user_name'),
                order.get('user_phone'),
                order.get('demand_status'),
                order.get('accept_status'),
                order.get('multi_quote_gray', 0),
                order.get('enquiry_time'),
                order.get('first_handle_time'),
                order.get('last_handle_time'),
            ))
        conn.commit()
    finally:
        conn.close()


def update_order_progress(company, enquiry_no):
    """
    每单完成后聚合更新明细进度（item_total / item_quoted / last_handle_time）。
    首轮处理时间由 INSERT 时 first_handle_time 写入，此处不覆盖。
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE qpl_order o
                SET o.item_total = (SELECT COUNT(*) FROM qpl_order_item i
                                    WHERE i.company = o.company
                                      AND i.supplier_enquiry_no = o.supplier_enquiry_no),
                    o.item_quoted = (SELECT COUNT(*) FROM qpl_order_item i
                                     WHERE i.company = o.company
                                       AND i.supplier_enquiry_no = o.supplier_enquiry_no
                                       AND i.status = 'quoted'),
                    o.last_handle_time = NOW()
                WHERE o.company = %s AND o.supplier_enquiry_no = %s
            """, (company, enquiry_no))
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# 明细表
# ============================================================================

def upsert_items(company, enquiry_no, items):
    """
    明细批量 upsert（uk: company + enquiry_item_id）。

    ON DUPLICATE KEY UPDATE 仅更新基础信息字段，不含 status/fail/retry——
    重复入库不重置状态机。

    Args:
        items: 明细 dict 列表，键与 qpl_order_item 列名对应
    """
    if not items:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO qpl_order_item (
                    company, supplier_enquiry_no, supplier_demand_id, enquiry_item_id,
                    item_name, item_nick_names, item_oe, item_amount, assembly_quantity,
                    item_quality_list, sale_category_name, car_brand
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    supplier_demand_id = VALUES(supplier_demand_id),
                    item_name = VALUES(item_name),
                    item_nick_names = VALUES(item_nick_names),
                    item_oe = VALUES(item_oe),
                    item_amount = VALUES(item_amount),
                    assembly_quantity = VALUES(assembly_quantity),
                    item_quality_list = VALUES(item_quality_list),
                    sale_category_name = VALUES(sale_category_name)
            """
            for item in items:
                cursor.execute(sql, (
                    company,
                    enquiry_no,
                    item.get('supplier_demand_id'),
                    item.get('enquiry_item_id'),
                    item.get('item_name'),
                    item.get('item_nick_names'),
                    item.get('item_oe'),
                    item.get('item_amount', 1),
                    item.get('assembly_quantity', 1),
                    item.get('item_quality_list'),
                    item.get('sale_category_name'),
                    item.get('car_brand'),
                ))
        conn.commit()
        qpl_log(f"[{company}] 明细入库 {len(items)} 条", order_no=enquiry_no)
    finally:
        conn.close()


def mark_item_quoted(company, item_id, quote_source=None, matched_brand=None,
                     item_sell_price=None, delivery_aging=None, parts_no=None,
                     item_quality=None):
    """报价成功：写入终态 quoted 及最新报价结果冗余字段"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE qpl_order_item
                SET status = 'quoted', next_retry_time = NULL, last_attempt_time = NOW(),
                    quote_source = %s, matched_brand = %s, item_sell_price = %s,
                    delivery_aging = %s, parts_no = %s, item_quality = %s
                WHERE company = %s AND enquiry_item_id = %s
            """, (quote_source, matched_brand, item_sell_price, delivery_aging,
                  parts_no, item_quality, company, item_id))
        conn.commit()
    finally:
        conn.close()


def mark_item_failed(company, item_id, fail_stage, fail_reason, is_temp,
                     quote_source=None, matched_brand=None):
    """
    报价失败：按状态机写入失败终态或临时失败。

    is_temp=True  → status = IF(retry_count+1 >= 3, 'failed_biz', 'failed_temp')，
                    retry_count+1，冷却期未耗尽时 next_retry_time = NOW()+4h
    is_temp=False → 直接终态 failed_biz，next_retry_time 置 NULL
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if is_temp:
                cursor.execute("""
                    UPDATE qpl_order_item
                    SET retry_count = retry_count + 1,
                        status = IF(retry_count + 1 >= %s, 'failed_biz', 'failed_temp'),
                        next_retry_time = IF(retry_count + 1 >= %s, NULL,
                                             DATE_ADD(NOW(), INTERVAL %s HOUR)),
                        last_attempt_time = NOW(),
                        fail_stage = %s, fail_reason = %s,
                        quote_source = %s, matched_brand = %s
                    WHERE company = %s AND enquiry_item_id = %s
                """, (MAX_RETRY, MAX_RETRY, COOLING_HOURS,
                      fail_stage, fail_reason, quote_source, matched_brand,
                      company, item_id))
            else:
                cursor.execute("""
                    UPDATE qpl_order_item
                    SET status = 'failed_biz', next_retry_time = NULL,
                        last_attempt_time = NOW(),
                        fail_stage = %s, fail_reason = %s,
                        quote_source = %s, matched_brand = %s
                    WHERE company = %s AND enquiry_item_id = %s
                """, (fail_stage, fail_reason, quote_source, matched_brand,
                      company, item_id))
        conn.commit()
    finally:
        conn.close()


def reset_item_for_retry(company, item_id):
    """手动重试：终态明细打回 pending，重试计数清零，冷却立即到期"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE qpl_order_item
                SET status = 'pending', retry_count = 0, next_retry_time = NOW()
                WHERE company = %s AND enquiry_item_id = %s
            """, (company, item_id))
        conn.commit()
        qpl_log(f"[{company}] 手动重试重置明细 {item_id} 为 pending")
    finally:
        conn.close()


def fetch_pending_items(company):
    """
    取本轮待处理明细（R2/P2 数据源）：
    status IN (pending, failed_temp) 且冷却到期（next_retry_time 为空或 <= NOW），
    JOIN 订单表带出报价所需订单级字段。

    Returns:
        list[dict]（DictCursor）
    """
    conn = get_db_connection()
    try:
        cursor = get_dict_cursor(conn)
        try:
            cursor.execute("""
                SELECT i.*, o.tid, o.car_type5, o.vin_code, o.demand_status
                FROM qpl_order_item i
                JOIN qpl_order o
                  ON o.company = i.company AND o.supplier_enquiry_no = i.supplier_enquiry_no
                WHERE i.company = %s
                  AND i.status IN ('pending', 'failed_temp')
                  AND (i.next_retry_time IS NULL OR i.next_retry_time <= NOW())
                ORDER BY o.enquiry_time, i.id
            """, (company,))
            return cursor.fetchall()
        finally:
            cursor.close()
    finally:
        conn.close()


def fetch_item_statuses(company, item_ids):
    """
    查询明细本地状态（P2 过滤依据）。

    Returns:
        dict: {enquiry_item_id: {'status': str, 'next_retry_time': datetime|None}}
    """
    if not item_ids:
        return {}
    conn = get_db_connection()
    try:
        cursor = get_dict_cursor(conn)
        try:
            placeholders = ','.join(['%s'] * len(item_ids))
            cursor.execute(
                f"SELECT enquiry_item_id, status, next_retry_time "
                f"FROM qpl_order_item "
                f"WHERE company = %s AND enquiry_item_id IN ({placeholders})",
                (company, *item_ids),
            )
            return {
                row['enquiry_item_id']: {
                    'status': row['status'],
                    'next_retry_time': row['next_retry_time'],
                }
                for row in cursor.fetchall()
            }
        finally:
            cursor.close()
    finally:
        conn.close()


# ============================================================================
# 尝试流水表（append-only）
# ============================================================================

def record_attempt(company, enquiry_no, item_id, round_id, action, result,
                   quote_source=None, fail_stage=None, fail_reason=None,
                   request_snapshot=None, response_snapshot=None):
    """
    追加一条尝试流水（只插不改）。

    request_snapshot / response_snapshot 为 dict 时序列化为 JSON 字符串存储。
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO qpl_quote_attempt (
                    company, supplier_enquiry_no, enquiry_item_id, round_id,
                    action, result, quote_source, fail_stage, fail_reason,
                    request_snapshot, response_snapshot
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                company, enquiry_no, item_id, round_id,
                action, result, quote_source, fail_stage, fail_reason,
                _to_json(request_snapshot), _to_json(response_snapshot),
            ))
        conn.commit()
    finally:
        conn.close()


def _to_json(snapshot):
    """dict 序列化为 JSON 字符串，其余原样返回（None/字符串）"""
    if snapshot is None or isinstance(snapshot, str):
        return snapshot
    return json.dumps(snapshot, ensure_ascii=False)


def make_round_id(company, now=None):
    """生成轮次上下文标识：YYYYMMDDHHMMSS_company"""
    now = now or datetime.now()
    return f"{now.strftime('%Y%m%d%H%M%S')}_{company}"


def next_cooling_time(now=None):
    """临时失败的下一次重试时间（冷却 COOLING_HOURS 小时）"""
    return (now or datetime.now()) + timedelta(hours=COOLING_HOURS)
