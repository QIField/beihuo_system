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
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

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

# 01-09 开头库位：第一次保存不推送，第二次才推送
KWNOS_PATTERN = re.compile(r"^0[1-9]-")

# type 显示映射
TYPE_NAME_MAP = {
    3: "收货",
    5: "拣货",
}


def _fetch_orders(company: str, logger: logging.Logger) -> List[Dict[str, Any]]:
    """
    按 (type, status) 组合爬取订单列表，按 orders_id 去重
    """
    seen_order_ids = set()
    orders = []

    for order_type, status in CRAWL_COMBINATIONS:
        logger.info("[wms_order_push] 开始爬取 type=%s, status=%s", order_type, status)

        records = get_status_orders_by_page_service(
            type=order_type,
            status=status,
            store=company,
            persist=False,
            logger=logger,
        )

        if not records:
            logger.info("[wms_order_push] type=%s, status=%s 无数据", order_type, status)
            continue

        for record in records:
            orders_id = record.get("orders_id")
            if orders_id in seen_order_ids:
                continue
            seen_order_ids.add(orders_id)
            orders.append(record)

        logger.info("[wms_order_push] type=%s, status=%s 获取 %s 条", order_type, status, len(records))

    return orders


def _parse_pick_work_items(spider: WmsGzbbrSpider, orders_id: Any, order_type: int) -> List[Dict[str, Any]]:
    """
    调用 git_pick_work 接口，按 type 解析商品明细
    """
    resp = spider.get_pick_work(orders_id)
    data = resp.json()
    items = data.get("data", {}).get("data", [])

    result = []
    for item in items:
        if order_type == 3 and item.get("is_grey_out_cn") == "已出库":
            continue

        result.append({
            "oe_number": item.get("oe_number"),
            "product_name": item.get("name"),
            "kwno": item.get("kwno"),
            "needqty": item.get("needqty"),
            "qty": item.get("qty"),
        })

    return result


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


def _build_excel_row(order: Dict[str, Any], item: Dict[str, Any], order_type: int) -> Dict[str, Any]:
    """
    组装 Excel 行数据，使用中文表头
    """
    pono = order.get("pono")
    needqty = item.get("needqty")
    qty = item.get("qty")

    return {
        "状态": TYPE_NAME_MAP.get(order_type, order_type),
        "订单": pono,
        "客户名称": order.get("fullname"),
        "操作人": order.get("name"),
        "oe_number": item.get("oe_number"),
        "名称": item.get("product_name"),
        "需要": needqty,
        "已拣货/已收货": qty,
        "缺货数/待出库数": _calculate_shortage(needqty, qty),
    }


def _export_to_excel(rows: List[Dict[str, Any]], company: str, date_str: str) -> str:
    """
    将记录导出到 static/exports/{category}_{company}_{date_str}.xlsx
    """
    os.makedirs(EXPORT_DIR, exist_ok=True)
    file_name = f"{CATEGORY}_{company}_{date_str}.xlsx"
    file_path = os.path.join(EXPORT_DIR, file_name)

    df = pd.DataFrame(rows)
    df.to_excel(file_path, index=False)

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


def run_wms_order_push(company: str = DEFAULT_COMPANY, logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    执行 WMS 订单推送

    流程：
    1. 爬取订单列表
    2. 对每个订单调用 git_pick_work 获取明细
    3. 按 type 过滤明细
    4. 01-09 仓位：第一次保存不推送，第二次才推送
    5. 生成 Excel
    6. 推送下载链接

    :param company: 门店代码
    :param logger: 可选日志器，外部传入则使用外部日志器
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

    spider = WmsGzbbrSpider(logger=logger)
    pono_list = [order.get("pono") for order in orders]
    seen_keys = _load_seen_keys(pono_list)
    running_seen = seen_keys.copy()
    new_seen_keys: Set[Tuple[str, str, str]] = set()
    excel_rows = []

    try:
        for order in orders:
            orders_id = order.get("orders_id")
            order_type_raw = order.get("type")
            order_type = int(order_type_raw) if order_type_raw is not None else None

            items = _parse_pick_work_items(spider, orders_id, order_type)

            for item in items:
                kwno = item.get("kwno") or ""
                pono = order.get("pono")
                oe_number = item.get("oe_number")
                detail_key = (pono, kwno, oe_number)

                is_new = detail_key not in running_seen
                running_seen.add(detail_key)

                # 01-09 开头仓位：第一次保存不推送，第二次才推送
                if KWNOS_PATTERN.match(kwno):
                    if is_new:
                        new_seen_keys.add(detail_key)
                        continue

                excel_rows.append(_build_excel_row(order, item, order_type))
    finally:
        spider.close()

    _save_seen_keys(new_seen_keys)

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

    push_resp = message_push("WMS", message)
    result["pushed"] = True
    result["push_response"] = push_resp

    logger.info("[wms_order_push] 推送成功，%s 条，文件：%s", count, file_path)

    return result
