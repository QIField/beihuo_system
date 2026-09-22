# -*- coding:utf-8 -*-
"""
飞书任务同步 - API 客户端

负责调用飞书任务相关接口，含 3 次重试和完整错误日志。
"""

import time
import uuid
import requests

from app.utils.logger_config import get_task_logger
from .auth import get_tenant_access_token, get_app_id
from .config import (
    CREATE_TASK_URL,
    GET_TASK_URL,
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


def _request_with_retry(method, url, action_name, body=None, params=None):
    """
    通用 HTTP 请求封装，含 3 次重试。

    :param method: HTTP 方法（GET/POST/PATCH/DELETE）
    :param url: 请求地址
    :param action_name: 用于日志的动作名称
    :param body: 请求体（POST/PATCH）
    :param params: 查询参数（GET）
    :return: 飞书响应中的 data 字段
    :raises: 重试耗尽后抛出最后一次异常
    """
    last_exc = None
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            logger.info(f"[{action_name}] 第{attempt}次请求, method={method}, url={url}, body={body}, params={params}")
            resp = requests.request(
                method,
                url,
                headers=_request_headers(),
                json=body,
                params=params,
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


def _post_with_retry(url, body, action_name):
    """通用 POST 请求封装（保留给既有调用方）。"""
    return _request_with_retry('POST', url, action_name, body=body)


def _get_with_retry(url, action_name, params=None):
    """通用 GET 请求封装。"""
    return _request_with_retry('GET', url, action_name, params=params)


def _format_time_field(dt):
    """将 datetime 转为飞书任务接口需要的毫秒时间戳字符串"""
    return {"timestamp": str(int(dt.timestamp() * 1000)), "is_all_day": False}


def _build_task_members(owner_open_id):
    """构造任务成员列表：负责人 + 应用关注者（保证能收到状态变更事件）。"""
    members = []
    if owner_open_id:
        members.append({"id": owner_open_id, "type": "user", "role": "assignee"})
    try:
        app_id = get_app_id()
        members.append({"id": app_id, "type": "app", "role": "follower"})
    except Exception as e:
        logger.warning(f"[飞书任务] 获取 app_id 失败，跳过添加应用关注者: {e}")
    return members


def create_lark_task(summary, description=None, start_time=None, due_time=None, owner_open_id=None):
    """
    调用飞书创建任务接口。

    :param summary: 任务标题
    :param description: 任务内容/描述，可选
    :param start_time: 开始时间，datetime 对象，可选
    :param due_time: 截止时间，datetime 对象，可选
    :param owner_open_id: 负责人飞书 open_id，可选
    :return: 飞书响应 data 字段
    :raises: 重试耗尽后抛出最后一次异常
    """
    body = {"summary": summary}
    if description:
        body["description"] = description
    if start_time:
        body["start"] = _format_time_field(start_time)
    if due_time:
        body["due"] = _format_time_field(due_time)

    members = _build_task_members(owner_open_id)
    if members:
        body["members"] = members

    data = _post_with_retry(CREATE_TASK_URL, body, '飞书创建任务')
    logger.info(f"[飞书创建任务] 成功, guid={data['task']['guid']}")
    return data


def create_lark_subtask(parent_guid, summary, due_time=None, owner_open_id=None):
    """
    调用飞书创建子任务接口（父任务必须已存在）。

    文档：POST /open-apis/task/v2/tasks/:task_guid/subtasks

    :param parent_guid: 父任务 GUID
    :param summary: 子任务标题
    :param due_time: 截止时间，datetime 对象，可选
    :param owner_open_id: 负责人飞书 open_id，可选
    :return: 飞书子任务对象 data.subtask
    :raises: 重试耗尽后抛出最后一次异常
    """
    url = f"{CREATE_TASK_URL}/{parent_guid}/subtasks"
    body = {
        "summary": summary,
        "client_token": str(uuid.uuid4()),
    }
    if due_time:
        body["due"] = _format_time_field(due_time)

    members = _build_task_members(owner_open_id)
    if members:
        body["members"] = members

    data = _post_with_retry(url, body, '飞书创建子任务')
    logger.info(f"[飞书创建子任务] 成功, parent_guid={parent_guid}, guid={data['subtask']['guid']}")
    return data['subtask']


def list_lark_subtasks(parent_guid, page_size=100):
    """
    分页拉取一个父任务下的全部子任务（按飞书界面顺序）。

    文档：GET /open-apis/task/v2/tasks/:task_guid/subtasks

    :param parent_guid: 父任务 GUID
    :param page_size: 单页大小，1~100
    :return: 子任务对象列表 data.items
    :raises: 重试耗尽后抛出最后一次异常
    """
    url = f"{GET_TASK_URL}/{parent_guid}/subtasks"
    items = []
    page_token = None
    while True:
        params = {"page_size": page_size, "user_id_type": "open_id"}
        if page_token:
            params["page_token"] = page_token
        data = _get_with_retry(url, '飞书获取子任务列表', params=params)
        items.extend(data.get('items') or [])
        if not data.get('has_more'):
            break
        page_token = data.get('page_token')
        if not page_token:
            break
    logger.info(f"[飞书获取子任务列表] 完成, parent_guid={parent_guid}, count={len(items)}")
    return items


def patch_lark_task(task_guid, task_body, update_fields, action_name='飞书更新任务'):
    """
    更新任务/子任务（标题、描述、时间、完成状态等）。

    文档：PATCH /open-apis/task/v2/tasks/:task_guid
    请求体固定为 {"task": {...}, "update_fields": [...]} 双段结构。
    成员/提醒/清单不能通过本接口修改。

    :param task_guid: 任务或子任务 GUID
    :param task_body: 要更新的字段新值
    :param update_fields: 需要更新的字段名列表
    :param action_name: 日志动作名
    :return: 飞书响应 data 字段
    :raises: 重试耗尽后抛出最后一次异常
    """
    url = f"{GET_TASK_URL}/{task_guid}"
    body = {"task": task_body, "update_fields": update_fields}
    data = _request_with_retry('PATCH', url, action_name, body=body)
    logger.info(f"[{action_name}] 成功, guid={task_guid}, fields={update_fields}")
    return data


def delete_lark_task(task_guid, action_name='飞书删除任务'):
    """
    删除任务/子任务，删除后不可恢复。

    文档：DELETE /open-apis/task/v2/tasks/:task_guid

    :param task_guid: 任务或子任务 GUID
    :return: 飞书响应 data 字段
    :raises: 重试耗尽后抛出最后一次异常
    """
    url = f"{GET_TASK_URL}/{task_guid}"
    data = _request_with_retry('DELETE', url, action_name)
    logger.info(f"[{action_name}] 成功, guid={task_guid}")
    return data


def get_lark_task(task_guid):
    """
    调用飞书查询任务详情接口。

    :param task_guid: 任务 GUID
    :return: 飞书响应 data 字段
    :raises: 重试耗尽后抛出最后一次异常
    """
    url = f"{GET_TASK_URL}/{task_guid}"
    headers = _request_headers()
    last_exc = None

    for attempt in range(1, RETRY_TIMES + 1):
        try:
            logger.info(f"[飞书查询任务] 第{attempt}次请求, url={url}")
            resp = requests.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"[飞书查询任务] 第{attempt}次响应, status={resp.status_code}, result={result}")

            if result.get("code") != 0:
                raise RuntimeError(f"飞书接口返回错误: {result}")

            return result.get("data")
        except Exception as e:
            last_exc = e
            logger.warning(f"[飞书查询任务] 第{attempt}次失败: {e}")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_INTERVAL)

    logger.exception("[飞书查询任务] 多次重试均失败")
    raise last_exc


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
