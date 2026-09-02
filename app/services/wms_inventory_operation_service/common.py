# -*- coding:utf-8 -*-
"""
WMS 库存操作推送服务 - 公共逻辑

包含采购入库和采购移除共用的数据提取、接口调用、日志保存逻辑。
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from app.utils.orm.session import orm_session

from .utils import _is_not_empty, _safe_decimal, _safe_int


PAGE_LIMIT = 20


def _extract_orders(
    response: Any,
    logger: Optional[logging.Logger] = None,
    require_supplier: bool = True,
) -> List[Dict[str, Any]]:
    """
    从 get_status_orders 响应中提取订单

    :param response: 接口响应
    :param logger: 可选日志器
    :param require_supplier: 为 True 时只返回 supplier_short_name 不为空的订单
    """
    if response is None:
        return []

    json_data = response.json()
    status = json_data.get("status")
    if status not in (0, 200) and status is not None:
        if logger is not None:
            logger.warning(
                "[库存操作] get_status_orders 返回异常: status=%s, msg=%s",
                status,
                json_data.get("msg"),
            )
        return []

    page_data = json_data.get("data", {}).get("data", {}).get("data", []) or []
    orders = []
    for item in page_data:
        supplier_short_name = item.get("supplier_short_name")
        if require_supplier and not _is_not_empty(supplier_short_name):
            continue

        orders_id = item.get("orders_id")
        orders_no = item.get("orders_no")
        if not orders_id or not orders_no:
            continue

        order = {
            "orders_id": str(orders_id),
            "orders_no": str(orders_no),
        }
        if _is_not_empty(supplier_short_name):
            order["supplier_short_name"] = str(supplier_short_name).strip()
        else:
            order["supplier_short_name"] = None

        orders.append(order)

    return orders


def _fetch_orders_by_type(
    spider: Any,
    type_val: int,
    status_val: int,
    logger: logging.Logger,
    require_supplier: bool = True,
) -> List[Dict[str, Any]]:
    """分页拉取指定 type 和 status 的订单列表"""
    all_orders = []
    current_page = 1

    while True:
        logger.info("[库存操作] 拉取 type=%s status=%s 第 %s 页", type_val, status_val, current_page)
        resp = spider.get_status_orders(type=type_val, status=status_val, page=current_page)
        orders = _extract_orders(resp, logger=logger, require_supplier=require_supplier)

        if not orders:
            logger.info("[库存操作] type=%s status=%s 第 %s 页无数据，结束", type_val, status_val, current_page)
            break

        all_orders.extend(orders)
        logger.info(
            "[库存操作] type=%s status=%s 第 %s 页获取 %s 条，累计 %s 条",
            type_val, status_val, current_page, len(orders), len(all_orders),
        )

        if len(orders) < PAGE_LIMIT:
            break

        current_page += 1

    return all_orders


def _run_flow(
    spider: Any,
    logger: logging.Logger,
    dry_run: bool,
    type_val: int,
    operation_name: str,
    process_one_func: Callable,
) -> Dict[str, Any]:
    """执行采购入库/移除通用流程"""
    logger.info("[%s] 开始拉取订单", operation_name)

    all_orders_status_0 = _fetch_orders_by_type(spider, type_val=type_val, status_val=0, logger=logger)
    all_orders_status_1 = _fetch_orders_by_type(spider, type_val=type_val, status_val=1, logger=logger)
    all_orders = all_orders_status_0 + all_orders_status_1

    eligible_orders = [order for order in all_orders if _is_not_empty(order.get("supplier_short_name"))]
    logger.info(
        "[%s] 总订单 %s 条，supplier_short_name 非空 %s 条",
        operation_name, len(all_orders), len(eligible_orders),
    )

    if not eligible_orders:
        return {
            "all_count": len(all_orders),
            "eligible_count": 0,
            "eligible_order_nos": [],
            "total": 0,
            "pushed": 0,
            "skipped": 0,
            "results": [],
        }

    results = []
    pushed_count = 0
    skipped_count = 0

    for order in eligible_orders:
        result = process_one_func(spider, order, logger, dry_run)
        results.append(result)
        if result["pushed"]:
            pushed_count += 1
        else:
            skipped_count += 1

    logger.info("[%s] 完成，推送 %s 条，跳过 %s 条", operation_name, pushed_count, skipped_count)
    return {
        "all_count": len(all_orders),
        "eligible_count": len(eligible_orders),
        "eligible_order_nos": [order["orders_no"] for order in eligible_orders],
        "total": len(eligible_orders),
        "pushed": pushed_count,
        "skipped": skipped_count,
        "results": results,
    }


def _extract_po_pono(response: Any) -> Optional[str]:
    """从 get_return_items 响应中提取 data.po.pono"""
    if response is None:
        return None
    json_data = response.json()
    return json_data.get("data", {}).get("po", {}).get("pono")


def _extract_item_details(
    response: Any,
    orders_no: str,
    field_map: Dict[str, Optional[Callable[[Any], Any]]],
) -> List[Dict[str, Any]]:
    """
    从 get_return_items 响应中提取商品明细

    :param field_map: 字段名到转换函数的映射，转换函数为 None 时原值保留
    """
    if response is None:
        return []

    json_data = response.json()
    items_by_group = json_data.get("data", {}).get("data", {}) or {}
    if not isinstance(items_by_group, dict):
        return []

    items = items_by_group.get(orders_no, []) or []
    details = []
    for item in items:
        if not isinstance(item, dict):
            continue
        detail = {}
        for field_name, converter in field_map.items():
            value = item.get(field_name)
            detail[field_name] = converter(value) if converter else value
        details.append(detail)

    return details


def _call_main_and_confirm(
    spider: Any,
    main_api_method: Callable,
    confirm_type: str,
    orders_id: str,
    logger: logging.Logger,
    operation_name: str,
) -> Tuple[Optional[int], Optional[str], Optional[int], Optional[str]]:
    """
    调用主接口，成功后再调用确认接口

    :return: (主接口 status, 主接口 msg, 确认接口 status, 确认接口 msg)
    """
    push_resp = main_api_method(orders_id=orders_id)
    push_data = push_resp.json()
    api_response_status = push_data.get("status")
    api_response_message = push_data.get("msg")

    confirm_api_status = None
    confirm_message = None
    if api_response_status == 200:
        confirm_resp = spider.orders_workok(type=confirm_type, orders_id=orders_id)
        confirm_data = confirm_resp.json()
        confirm_api_status = confirm_data.get("status")
        confirm_message = confirm_data.get("msg")

    return api_response_status, api_response_message, confirm_api_status, confirm_message


def _build_push_result(
    orders_id: str,
    orders_no: str,
    total_needqty: Optional[int],
    total_qty: Optional[int],
    total_price: Optional[float],
    dry_run: bool,
) -> Dict[str, Any]:
    """构建推送结果基础字典"""
    return {
        "orders_id": orders_id,
        "orders_no": orders_no,
        "pushed": False,
        "total_needqty": total_needqty,
        "total_qty": total_qty,
        "total_price": total_price,
        "api_response_code": None,
        "api_response_message": None,
        "confirm_api_response_code": None,
        "confirm_api_response_message": None,
        "dry_run": dry_run,
    }


def _build_log_data(
    orders_id: str,
    orders_no: str,
    pono: Optional[str],
    supplier_short_name: str,
    totals: Dict[str, Any],
    api_response_code: Any,
    api_response_message: Optional[str],
    confirm_api_response_code: Any,
    confirm_api_response_message: Optional[str],
    item_details: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """构建推送日志数据（头表 + 明细表）"""
    now = datetime.now()
    header_data = {
        "orders_id": orders_id,
        "orders_no": orders_no,
        "pono": pono,
        "supplier_short_name": supplier_short_name,
        "api_response_code": api_response_code,
        "api_response_message": api_response_message,
        "confirm_api_response_code": confirm_api_response_code,
        "confirm_api_response_message": confirm_api_response_message,
        "pushed_at": now,
    }
    header_data.update(totals)

    detail_data_list = [
        {"orders_id": orders_id, **item}
        for item in item_details
    ]

    return header_data, detail_data_list
