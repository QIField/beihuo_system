#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""汽配龙下单状态同步

从汽配龙查询 supplier_enquiry_status=3 的询价单，
按 item 级别的 quoteStatusStr 更新 qpl_quote_record.order_status。
只更新已有记录，不插入缺失记录。
"""

from app.utils.qpl_auto_bill.enquiry_api import query_enquiry_list
from app.utils.qpl_auto_bill.qpl_config import qpl_log
from app.utils.database_connection import get_db_connection


def sync_order_status(target_date, company='fsbbr'):
    """
    同步指定日期的汽配龙产品下单状态。

    Args:
        target_date: 目标日期字符串，格式 yyyy-MM-dd
        company: 组织代码，默认 fsbbr

    Returns:
        dict: {"updated": 更新条数, "skipped": 跳过条数, "date": target_date, "company": company}
    """
    qpl_log(f"[下单状态同步] 开始同步 {target_date} {company}")

    result = query_enquiry_list(
        begin_date=target_date,
        end_date=target_date,
        supplier_enquiry_status=3,
        company=company
    )

    if not isinstance(result, dict) or result.get('code') != 10000 or not result.get('success'):
        qpl_log(f"[下单状态同步] 接口返回异常: {result}")
        return {"updated": 0, "skipped": 0, "date": target_date, "company": company}

    records = result.get('data', []) or []
    if not records:
        qpl_log(f"[下单状态同步] {target_date} 无状态为3的询价单")
        return {"updated": 0, "skipped": 0, "date": target_date, "company": company}

    updated_total = 0
    skipped_total = 0

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for record in records:
                supplier_enquiry_no = record.get('supplierEnquiryNo')
                if not supplier_enquiry_no:
                    continue

                items = record.get('supplierEnquiryItemList', []) or []
                for item in items:
                    enquiry_item_id = item.get('enquiryItemId')
                    quote_status_str = item.get('quoteStatusStr')
                    if not enquiry_item_id or not quote_status_str:
                        skipped_total += 1
                        continue

                    cursor.execute(
                        """
                        UPDATE qpl_quote_record
                        SET order_status = %s
                        WHERE supplier_enquiry_no = %s
                          AND enquiry_item_id = %s
                          AND company = %s
                        """,
                        (quote_status_str, supplier_enquiry_no, str(enquiry_item_id), company)
                    )
                    updated_total += cursor.rowcount

        conn.commit()
    finally:
        conn.close()

    qpl_log(
        f"[下单状态同步] {target_date} {company} 完成，"
        f"更新 {updated_total} 条，跳过 {skipped_total} 条"
    )
    return {"updated": updated_total, "skipped": skipped_total, "date": target_date, "company": company}
