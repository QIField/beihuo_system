# -*- coding: utf-8 -*-
"""
物料在途库存同步 - API 客户端

负责调用"获取物料在途库存列表"接口，含超时与网络异常重试。
"""

import time

import requests

from app.utils.logger_config import get_task_logger
from .config import API_URL, REQUEST_TIMEOUT, RETRY_TIMES, RETRY_INTERVAL

logger = get_task_logger('b2b_intransit_sync')


def fetch_in_transit_stock(token):
    """
    调用在途库存列表接口

    :param token: B2B 平台 token（放入请求头）
    :return: 接口响应 JSON（dict）；"暂无数据"时返回 {'status': 404, 'data': []}
    :raises: 重试耗尽后抛出最后一次网络异常
    """
    headers = {'token': token}
    last_exc = None

    for attempt in range(1, RETRY_TIMES + 1):
        try:
            response = requests.get(API_URL, headers=headers, timeout=REQUEST_TIMEOUT)
            logger.info(f"[在途接口] 第{attempt}次请求 HTTP {response.status_code}")

            try:
                return response.json()
            except ValueError:
                text = response.text or ''
                # 文档约定失败(404)返回纯文本"暂无数据"，视为空列表
                if response.status_code == 404 or '暂无数据' in text:
                    return {'status': 404, 'msg': '暂无数据', 'data': []}
                raise ValueError(f"响应非JSON: HTTP {response.status_code}, body={text[:200]}")

        except requests.exceptions.RequestException as e:
            last_exc = e
            logger.warning(f"[在途接口] 网络请求异常(第{attempt}次): {e}")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_INTERVAL)

    raise last_exc
