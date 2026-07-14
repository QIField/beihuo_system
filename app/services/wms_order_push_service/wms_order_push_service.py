# -*- coding: utf-8 -*-
# @Time    : 2026/7/9
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_order_push_service.py
# @Software: PyCharm
# @Desc    : WMS 订单推送服务
#            爬取 WMS 状态订单，获取明细，不入库，生成 Excel 并推送下载链接

import logging
import os
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from openpyxl.styles import Alignment

from app.models.orm_models.wms.wms_order_push_seen import WmsOrderPushSeen
from app.scripts.spiders.spider_entities.wms_gzbbr import WmsGzbbrSpider
from app.scripts.tasks.wms.get_status_orders_tasks import get_status_orders_by_page_service
from app.utils.common_util_module.server_push import message_push
from app.utils.logger_config import get_task_logger
from app.utils.orm.session import orm_session


# 业务分类标识（用于通用 Excel 路由和文件命名）
CATEGORY = "wms_order_push"

# 默认门店
DEFAULT_COMPANY = "fsbbr"

# 导出目录
EXPORT_DIR = os.path.join("static", "exports")

# 下载 URL 模板
DOWNLOAD_URL_TEMPLATE = "http://x.fsbbr.net/web/download_excel/{category}/{company}/{date_str}"

# 需要爬取的 (type, status) 组合
CRAWL_COMBINATIONS = [
    (3, 0),
    (3, 1),
    (5, 0),
    (5, 1),
]

# 01-09 开头库位：第一次保存不推送，第二次才推送（仅 status=1 使用）
KWNOS_PATTERN = re.compile(r"^0[1-9]-")

# status=1 时订单列表需要额外保留的字段（不入库，仅用于 Excel）
PICK_WORK_EXTRA_FIELDS = ["handler_name", "real_name"]

# type 显示映射
TYPE_NAME_MAP = {
    3: "收货",
    5: "拣货",
}

# Excel 列顺序
EXCEL_COLUMNS = [
    "状态", "订单", "客户名称", "采购员/业务员", "订单日期", "操作人",
    "序号", "oe_number", "名称", "需要", "已拣货/已收货", "缺货数/待出库数",
]

# 需要按订单纵向合并的列索引（1-based）：状态、订单、客户名称、采购员/业务员、订单日期、操作人
MERGE_COLS = [1, 2, 3, 4, 5, 6]


def _fetch_orders(company: str, logger: logging.Logger) -> List[Dict[str, Any]]:
    """
    按 (type, status) 组合爬取订单列表，按 orders_no 去重
    """
    seen_order_nos = set()
    orders = []

    for order_type, status in CRAWL_COMBINATIONS:
        logger.info("[wms_order_push] 开始爬取 type=%s, status=%s", order_type, status)

        # status=1 仍需 handler_name/real_name，status=0 不需要
        extra_fields = PICK_WORK_EXTRA_FIELDS if status == 1 else None

        records = get_status_orders_by_page_service(
            type=order_type,
            status=status,
            store=company,
            persist=False,
            logger=logger,
            extra_fields=extra_fields,
        )

        if not records:
            logger.info("[wms_order_push] type=%s, status=%s 无数据", order_type, status)
            continue

        for record in records:
            orders_no = record.get("orders_no")
            if not orders_no or orders_no in seen_order_nos:
                continue
            seen_order_nos.add(orders_no)
            record["status"] = status
            orders.append(record)

        logger.info("[wms_order_push] type=%s, status=%s 获取 %s 条", order_type, status, len(records))

    return orders


def _parse_pick_work_items(spider: WmsGzbbrSpider, orders_id: Any) -> List[Dict[str, Any]]:
    """
    调用 git_pick_work 接口，解析商品明细
    """
    resp = spider.get_pick_work(orders_id)
    data = resp.json()
    items = data.get("data", {}).get("data", [])

    return [
        {
            "oe_number": item.get("oe_number"),
            "product_name": item.get("name"),
            "kwno": item.get("kwno"),
            "needqty": item.get("needqty"),
            "qty": item.get("qty"),
        }
        for item in items
    ]


