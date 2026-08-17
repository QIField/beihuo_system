#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CRM updateView 接口统一调用与日志记录工具

所有调用 https://crm.gzbbr.com/api/Product.Product/updateView 的地方，
统一使用本模块提供的函数，自动将请求参数、门店/组织来源、响应结果写入数据库。
"""

import json
import traceback

from app.utils.database_connection import db_execute


UPDATE_VIEW_URL = "https://crm.gzbbr.com/api/Product.Product/updateView"
VIEW_URL = "https://crm.gzbbr.com/api/Product.Product/view"

ALL_VIEW_FIELDS = [
    "product_id", "cass_desc", "brand_code", "l_name_zh_store",
    "brand_barcode", "store_cass_price", "store_peer_price",
    "qpl_price", "cost_price", "manufacturer_price",
]

# 需要单独记录原始值的字段（product_id 已有独立字段，不再重复）
ORIGINAL_FIELDS = [f for f in ALL_VIEW_FIELDS if f != "product_id"]

# 从 view 接口额外爬取、仅用于数据库记录的字段（不加入 updateView payload）
EXTRA_LOG_FIELDS = [
    ("brand_name", "更新品牌"),
    ("number", "更新oe"),
]


def _extract_product_id(payload):
    """从 payload 中提取 product_id，用于日志记录"""
    if isinstance(payload, dict):
        product_id = payload.get("product_id")
        return str(product_id) if product_id is not None else ""
    return ""


def _extract_original_values(view_data):
    """从 /view 返回的数据中提取需要记录的原始字段值"""
    if not isinstance(view_data, dict):
        return {}
    return {
        field: (str(view_data[field]) if view_data.get(field) is not None else None)
        for field in ORIGINAL_FIELDS
    }


def _extract_extra_values(view_data):
    """从 /view 返回的数据中提取额外记录字段（不加入 updateView payload）"""
    if not isinstance(view_data, dict):
        return {}
    return {
        field: (str(view_data[field]) if view_data.get(field) is not None else None)
        for field, _ in EXTRA_LOG_FIELDS
    }


def log_update_view_request(source, store_code, payload, response_status, response_msg=None, original_values=None, extra_original_values=None):
    """
    记录一次 updateView 请求日志到数据库。

    日志记录失败不会抛出异常，避免影响主流程。

    :param source: str 调用来源标识，如 'crm_price_sync'
    :param store_code: str 门店/组织代码，如 'fsbbr'
    :param payload: dict 请求参数
    :param response_status: str 响应状态：success / failed / error
    :param response_msg: str 接口返回消息或异常信息
    :param original_values: dict 调用前从 /view 接口获取的原始字段值
    :param extra_original_values: dict 调用前从 /view 接口获取的额外记录字段值
    """
    try:
        original_values = original_values or {}
        extra_original_values = extra_original_values or {}
        sql = """
            INSERT INTO crm_updateview_log
            (source, store_code, product_id, request_payload,
             original_cass_desc, original_brand_code, original_l_name_zh_store,
             original_brand_barcode, original_store_cass_price, original_store_peer_price,
             original_qpl_price, original_cost_price, original_manufacturer_price,
             更新品牌, 更新oe,
             response_status, response_msg)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            source,
            store_code,
            _extract_product_id(payload),
            json.dumps(payload, ensure_ascii=False, default=str),
        ]
        for field in ORIGINAL_FIELDS:
            params.append(original_values.get(field))
        for field, _ in EXTRA_LOG_FIELDS:
            params.append(extra_original_values.get(field))
        params.extend([response_status, response_msg])

        db_execute(sql, tuple(params))
    except Exception as e:
        print(f"[updateView日志] 记录失败: {e}")


def execute_update_view_with_log(session, payload, source, store_code, headers=None, timeout=30, original_values=None, extra_original_values=None):
    """
    执行 updateView 请求并记录日志。

    :param session: requests.Session 已携带认证信息的会话
    :param payload: dict 请求体
    :param source: str 调用来源标识
    :param store_code: str 门店/组织代码
    :param headers: dict 可选的自定义请求头
    :param timeout: int 请求超时时间（秒）
    :param original_values: dict 可选的 /view 原始字段值
    :param extra_original_values: dict 可选的 /view 额外记录字段值
    :return: (success: bool, msg: str)
    """
    try:
        response = session.post(UPDATE_VIEW_URL, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == 200:
            msg = data.get("msg", "更新成功")
            log_update_view_request(source, store_code, payload, "success", msg, original_values, extra_original_values)
            return True, msg

        msg = data.get("msg", "更新失败")
        log_update_view_request(source, store_code, payload, "failed", msg, original_values, extra_original_values)
        return False, msg

    except Exception as e:
        error_msg = f"API调用失败: {e}"
        log_update_view_request(source, store_code, payload, "error", f"{error_msg}\n{traceback.format_exc()}", original_values, extra_original_values)
        return False, error_msg


def fetch_view_then_update(session, product_id, new_values, source, store_code, headers=None, timeout=30):
    """
    先查询产品视图获取完整字段，将新值与原值合并后调用 updateView。

    :param session: requests.Session 已携带认证信息的会话
    :param product_id: str 产品ID
    :param new_values: dict 需要更新的字段（仅包含有值的字段）
    :param source: str 调用来源标识
    :param store_code: str 门店/组织代码
    :param headers: dict 可选的自定义请求头
    :param timeout: int 请求超时时间（秒）
    :return: (success: bool, msg: str)
    """
    # 1. 查询 view 接口
    try:
        response = session.get(
            VIEW_URL,
            params={"product_id": product_id},
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != 200:
            error_msg = f"查询view失败: {data.get('msg', '未知错误')}"
            log_update_view_request(source, store_code, {"product_id": product_id}, "error", error_msg)
            return False, error_msg

        view_data = data.get("data", {})
    except Exception as e:
        error_msg = f"查询view失败: {e}"
        log_update_view_request(source, store_code, {"product_id": product_id}, "error", error_msg)
        return False, error_msg

    # 2. 合并字段：view 原值为底，new_values 覆盖
    payload = {}
    for field in ALL_VIEW_FIELDS:
        if field in new_values:
            payload[field] = new_values[field]
        elif field in view_data:
            payload[field] = view_data[field]
        else:
            payload[field] = None if field != "product_id" else str(product_id)

    # 确保 product_id 正确
    payload["product_id"] = str(product_id)

    # 3. 提取原始字段值并调用 updateView
    original_values = _extract_original_values(view_data)
    extra_original_values = _extract_extra_values(view_data)
    return execute_update_view_with_log(
        session=session,
        payload=payload,
        source=source,
        store_code=store_code,
        headers=headers,
        timeout=timeout,
        original_values=original_values,
        extra_original_values=extra_original_values,
    )
