# -*- coding:utf-8 -*-
"""
OE军备统计月度汇总刷新服务

将 crmapp_ks_inquiry_detail 明细按自然月预汇总到两张汇总表：
  1. ks_inquiry_oe_monthly_summary           OE军备统计主表（月+门店+OE+车辆品牌）
  2. ks_inquiry_customer_by_oe_monthly_summary  OE客户统计副表（月+门店+OE+客户）
"""

from datetime import date
from dateutil.relativedelta import relativedelta

from app.utils.database_connection import db_cursor

# OE军备统计主表：删除指定月数据 + 重新汇总插入
OE_SUMMARY_SQL = """
INSERT INTO ks_inquiry_oe_monthly_summary
    (summary_month, company, resolve_parts_num, car_brand_name, parts_name, inquiry_count)
SELECT
    DATE_FORMAT(quote_date, '%%Y-%%m-01') AS summary_month,
    company,
    resolve_parts_num,
    COALESCE(car_brand_name, '') AS car_brand_name,
    MAX(resolve_parts_name) AS parts_name,
    COUNT(DISTINCT inquiryId) AS inquiry_count
FROM crmapp_ks_inquiry_detail
WHERE quote_date >= %s AND quote_date <= %s
  AND COALESCE(resolve_parts_num, '') != ''
GROUP BY summary_month, company, resolve_parts_num, car_brand_name
ON DUPLICATE KEY UPDATE
    parts_name = VALUES(parts_name),
    inquiry_count = VALUES(inquiry_count),
    updated_at = NOW()
"""

# OE客户统计副表
CUSTOMER_SUMMARY_SQL = """
INSERT INTO ks_inquiry_customer_by_oe_monthly_summary
    (summary_month, company, resolve_parts_num, garage_company_name, inquiry_count)
SELECT
    DATE_FORMAT(quote_date, '%%Y-%%m-01') AS summary_month,
    company,
    resolve_parts_num,
    COALESCE(garage_company_name, '') AS garage_company_name,
    COUNT(DISTINCT inquiryId) AS inquiry_count
FROM crmapp_ks_inquiry_detail
WHERE quote_date >= %s AND quote_date <= %s
  AND COALESCE(resolve_parts_num, '') != ''
  AND COALESCE(TRIM(garage_company_name), '') != ''
GROUP BY summary_month, company, resolve_parts_num, garage_company_name
ON DUPLICATE KEY UPDATE
    inquiry_count = VALUES(inquiry_count),
    updated_at = NOW()
"""

# 清理指定月旧数据（先删后插，保证删除的明细不再残留）
DELETE_OE_SQL = "DELETE FROM ks_inquiry_oe_monthly_summary WHERE summary_month = %s"
DELETE_CUSTOMER_SQL = "DELETE FROM ks_inquiry_customer_by_oe_monthly_summary WHERE summary_month = %s"


def refresh_month(month: date):
    """
    重算指定自然月的两张汇总表（先删该月数据再重新汇总，幂等）

    Args:
        month: 该月任意一天，内部取月首日
    """
    month_first = month.replace(day=1)
    month_last = month_first + relativedelta(months=1) - relativedelta(days=1)

    with db_cursor() as cursor:
        cursor.execute(DELETE_OE_SQL, (month_first,))
        cursor.execute(DELETE_CUSTOMER_SQL, (month_first,))
        cursor.execute(OE_SUMMARY_SQL, (month_first, month_last))
        cursor.execute(CUSTOMER_SUMMARY_SQL, (month_first, month_last))

    print(f"[OeMonthlySummaryService] 已刷新 {month_first.strftime('%Y-%m')} 汇总数据")


def refresh_recent_months():
    """重算上个月 + 当前月（每日定时任务调用）"""
    today = date.today()
    refresh_month(today)
    refresh_month(today - relativedelta(months=1))


def refresh_all():
    """
    全量重算所有历史月份（初始化/修复用）

    从明细表最早月份起逐月重算
    """
    with db_cursor() as cursor:
        cursor.execute("SELECT MIN(quote_date) FROM crmapp_ks_inquiry_detail")
        row = cursor.fetchone()

    min_date = None
    if isinstance(row, dict):
        min_date = row.get('MIN(quote_date)') or row.get('min_date')
    else:
        min_date = row[0] if row else None

    if not min_date:
        print("[OeMonthlySummaryService] 明细表无数据，跳过全量刷新")
        return

    month = min_date.replace(day=1) if isinstance(min_date, date) else date.today()
    today = date.today()
    count = 0
    while month <= today:
        refresh_month(month)
        month = month + relativedelta(months=1)
        count += 1

    print(f"[OeMonthlySummaryService] 全量刷新完成，共 {count} 个月")
