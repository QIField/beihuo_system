# -*- coding:utf-8 -*-
"""
多渠道报价调价 - 价格更新服务

职责：
- 根据 product_id 查询 data.gzbbr.com 公司价格
- 使用用户填写的卖价更新 price 和 peer_price
- 记录更新日志
"""

import json
from typing import Dict, Any, List

from app.utils.data_gzbbr import DataGzbbrApiClient, CookieExpiredError
from app.utils.logger_config import get_task_logger
from app.services.multi_channel_quote_adjust_service.repository import (
    save_update_log,
    delete_import_record,
)

logger = get_task_logger('multi_channel_quote_adjust')


def _build_request_params(payload: Dict[str, Any]) -> str:
    """将 payload 字典拼接为 k=v&k=v 格式字符串"""
    return "&".join([f"{k}={v}" for k, v in payload.items()])


def _is_update_success(response: Dict[str, Any]) -> bool:
    """判断 update 接口是否返回成功格式"""
    return response.get("status") == "00" and response.get("msg") == "修改成功"


def _do_update_one(
    client: DataGzbbrApiClient,
    company: str,
    product_id: str,
    price: str,
    peer_price: str,
    oe: str,
    create_by: str,
) -> Dict[str, Any]:
    """
    执行单条价格更新，返回 detail 与 data

    Returns:
        (detail, data)
        detail: {"product_id": ..., "cass_price": ..., "peer_price": ..., "status": ..., "msg": ...}
        data: {"index_info": ..., "request_params": ..., "update_result": ...} or None
    """
    detail = {
        "product_id": product_id,
        "cass_price": price,
        "peer_price": peer_price,
        "status": "失败",
        "msg": "",
    }
    data = None

    if not product_id:
        detail["msg"] = "product_id 不能为空"
        return detail, data

    if not price or not peer_price:
        detail["msg"] = "开思价和同行价均不能为空"
        return detail, data

    try:
        index_result = client.get_company_price(product_id)
        rows = index_result.get("rows", [])
        if not rows:
            detail["msg"] = "未找到公司价格记录"
            _save_log(
                company=company,
                product_id=product_id,
                sell_price=price,
                oe=oe,
                create_by=create_by,
                status="失败",
                error_msg=detail["msg"],
            )
            return detail, data

        base_info = rows[0]
        payload, update_result = client.update_company_price(base_info, price, peer_price)
        data = {
            "index_info": base_info,
            "request_params": _build_request_params(payload),
            "update_result": update_result,
        }

        if _is_update_success(update_result):
            detail["status"] = "成功"
            detail["msg"] = "更新成功"
            _save_log(
                company=company,
                product_id=product_id,
                sell_price=price,
                oe=oe,
                create_by=create_by,
                base_info=base_info,
                payload=payload,
                update_result=None,
                status="成功",
                error_msg="",
            )
            try:
                delete_import_record(company, oe, product_id)
            except Exception as e:
                detail["msg"] += f"（删除导入记录失败: {e}）"
        else:
            detail["msg"] = update_result.get("msg", "更新失败")
            _save_log(
                company=company,
                product_id=product_id,
                sell_price=price,
                oe=oe,
                create_by=create_by,
                base_info=base_info,
                payload=payload,
                update_result=update_result,
                status="失败",
                error_msg=detail["msg"],
            )
    except CookieExpiredError:
        raise
    except Exception as e:
        import traceback
        detail["msg"] = f"异常: {e}"
        _save_log(
            company=company,
            product_id=product_id,
            sell_price=price,
            oe=oe,
            create_by=create_by,
            status="失败",
            error_msg=detail["msg"],
        )

    return detail, data


def update_product_sell_price(company: str, product_id: str, price: str, peer_price: str, oe: str = "") -> Dict[str, Any]:
    """
    更新指定产品的开思价和同行价到公司价格系统，并记录日志

    Args:
        company: 公司代码，如 fsbbr, zhbbr
        product_id: 产品 ID
        price: 开思价
        peer_price: 同行价
        oe: 可选，OE号

    Returns:
        {
            "success": bool,
            "msg": str,
            "data": dict or None
        }
    """
    if not product_id:
        return {"success": False, "msg": "product_id 不能为空", "data": None}

    price = str(price).strip() if price is not None else ""
    peer_price = str(peer_price).strip() if peer_price is not None else ""

    if not price or not peer_price:
        return {"success": False, "msg": "开思价和同行价均不能为空", "data": None}

    client = DataGzbbrApiClient(company, logger=logger)
    detail, data = _do_update_one(client, company, product_id, price, peer_price, oe, create_by="")

    return {
        "success": detail["status"] == "成功",
        "msg": detail["msg"],
        "data": data,
    }


def batch_update_sell_price(company: str, updates: List[Dict[str, Any]], create_by: str = "") -> Dict[str, Any]:
    """
    批量更新产品卖价

    Args:
        company: 公司代码
        updates: 更新列表，每项包含 product_id, cass_price, peer_price, oe
        create_by: 操作人

    Returns:
        {
            "success_count": int,
            "fail_count": int,
            "details": [...]
        }
    """
    success_count = 0
    fail_count = 0
    details = []

    client = DataGzbbrApiClient(company, logger=logger)

    for item in updates:
        product_id = item.get("product_id")
        price = str(item.get("cass_price") or "").strip()
        peer_price = str(item.get("peer_price") or "").strip()
        oe = item.get("oe", "")

        detail, _ = _do_update_one(client, company, product_id, price, peer_price, oe, create_by)
        details.append(detail)

        if detail["status"] == "成功":
            success_count += 1
        else:
            fail_count += 1

    return {
        "success_count": success_count,
        "fail_count": fail_count,
        "details": details,
    }


def _save_log(
    company: str,
    product_id: str,
    sell_price: str,
    oe: str,
    create_by: str,
    base_info: Dict[str, Any] = None,
    payload: Dict[str, Any] = None,
    update_result: Dict[str, Any] = None,
    status: str = "",
    error_msg: str = "",
) -> None:
    """封装更新日志写入"""
    log_item = {
        "company": company,
        "oe": oe or "",
        "product_id": product_id or "",
        "sell_price": str(sell_price) if sell_price is not None else "",
        "company_price_id": base_info.get("company_price_id") if base_info else "",
        "index_product_id": base_info.get("product_id") if base_info else "",
        "company_id": base_info.get("company_id") if base_info else "",
        "company_name": base_info.get("company_name") if base_info else "",
        "original_price": base_info.get("price") if base_info else "",
        "original_peer_price": base_info.get("peer_price") if base_info else "",
        "min_quantity": base_info.get("min_quantity") if base_info else 1,
        "start_date": _timestamp_to_str(base_info.get("start_date")) if base_info else "",
        "end_date": _timestamp_to_str(base_info.get("end_date")) if base_info else "",
        "price_status": base_info.get("status") if base_info else 1,
        "update_request_params": _build_request_params(payload) if payload else "",
        "update_response": json.dumps(update_result, ensure_ascii=False) if update_result is not None else None,
        "status": status,
        "error_msg": error_msg,
        "create_by": create_by,
    }
    save_update_log(log_item)


def _timestamp_to_str(ts: Any) -> str:
    """将 Unix 时间戳转为字符串"""
    if ts is None or ts == "":
        return ""
    try:
        import datetime as dt
        return dt.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return str(ts)
