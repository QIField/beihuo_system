# -*- coding: utf-8 -*-
# @Time    : 2026/6/21
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : ks_nonself_report_service.py
# @Software: PyCharm
# @Desc    : 开思下单业务汇报服务
#            每日定时任务运行结束后调用，统计昨日数据，
#            生成 Excel（非本店下单 / 本店下单 两个工作表）并通过微信推送下载链接。

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

import pandas as pd
from openpyxl.styles import Alignment

from app.utils.database_connection import db_cursor
from app.utils.common_util_module.server_push import message_push
from app.utils.logger_config import get_task_logger

logger = get_task_logger('ks_nonself_report')


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

# 按 inquiryId 合并的列名
MERGE_BY_INQUIRYID_COLUMNS = [
    "inquiryId",
    "garage_company_name",
    "vin",
    "engine",
    "production_date",
    "chassis",
]

# Excel 列顺序
EXCEL_COLUMNS = [
    "inquiryId", "garage_company_name", "partsNum", "partsName",
    "brandName", "brandNormalized", "brandId", "sellerPrice", "sellerBtPrice",
    "display_seller_status", "remark", "vin", "engine", "production_date", "chassis",
    "car_brand_name", "location_name", "arrival_time"
]


def _fetch_records(company: str, date_str: str, statuses: Tuple[str, ...]) -> List[Dict[str, Any]]:
    """
    查询指定门店、指定日期、指定状态的明细
    """
    if not statuses:
        return []

    placeholders = ', '.join(['%s'] * len(statuses))
    sql = f"""
        SELECT
            inquiryId,
            garage_company_name,
            partsNum,
            partsName,
            brandName,
            brandNormalized,
            brandId,
            sellerPrice,
            sellerBtPrice,
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
        WHERE display_seller_status IN ({placeholders})
          AND company = %s
          AND quote_date = %s
        ORDER BY created_at DESC
    """
    params = statuses + (company, date_str)
    logger.info(f"[数据查询] 门店={company}, 日期={date_str}, 状态={statuses}")
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        logger.info(f"[数据查询] 门店={company}, 日期={date_str}, 状态={statuses}, 返回 {len(rows)} 条")
        return rows


def _build_sheet_data(records: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, List[Tuple[int, int]]]:
    """
    按 inquiryId 排序、分组，组间插入空行，返回 DataFrame 和合并范围

    :param records: 原始记录列表
    :return: (DataFrame, 合并范围列表[(start_excel_row, end_excel_row)])
    """
    if not records:
        return pd.DataFrame(columns=EXCEL_COLUMNS), []

    # 按 inquiryId 排序
    sorted_records = sorted(records, key=lambda r: r.get("inquiryId", ""))

    data_rows: List[Dict[str, Any]] = []
    merge_ranges: List[Tuple[int, int]] = []
    current_inquiry_id: Any = None
    group_start_row: int = 0
    excel_row = 2  # 第 1 行为表头，数据从第 2 行开始

    for record in sorted_records:
        inquiry_id = record.get("inquiryId")
        if inquiry_id != current_inquiry_id:
            if current_inquiry_id is not None:
                # 结束上一个 inquiryId 分组
                if group_start_row > 0:
                    merge_ranges.append((group_start_row, excel_row - 1))
                # 不同 inquiryId 之间插入空行
                data_rows.append({col: "" for col in EXCEL_COLUMNS})
                excel_row += 1
            current_inquiry_id = inquiry_id
            group_start_row = excel_row

        data_rows.append({col: record.get(col, "") for col in EXCEL_COLUMNS})
        excel_row += 1

    # 结束最后一个分组
    if group_start_row > 0:
        merge_ranges.append((group_start_row, excel_row - 1))

    df = pd.DataFrame(data_rows, columns=EXCEL_COLUMNS)
    return df, merge_ranges


def _apply_inquiryid_merges(ws, merge_ranges: List[Tuple[int, int]]) -> None:
    """
    对 MERGE_BY_INQUIRYID_COLUMNS 列按 inquiryId 行范围纵向合并单元格
    """
    merge_col_indices = []
    for col_name in MERGE_BY_INQUIRYID_COLUMNS:
        if col_name in EXCEL_COLUMNS:
            merge_col_indices.append(EXCEL_COLUMNS.index(col_name) + 1)

    for start_row, end_row in merge_ranges:
        if start_row >= end_row:
            continue
        for col_idx in merge_col_indices:
            ws.merge_cells(start_row=start_row, start_column=col_idx, end_row=end_row, end_column=col_idx)
            ws.cell(row=start_row, column=col_idx).alignment = Alignment(vertical="center")


