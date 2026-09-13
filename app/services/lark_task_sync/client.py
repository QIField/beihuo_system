# -*- coding:utf-8 -*-
"""
飞书任务同步 - API 客户端

负责调用飞书任务相关接口，含 3 次重试和完整错误日志。
"""

import time
import requests

from app.utils.logger_config import get_task_logger
from .auth import get_tenant_access_token
from .config import (
    CREATE_TASK_URL,
    BATCH_GET_USER_ID_URL,
    REQUEST_TIMEOUT,
    RETRY_TIMES,
    RETRY_INTERVAL,
)

logger = get_task_logger('lark_task_sync')


def _request_headers():
    return {
        "Authorization": f"Bearer {get_tenant_access_token()}",
        "Content-Type": "application/json; charset=utf-8",
    }


def _post_with_retry(url, body, action_name):
    """
    通用 POST 请求封装，含 3 次重试。

    :param url: 请求地址
    :param body: 请求体
    :param action_name: 用于日志的动作名称
    :return: 飞书响应中的 data 字段
    :raises: 重试耗尽后抛出最后一次异常
    """
    last_exc = None
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            logger.info(f"[{action_name}] 第{attempt}次请求, url={url}, body={body}")
            resp = requests.post(
                url,
                headers=_request_headers(),
                json=body,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"[{action_name}] 第{attempt}次响应, status={resp.status_code}, result={result}")

            if result.get("code") != 0:
                raise RuntimeError(f"飞书接口返回错误: {result}")

            return result.get("data")

        except requests.exceptions.HTTPError as e:
            last_exc = e
            try:
                resp_text = resp.text
            except Exception:
                resp_text = '<无法读取响应>'
            logger.warning(f"[{action_name}] 第{attempt}次HTTP失败: status={resp.status_code}, response={resp_text}, error={e}")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_INTERVAL)
        except Exception as e:
            last_exc = e
            logger.warning(f"[{action_name}] 第{attempt}次失败: {e}")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_INTERVAL)

    logger.exception(f"[{action_name}] {RETRY_TIMES}次重试均失败")
    raise last_exc


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
        body["members"] = [{"id": owner_open_id, "type": "user", "role": "assignee"}]

    data = _post_with_retry(CREATE_TASK_URL, body, '飞书创建任务')
    logger.info(f"[飞书创建任务] 成功, guid={data['task']['guid']}")
    return data


def _chunk_list(items, size):
    """将列表按指定大小分批。"""
    for i in range(0, len(items), size):
        yield items[i:i + size]


def batch_get_lark_user_ids(mobiles=None, emails=None, batch_size=50):
    """
    调用飞书 batch_get_id 接口，通过手机号/邮箱批量获取用户 open_id/union_id。

    接口文档：https://open.feishu.cn/document/server-docs/contact-v3/user/batch_get_id

    :param mobiles: 手机号列表，可选
    :param emails: 邮箱列表，可选
    :param batch_size: 每批最大数量，默认 50
    :return: {
        'mobiles': {'138xxxx': {'open_id': 'ou_xxx', 'union_id': 'on_xxx'}, ...},
        'emails':  {'a@b.com': {'open_id': 'ou_xxx', 'union_id': 'on_xxx'}, ...},
    }
    :raises: 任一批次重试耗尽后抛出异常
    """
    mobiles = mobiles or []
    emails = emails or []

    result = {'mobiles': {}, 'emails': {}}

    for chunk in _chunk_list(mobiles, batch_size):
        data = _post_with_retry(
            BATCH_GET_USER_ID_URL,
            {'mobiles': chunk},
            '飞书批量反查用户ID-mobiles',
        )
        for item in data.get('user_list', []):
            mobile = item.get('mobile')
            if not mobile:
                continue
            # 飞书 batch_get_id 接口用 user_id 字段返回 open_id
            open_id = item.get('open_id') or item.get('user_id')
            result['mobiles'][mobile] = {
                'open_id': open_id,
                'union_id': item.get('union_id'),
                'user_id': item.get('user_id'),
            }

    for chunk in _chunk_list(emails, batch_size):
        data = _post_with_retry(
            BATCH_GET_USER_ID_URL,
            {'emails': chunk},
            '飞书批量反查用户ID-emails',
        )
        for item in data.get('user_list', []):
            email = item.get('email')
            if not email:
                continue
            # 飞书 batch_get_id 接口用 user_id 字段返回 open_id
            open_id = item.get('open_id') or item.get('user_id')
            result['emails'][email] = {
                'open_id': open_id,
                'union_id': item.get('union_id'),
                'user_id': item.get('user_id'),
            }

    logger.info(
        f"[飞书批量反查用户ID] 完成, "
        f"mobiles命中={len(result['mobiles'])}, emails命中={len(result['emails'])}"
    )
    return result