def _format_podt(podt: Any) -> Optional[str]:
    """
    将 data.po.podt 截取为 YYYY-MM-DD
    """
    if not podt:
        return None
    text = str(podt)
    if ' ' in text:
        return text.split(' ', 1)[0]
    return text


def _parse_return_items(spider: WmsGzbbrSpider, orders_no: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    调用 get_return_items 接口，返回订单头信息和商品明细
    """
    resp = spider.get_return_items(orders_no)
    data = resp.json()

    po_info = data.get("data", {}).get("po", {})
    order_header = {
        "pono": po_info.get("pono"),
        "orders_id": po_info.get("orders_id"),
        "fullname": po_info.get("fullname"),
        "orderdate": _format_podt(po_info.get("podt")),
    }

    items_by_group = data.get("data", {}).get("data", {})
    if not isinstance(items_by_group, dict):
        return order_header, []

    items = items_by_group.get(orders_no, []) or []

    detail = [
        {
            "oe_number": item.get("number"),
            "product_name": item.get("l_name_zh"),
            "kwno": item.get("kw_no"),
            "needqty": item.get("needqty"),
            "qty": item.get("qty"),
        }
        for item in items
    ]

    return order_header, detail


def _load_seen_keys(pono_list: List[str]) -> Set[Tuple[str, str, str]]:
    """
    批量查询当前这批订单已见过的 (pono, kwno, oe_number)
    """
    if not pono_list:
        return set()

    with orm_session() as session:
        rows = session.query(WmsOrderPushSeen).filter(
            WmsOrderPushSeen.pono.in_(pono_list)
        ).all()
        return {(row.pono, row.kwno, row.oe_number) for row in rows}


def _save_seen_keys(keys: Set[Tuple[str, str, str]]) -> None:
    """
    批量保存新见到的 (pono, kwno, oe_number)
    """
    if not keys:
        return

    with orm_session() as session:
        for pono, kwno, oe_number in keys:
            seen = WmsOrderPushSeen(
                pono=pono,
                kwno=kwno,
                oe_number=oe_number,
            )
            session.add(seen)
        session.commit()


def _calculate_shortage(needqty: Any, qty: Any) -> int:
    """
    计算缺货数/待出库数：需要 - 已拣货/已收货
    """
    try:
        n = int(needqty) if needqty is not None else 0
        q = int(qty) if qty is not None else 0
        return n - q
    except (ValueError, TypeError):
        return 0


def _get_purchaser_or_salesperson(order: Dict[str, Any], order_type: int) -> Optional[str]:
    """
    根据订单类型从订单列表接口获取采购员/业务员
    - type=5（拣货）：取 handler_name
    - type=3（收货）：取 real_name
    """
    if order_type == 5:
        return order.get("handler_name")
    if order_type == 3:
        return order.get("real_name")
    return None


def _build_excel_row(
    order: Dict[str, Any],
    item: Dict[str, Any],
    order_type: int,
    seq: int,
    status: int,
) -> Dict[str, Any]:
    """
    组装 Excel 行数据，使用中文表头
    - status=0 时操作人/采购员为空
    - status=1 时保留原值
    """
    pono = order.get("pono")
    needqty = item.get("needqty")
    qty = item.get("qty")

    return {
        "状态": TYPE_NAME_MAP.get(order_type, order_type),
        "订单": pono,
        "客户名称": order.get("fullname"),
        "采购员/业务员": _get_purchaser_or_salesperson(order, order_type) if status == 1 else "",
        "订单日期": order.get("orderdate"),
        "操作人": order.get("name") if status == 1 else "",
        "序号": seq,
        "oe_number": item.get("oe_number"),
        "名称": item.get("product_name"),
        "需要": needqty,
        "已拣货/已收货": qty,
        "缺货数/待出库数": _calculate_shortage(needqty, qty),
    }


def _build_sheet_data(rows: List[Dict[str, Any]], order_type: int) -> Tuple[pd.DataFrame, List[Tuple[int, int]]]:
    """
    按订单类型筛选数据，组间插入空行，并返回需要合并的单元格行范围

    :param rows: 所有 Excel 行数据
    :param order_type: 3（收货）或 5（拣货）
    :return: (DataFrame, 合并范围列表[(start_excel_row, end_excel_row)])
    """
    type_name = TYPE_NAME_MAP.get(order_type)
    sheet_rows = [row for row in rows if row.get("状态") == type_name]

    if not sheet_rows:
        return pd.DataFrame(columns=EXCEL_COLUMNS), []

    data_rows: List[Dict[str, Any]] = []
    merge_ranges: List[Tuple[int, int]] = []

    current_pono: Optional[str] = None
    group_start_row: Optional[int] = None
    excel_row = 2  # 第 1 行为表头，数据从第 2 行开始

    for row in sheet_rows:
        pono = row.get("订单")
        if pono != current_pono:
            if current_pono is not None:
                # 结束上一个订单组的范围
                if group_start_row is not None:
                    merge_ranges.append((group_start_row, excel_row - 1))
                # 不同订单之间插入空行
                data_rows.append({col: "" for col in EXCEL_COLUMNS})
                excel_row += 1
            current_pono = pono
            group_start_row = excel_row

        data_rows.append({col: row.get(col, "") for col in EXCEL_COLUMNS})
        excel_row += 1

    # 结束最后一个订单组
    if group_start_row is not None:
        merge_ranges.append((group_start_row, excel_row - 1))

    df = pd.DataFrame(data_rows, columns=EXCEL_COLUMNS)
    return df, merge_ranges


def _apply_cell_merges(ws, merge_ranges: List[Tuple[int, int]], merge_cols: List[int]) -> None:
    """
    对指定列按订单行范围纵向合并单元格，并设置垂直居中
    """
    for start_row, end_row in merge_ranges:
        if start_row >= end_row:
            continue
        for col_idx in merge_cols:
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
        # 留一定边距
        adjusted_width = max_length + 2
        if adjusted_width > 0:
            ws.column_dimensions[column_letter].width = adjusted_width


def _export_to_excel(rows: List[Dict[str, Any]], company: str, date_str: str) -> str:
    """
    将记录按状态分工作表导出：
    - 收货、拣货分别存放
    - 不同订单之间插入空行
    - 同一订单的状态、订单、客户名称、采购员/业务员、操作人单元格合并
    """
    os.makedirs(EXPORT_DIR, exist_ok=True)
    file_name = f"{CATEGORY}_{company}_{date_str}.xlsx"
    file_path = os.path.join(EXPORT_DIR, file_name)

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        for order_type in (3, 5):
            sheet_name = TYPE_NAME_MAP.get(order_type, order_type)
            df, merge_ranges = _build_sheet_data(rows, order_type)

            # 即使无数据也创建工作表（保留表头）
            if df.empty:
                df = pd.DataFrame(columns=EXCEL_COLUMNS)

            df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            _apply_cell_merges(ws, merge_ranges, MERGE_COLS)
            ws.freeze_panes = "A2"  # 冻结标题行
            _auto_fit_columns(ws)  # 自动调整列宽

    return file_path


def _build_download_url(company: str, date_str: str) -> str:
    return DOWNLOAD_URL_TEMPLATE.format(
        category=CATEGORY, company=company, date_str=date_str
    )


def _build_message(now_str: str, company: str, count: int, download_url: str) -> str:
    return (
        "===【WMS订单推送】===\n"
        f"统计时间：{now_str}\n"
        f"门店：{company}\n"
        f"数据条数：{count}\n"
        f"文件下载链接：{download_url}"
    )


def run_wms_order_push(
    company: str = DEFAULT_COMPANY,
    logger: Optional[logging.Logger] = None,
    push: bool = True,
) -> Dict[str, Any]:
    """
    执行 WMS 订单推送

    流程：
    1. 爬取订单列表，按 orders_no 去重
    2. status=0 的订单调用 get_return_items 获取明细
    3. status=1 的订单调用 git_pick_work 获取明细
    4. status=1 的订单执行 01-09 仓位过滤（第一次保存不推送，第二次才推送）
    5. 生成 Excel
    6. 推送下载链接（push=True 时）

    :param company: 门店代码
    :param logger: 可选日志器，外部传入则使用外部日志器
    :param push: 是否执行推送，默认 True；测试时可传 False 只生成 Excel
    :return: 执行结果
    """
    logger = logger or get_task_logger('wms_order_push')

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d_%H%M")
    now_str = now.strftime("%Y-%m-%d %H:%M")

    logger.info("\n[wms_order_push] 开始执行 - %s", now_str)

    orders = _fetch_orders(company, logger)
    if not orders:
        logger.info("[wms_order_push] 无订单数据，跳过")
        return {"company": company, "count": 0, "file_path": None, "pushed": False}

    combo_order_counts = Counter((order.get("type"), order.get("status")) for order in orders)
    logger.info("[wms_order_push] 各组合订单数: %s", dict(combo_order_counts))

    spider = WmsGzbbrSpider(logger=logger)

    # 仓位过滤仅对 status=1 的订单生效
    pick_work_orders = [order for order in orders if order.get("status") == 1]
    pono_list = [order.get("pono") for order in pick_work_orders]
    seen_keys = _load_seen_keys(pono_list)
    running_seen = seen_keys.copy()
    new_seen_keys: Set[Tuple[str, str, str]] = set()
    excel_rows = []
    combo_row_counts: Dict[Tuple[int, int], int] = {}

    try:
        for order in orders:
            orders_no = order.get("orders_no")
            order_type_raw = order.get("type")
            order_type = int(order_type_raw) if order_type_raw is not None else None
            status = order.get("status")
            combo_key = (order_type, status)

            if status == 0:
                header, items = _parse_return_items(spider, orders_no)
                current_order = header
            else:
                orders_id = order.get("orders_id")
                items = _parse_pick_work_items(spider, orders_id)
                current_order = order

            for seq, item in enumerate(items, start=1):
                if status == 1:
                    kwno = item.get("kwno") or ""
                    pono = current_order.get("pono")
                    oe_number = item.get("oe_number")
                    detail_key = (pono, kwno, oe_number)

                    is_new = detail_key not in running_seen
                    running_seen.add(detail_key)

                    # 01-09 开头仓位：第一次保存不推送，第二次才推送
                    if KWNOS_PATTERN.match(kwno):
                        if is_new:
                            new_seen_keys.add(detail_key)
                            continue

                excel_rows.append(_build_excel_row(current_order, item, order_type, seq, status))
                combo_row_counts[combo_key] = combo_row_counts.get(combo_key, 0) + 1
    finally:
        spider.close()

    _save_seen_keys(new_seen_keys)

    logger.info("[wms_order_push] 各组合明细行数: %s", combo_row_counts)

    count = len(excel_rows)
    result = {
        "company": company,
        "count": count,
        "file_path": None,
        "pushed": False,
    }

    if count == 0:
        logger.info("[wms_order_push] 无明细数据，跳过导出和推送")
        return result

    file_path = _export_to_excel(excel_rows, company, date_str)
    result["file_path"] = file_path

    download_url = _build_download_url(company, date_str)
    message = _build_message(now_str, company, count, download_url)

    if push:
        push_resp = message_push("WMS", message)
        result["pushed"] = True
        result["push_response"] = push_resp
        logger.info("[wms_order_push] 推送成功，%s 条，文件：%s", count, file_path)
    else:
        logger.info("[wms_order_push] 已生成 Excel（未推送），%s 条，文件：%s", count, file_path)

    return result
