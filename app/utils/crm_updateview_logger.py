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


def _extract_product_id(payload):
    """从 payload 中提取 product_id，用于日志记录"""
    if isinstance(payload, dict):
        product_id = payload.get("product_id")
        return str(product_id) if product_id is not None else ""
    return ""


def log_update_view_request(source, store_code, payload, response_status, response_msg=None):
    """
    记录一次 updateView 请求日志到数据库。

    日志记录失败不会抛出异常，避免影响主流程。

    :param source: str 调用来源标识，如 'crm_price_sync'
    :param store_code: str 门店/组织代码，如 'fsbbr'
    :param payload: dict 请求参数
    :param response_status: str 响应状态：success / failed / error
    :param response_msg: str 接口返回消息或异常信息
    """
    try:
        sql = """
            INSERT INTO crm_updateview_log
            (source, store_code, product_id, request_payload, response_status, response_msg)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        db_execute(sql, (
            source,
            store_code,
            _extract_product_id(payload),
            json.dumps(payload, ensure_ascii=False, default=str),
            response_status,
            response_msg,
        ))
    except Exception as e:
        print(f"[updateView日志] 记录失败: {e}")


def execute_update_view_with_log(session, payload, source, store_code, headers=None, timeout=30):
    """
    执行 updateView 请求并记录日志。

    :param session: requests.Session 已携带认证信息的会话
    :param payload: dict 请求体
    :param source: str 调用来源标识
    :param store_code: str 门店/组织代码
    :param headers: dict 可选的自定义请求头
    :param timeout: int 请求超时时间（秒）
    :return: (success: bool, msg: str)
    """
    try:
        response = session.post(UPDATE_VIEW_URL, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == 200:
            msg = data.get("msg", "更新成功")
            log_update_view_request(source, store_code, payload, "success", msg)
            return True, msg

        msg = data.get("msg", "更新失败")
        log_update_view_request(source, store_code, payload, "failed", msg)
        return False, msg

    except Exception as e:
        error_msg = f"API调用失败: {e}"
        log_update_view_request(source, store_code, payload, "error", f"{error_msg}\n{traceback.format_exc()}")
        return False, error_msg
