# -*- coding:utf-8 -*-
"""
飞书任务同步 - API 客户端

负责调用飞书任务相关接口，含 3 次重试和完整错误日志。
"""

import time
import requests

from app.utils.logger_config import get_task_logger
from .auth import get_tenant_access_token
from .config import CREATE_TASK_URL, REQUEST_TIMEOUT, RETRY_TIMES, RETRY_INTERVAL

logger = get_task_logger('lark_task_sync')


def _request_headers():
    return {
        "Authorization": f"Bearer {get_tenant_access_token()}",
        "Content-Type": "application/json; charset=utf-8",
    }


def create_lark_task(summary, due_time=None, owner_open_id=None):
    """
    调用飞书创建任务接口。

    :param summary: 任务标题
    :param due_time: 截止时间，ISO8601 格式字符串，可选
    :param owner_open_id: 负责人飞书 open_id，可选
    :return: 飞书响应 data 字段
    :raises: 重试耗尽后抛出最后一次异常
    """
    body = {"summary": summary}
    if due_time:
        body["due_time"] = {"timestamp": due_time, "is_all_day": False}
    if owner_open_id:
        body["owner"] = {"id": owner_open_id, "type": "user"}

    last_exc = None
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            logger.info(f"[飞书创建任务] 第{attempt}次请求, summary={summary}")
            resp = requests.post(
                CREATE_TASK_URL,
                headers=_request_headers(),
                json=body,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            result = resp.json()

            if result.get("code") != 0:
                raise RuntimeError(f"飞书接口返回错误: {result}")

            logger.info(f"[飞书创建任务] 成功, guid={result['data']['task']['guid']}")
            return result["data"]

        except Exception as e:
            last_exc = e
            logger.warning(f"[飞书创建任务] 第{attempt}次失败: {e}")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_INTERVAL)

    logger.exception("[飞书创建任务] 3次重试均失败")
    raise last_exc