def _auto_fit_columns(ws) -> None:
    """
    根据单元格内容自动调整列宽
    """
    for column in ws.columns:
        column_letter = column[0].column_letter
        max_length = 0
        for cell in column:
            value = cell.value
            if value is None:
                continue
            try:
                cell_length = len(str(value))
                if cell_length > max_length:
                    max_length = cell_length
            except Exception:
                continue
        adjusted_width = max_length + 2
        if adjusted_width > 0:
            ws.column_dimensions[column_letter].width = adjusted_width


def _export_to_excel(nonself_records, self_records, company: str, date_str: str) -> str:
    """
    将记录按状态分两个工作表导出：
    - 非本店下单
    - 本店下单（含已在本店其他品质）
    """
    os.makedirs(EXPORT_DIR, exist_ok=True)
    file_name = f"{CATEGORY}_{company}_{date_str}.xlsx"
    file_path = os.path.join(EXPORT_DIR, file_name)

    logger.info(f"[Excel导出] 门店={company}, 日期={date_str}, 非本店={len(nonself_records)} 条, 本店={len(self_records)} 条, 文件={file_path}")
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        for sheet_name, records in [("非本店下单", nonself_records), ("本店下单", self_records)]:
            df, merge_ranges = _build_sheet_data(records)
            df = df.rename(columns={
                "sellerPrice": "含税价",
                "sellerBtPrice": "不含税价",
            })

            df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            _apply_inquiryid_merges(ws, merge_ranges)
            ws.freeze_panes = "A2"
            _auto_fit_columns(ws)
            logger.info(f"[Excel导出] 工作表={sheet_name}, 行数={len(df)}, 合并范围数={len(merge_ranges)}")

    logger.info(f"[Excel导出] 完成: {file_path}")
    return file_path


def _build_download_url(company: str, date_str: str) -> str:
    return DOWNLOAD_URL_TEMPLATE.format(
        category=CATEGORY, company=company, date_str=date_str
    )


def _build_message(
    now_str: str,
    date_str: str,
    store_name: str,
    nonself_count: int,
    self_count: int,
    same_quote_not_self_count: int,
    self_order_count: int,
    download_url: str
) -> str:
    return (
        "===【开思下单业务汇报】===\n"
        f"统计时间：{now_str}\n"
        f"数据日期范围：{date_str}\n"
        f"门店：{store_name}\n"
        f"非本店下单：{nonself_count} 条\n"
        f"本店下单：{self_count} 条\n"
        f"  - 已在本店其他品质：{same_quote_not_self_count} 条\n"
        f"  - 本店下单：{self_order_count} 条\n"
        f"文件下载链接：{download_url}"
    )


def run_ks_nonself_daily_report() -> Dict[str, Any]:
    """
    执行开思下单业务汇报
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

    logger.info(f"[开思下单汇报] 开始执行，数据日期：{date_str}")

    summary = {"date": date_str, "stores": []}

    for company, store_name in KS_NONSELF_STORE_MAP.items():
        logger.info(f"[开思下单汇报] 处理门店：{store_name}({company})")
        nonself_records = _fetch_records(company, date_str, ("非本店下单",))
        same_quote_not_self_records = _fetch_records(company, date_str, ("已在本店其他品质",))
        self_order_records = _fetch_records(company, date_str, ("本店下单",))
        self_records = same_quote_not_self_records + self_order_records
        nonself_count = len(nonself_records)
        same_quote_not_self_count = len(same_quote_not_self_records)
        self_order_count = len(self_order_records)
        self_count = same_quote_not_self_count + self_order_count
        total_count = nonself_count + self_count

        store_result = {
            "company": company,
            "store_name": store_name,
            "nonself_count": nonself_count,
            "same_quote_not_self_count": same_quote_not_self_count,
            "self_order_count": self_order_count,
            "self_count": self_count,
            "count": total_count,
            "pushed": False,
            "file_path": None,
        }

        if total_count == 0:
            logger.info(f"[开思下单汇报] {store_name}({company}) 无数据，跳过推送")
        else:
            try:
                file_path = _export_to_excel(nonself_records, self_records, company, date_str)
                store_result["file_path"] = file_path

                download_url = _build_download_url(company, date_str)
                message = _build_message(
                    now_str, date_str, store_name, nonself_count, self_count,
                    same_quote_not_self_count, self_order_count, download_url
                )

                logger.info(f"[开思下单汇报] {store_name}({company}) 开始推送消息")
                push_resp = message_push("开思", message)
                store_result["pushed"] = True
                logger.info(f"[开思下单汇报] {store_name}({company}) 推送成功，"
                            f"非本店{nonself_count} 条，本店{self_count} 条（已在本店其他品质{same_quote_not_self_count} 条，"
                            f"本店下单{self_order_count} 条），文件：{file_path}，响应：{push_resp}")
            except Exception:
                logger.exception(f"[开思下单汇报] {store_name}({company}) 导出或推送失败")
                store_result["pushed"] = False

        summary["stores"].append(store_result)

    logger.info(f"[开思下单汇报] 执行完成，结果：{summary}")
    return summary
