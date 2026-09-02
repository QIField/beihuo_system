# -*- coding:utf-8 -*-
"""
WMS 采购移除自动推送服务

职责：
1. 处理 type=3, status=0/1 的订单
2. 调用 get_return_items(is_self='') 获取明细和总量
3. supplier_short_name 非空时调用 removePurchaseFromInventory
4. 写入采购移除日志表
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.models.orm_models.wms.wms_remove_purchase_inventory_log import WmsRemovePurchaseInventoryLog
from app.models.orm_models.wms.wms_remove_purchase_inventory_log_detail import WmsRemovePurchaseInventoryLogDetail
from app.scripts.spiders.spider_entities.wms_gzbbr import WmsGzbbrSpider
from app.utils.orm.session import orm_session

from .common import (
    _build_log_data,
    _build_push_result,
    _call_main_and_confirm,
    _extract_item_details as _extract_item_details_common,
    _extract_po_pono,
    _run_flow,
)
from .utils import _safe_decimal, _safe_int


REMOVE_DETAIL_FIELDS = {
    "number": None,
    "l_name_zh": None,
    "brandname": None,
    "frey_no": None,
    "needqty": _safe_int,
    "qty": _safe_int,
    "price": _safe_decimal,
}


def _extract_totals(response: Any) -> Tuple[Optional[int], Optional[int], Optional[float]]:
    """从 get_return_items 响应中提取 total.needqty / total.qty / total.price"""
    if response is None:
        return None, None, None
    json_data = response.json()
    total = json_data.get("data", {}).get("total", {}) or {}
    return (
        _safe_int(total.get("needqty")),
        _safe_int(total.get("qty")),
        _safe_decimal(total.get("price")),
    )


def _extract_item_details(response: Any, orders_no: str) -> List[Dict[str, Any]]:
    """从 get_return_items 响应中提取采购移除商品明细"""
    return _extract_item_details_common(response, orders_no, REMOVE_DETAIL_FIELDS)


def _save_remove_log(
    orders_id: str,
    orders_no: str,
    pono: Optional[str],
    supplier_short_name: str,
    total_needqty: Optional[int],
    total_qty: Optional[int],
    total_price: Optional[float],
    api_response_code: Any,
    api_response_message: Optional[str],
    confirm_api_response_code: Any,
    confirm_api_response_message: Optional[str],
    item_details: List[Dict[str, Any]],
) -> None:
    """保存采购移除推送日志（头表 + 明细表 upsert）"""
    header_data, detail_data_list = _build_log_data(
        orders_id=orders_id,
        orders_no=orders_no,
        pono=pono,
        supplier_short_name=supplier_short_name,
        totals={"total_needqty": total_needqty, "total_qty": total_qty, "total_price": total_price},
        api_response_code=api_response_code,
        api_response_message=api_response_message,
        confirm_api_response_code=confirm_api_response_code,
        confirm_api_response_message=confirm_api_response_message,
        item_details=item_details,
    )

    with orm_session() as session:
        WmsRemovePurchaseInventoryLog.upsert(session, header_data)
        if detail_data_list:
            WmsRemovePurchaseInventoryLogDetail.bulk_upsert(session, detail_data_list)


def _process_one_order(
    spider: WmsGzbbrSpider,
    order: Dict[str, Any],
    logger: logging.Logger,
    dry_run: bool,
) -> Dict[str, Any]:
    """处理单个采购移除订单"""
    orders_id = order["orders_id"]
    orders_no = order["orders_no"]
    supplier_short_name = order["supplier_short_name"]

    logger.info("[采购移除] 处理订单 orders_no=%s orders_id=%s", orders_no, orders_id)

    resp = spider.get_return_items(orders_no=orders_no, is_self="")
    total_needqty, total_qty, total_price = _extract_totals(resp)
    logger.info(
        "[采购移除] orders_no=%s total_needqty=%s total_qty=%s total_price=%s",
        orders_no, total_needqty, total_qty, total_price,
    )

    result = _build_push_result(orders_id, orders_no, total_needqty, total_qty, total_price, dry_run)

    if dry_run:
        logger.info("[采购移除] orders_no=%s 字段非空（dry_run 不调用接口）", orders_no)
        result["pushed"] = True
        result["api_response_message"] = "dry_run"
        return result

    api_status, api_msg, confirm_status, confirm_msg = _call_main_and_confirm(
        spider,
        spider.remove_purchase_from_inventory,
        "3",
        orders_id,
        logger,
        "采购移除",
    )

    result.update({
        "pushed": api_msg == "成功" and confirm_msg == "返回成功",
        "api_response_code": api_status,
        "api_response_message": api_msg,
        "confirm_api_response_code": confirm_status,
        "confirm_api_response_message": confirm_msg,
    })

    pono = _extract_po_pono(resp)
    item_details = _extract_item_details(resp, orders_no)
    _save_remove_log(
        orders_id=orders_id,
        orders_no=orders_no,
        pono=pono,
        supplier_short_name=supplier_short_name,
        total_needqty=total_needqty,
        total_qty=total_qty,
        total_price=total_price,
        api_response_code=api_status,
        api_response_message=api_msg,
        confirm_api_response_code=confirm_status,
        confirm_api_response_message=confirm_msg,
        item_details=item_details,
    )

    return result


def run_remove_purchase_inventory(
    spider: WmsGzbbrSpider,
    logger: logging.Logger,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """执行采购移除自动推送"""
    return _run_flow(spider, logger, dry_run, 3, "采购移除", _process_one_order)
