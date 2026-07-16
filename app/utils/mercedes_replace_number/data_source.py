# -*- coding: utf-8 -*-
"""
多数据源 OE 查询
"""

from datetime import date
from typing import Set

from pymysql.cursors import DictCursor

from app.utils.database_connection import get_db_connection
from app.utils.logger_config import get_task_logger
from .config import DEFAULT_COMPANY, TASK_NAME


logger = get_task_logger(TASK_NAME)


def _format_date_range(target_date: date):
    start = f"{target_date.strftime('%Y-%m-%d')} 00:00:00"
    end = f"{target_date.strftime('%Y-%m-%d')} 23:59:59"
    return start, end


def fetch_wechat_oe_codes(target_date: date, company: str = DEFAULT_COMPANY) -> Set[str]:
    """
    查询 wechat_daily_quote_detail 表中 create_date 在 target_date 范围内的 oe_code。
    该表无 company 字段，company 仅用于日志。
    """
    start, end = _format_date_range(target_date)
    sql = """
        SELECT DISTINCT oe_code
        FROM wechat_daily_quote_detail
        WHERE create_date >= %s
          AND create_date <= %s
    """
    codes = _fetch_single_column(sql, (start, end))
    logger.info(f"[{company}] wechat_daily_quote_detail 获取到 {len(codes)} 个 OE")
    return codes


def fetch_crmapp_oe_codes(target_date: date, company: str = DEFAULT_COMPANY) -> Set[str]:
    """
    查询 crmapp_ks_inquiry_detail 表中 quote_date = target_date
    且 resolve_parts_num 以 A 开头的数据。
    """
    date_str = target_date.strftime('%Y-%m-%d')
    sql = """
        SELECT DISTINCT resolve_parts_num
        FROM crmapp_ks_inquiry_detail
        WHERE quote_date = %s
          AND resolve_parts_num LIKE %s
          AND company = %s
    """
    codes = _fetch_single_column(sql, (date_str, 'A%', company))
    logger.info(f"[{company}] crmapp_ks_inquiry_detail 获取到 {len(codes)} 个 OE")
    return codes


def collect_oe_codes(target_date: date, company: str = DEFAULT_COMPANY) -> Set[str]:
    """合并两个数据源并去重。"""
    wechat_codes = fetch_wechat_oe_codes(target_date, company)
    crmapp_codes = fetch_crmapp_oe_codes(target_date, company)
    merged = wechat_codes | crmapp_codes
    logger.info(f"[{company}] 合并去重后共 {len(merged)} 个 OE")
    return merged


def _fetch_single_column(sql: str, params: tuple) -> Set[str]:
    conn = None
    result = set()
    try:
        conn = get_db_connection()
        with conn.cursor(DictCursor) as cursor:
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                value = list(row.values())[0]
                if value:
                    result.add(str(value).strip())
    except Exception:
        logger.exception(f"SQL 查询失败: {sql}")
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    return result
