# -*- coding: utf-8 -*-
# @Time    : 2026/6/21
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : ks_nonself_report_service.py
# @Software: PyCharm
# @Desc    : 开思非本店下单业务汇报服务
#            每日定时任务运行结束后调用，统计昨日 display_seller_status='非本店下单' 的数据，
#            生成 Excel 文件并通过微信推送下载链接。

import os
from datetime import datetime, timedelta
from typing import Dict, Any

import pandas as pd

from app.utils.database_connection import db_cursor
from app.utils.common_util_module.server_push import message_push


# 门店映射：company 字段值 -> 中文显示名
# 未来新增门店仅需在此增加条目
KS_NONSELF_STORE_MAP = {
    "fsbbr": "佛山",
}

# 业务分类标识（用于通用 Excel 路由和文件命名）
CATEGORY = "ks_nonself"

# 导出目录与下载 URL 模板
EXPORT_DIR = os.path.join("static", "exports")
DOWNLOAD_URL_TEMPLATE = "http://x.fsbbr.net/web/download_excel/{category}/{company}/{date_str}"


def _fetch_nonself_records(company: str, date_str: str):
    """
    查询指定门店、指定日期的「非本店下单」明细
    """
    sql = """
        SELECT
            inquiryId,
            garage_company_name,
            partsNum,
            partsName,
            brandName,
            brandNormalized,
            brandId,
            display_seller_status,
            remark,
            vin,
            engine,
            production_date,
            chassis,
            car_brand_name,
            location_name,
            arrival_time
        FROM crmapp_ks_inquiry_detail
        WHERE display_seller_status = %s
          AND company = %s
          AND quote_date = %s
        ORDER BY created_at DESC
    """
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, ("非本店下单", company, date_str))
        return cursor.fetchall()


def _export_to_excel(records, company: str, date_str: str) -> str:
    """
    将记录导出到 static/exports/{category}_{company}_{date_str}.xlsx
    返回生成的文件绝对路径
    """
    os.makedirs(EXPORT_DIR, exist_ok=True)
    file_name = f"{CATEGORY}_{company}_{date_str}.xlsx"
    file_path = os.path.join(EXPORT_DIR, file_name)

    df = pd.DataFrame(records)
    df.to_excel(file_path, index=False)
    return file_path


def _build_download_url(company: str, date_str: str) -> str:
    return DOWNLOAD_URL_TEMPLATE.format(
        category=CATEGORY, company=company, date_str=date_str
    )


def _build_message(now_str: str, date_str: str, store_name: str, count: int, download_url: str) -> str:
    return (
        "===【开思非本店下单业务汇报】===\n"
        f"统计时间：{now_str}\n"
        f"数据日期范围：{date_str}\n"
        f"门店：{store_name}\n"
        f"数据条数：{count}\n"
        f"文件下载链接：{download_url}"
    )


def run_ks_nonself_daily_report() -> Dict[str, Any]:
    """
    执行开思非本店下单业务汇报
    - 数据范围：当前日期的前一天（昨天一整天）
    - 遍历 KS_NONSELF_STORE_MAP 中配置的门店
    - 有数据则导出 Excel 并推送消息；无数据跳过推送

    Returns:
        dict: 各门店执行结果
    """
    now = datetime.now()
    yesterday = (now - timedelta(days=1)).date()
    date_str = yesterday.strftime("%Y-%m-%d")
    now_str = now.strftime("%Y-%m-%d %H:%M")

    print(f"\n[开思非本店下单汇报] 开始执行，数据日期：{date_str}")

    summary = {"date": date_str, "stores": []}

    for company, store_name in KS_NONSELF_STORE_MAP.items():
        records = _fetch_nonself_records(company, date_str)
        count = len(records)
        store_result = {
            "company": company,
            "store_name": store_name,
            "count": count,
            "pushed": False,
            "file_path": None,
        }

        if count == 0:
            print(f"[开思非本店下单汇报] {store_name}({company}) 无数据，跳过推送")
        else:
            file_path = _export_to_excel(records, company, date_str)
            store_result["file_path"] = file_path

            download_url = _build_download_url(company, date_str)
            message = _build_message(now_str, date_str, store_name, count, download_url)

            push_resp = message_push("开思", message)
            store_result["pushed"] = True
            print(f"[开思非本店下单汇报] {store_name}({company}) 推送成功，{count} 条，"
                  f"文件：{file_path}，响应：{push_resp}")

        summary["stores"].append(store_result)

    print(f"[开思非本店下单汇报] 执行完成\n")
    return summary
