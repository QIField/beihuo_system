# -*- coding:utf-8 -*-
"""
飞书任务同步 - 业务编排层

负责：
1. 业务任务创建后异步同步到飞书
2. 接收飞书回调并更新业务任务状态
"""

import time
from datetime import datetime

from app.core.task_manager import task_manager
from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger
from app.sockets.notification_manager import notification_manager
from .config import RETRY_TIMES, RETRY_DELAYS, LARK_TASK_SYNC_ENABLED_KEY, get_current_env
from .client import create_lark_task, get_lark_task, subscribe_task_events
from .crypto import decrypt_lark_event
from .models import LarkTaskSyncModels

logger = get_task_logger('lark_task_sync')


def _is_sync_enabled():
    """读取同步开关"""
    from app.models.orm_models import BeihuoSystemConfig
    with orm_session() as session:
        config = session.query(BeihuoSystemConfig).filter(
            BeihuoSystemConfig.config_key == LARK_TASK_SYNC_ENABLED_KEY,
            BeihuoSystemConfig.env == get_current_env(),
            BeihuoSystemConfig.status == 1,
        ).first()
        return bool(config and config.config_value == '1')


def _do_sync_once(business_task_id, attempt=1):
    """单次同步执行，成功后返回 True"""
    with orm_session() as session:
        task = LarkTaskSyncModels.get_task_by_id(session, business_task_id)
        if not task:
            logger.warning(f"[飞书同步] 业务任务不存在, id={business_task_id}")
            return True

        # 已同步则跳过
        existing = LarkTaskSyncModels.get_mapping_by_business_id(session, business_task_id)
        if existing:
            logger.info(f"[飞书同步] 已存在映射, business_id={business_task_id}")
            return True

        # 查用户映射
        user_mapping = LarkTaskSyncModels.get_user_lark_mapping(session, task.assignee_id)
        owner_open_id = user_mapping.lark_open_id if user_mapping else None
        if not owner_open_id:
            logger.warning(f"[飞书同步] 负责人未绑定飞书, user_id={task.assignee_id}")
            # 无映射不算失败，停止重试
            return True

        # 在 session 内读取所有需要字段，避免调用飞书期间 session 过期导致 detached
        task_id = task.id
        task_title = task.title
        task_deadline = task.deadline

    # 调飞书创建任务（网络请求，耗时较长，不在 orm_session 内执行）
    due_time = task_deadline.strftime('%Y-%m-%dT%H:%M:%S+08:00') if task_deadline else None
    logger.info(
        f"[飞书同步] 开始调用创建任务, business_id={business_task_id}, "
        f"summary={task_title}, owner_open_id={owner_open_id}, due_time={due_time}"
    )
    result = create_lark_task(
        summary=task_title,
        due_time=due_time,
        owner_open_id=owner_open_id,
    )
    logger.info(f"[飞书同步] 飞书创建任务响应, business_id={business_task_id}, result={result}")

    task_guid = result['task']['guid']

    # 建立 Task V2 事件订阅关系（幂等，失败不影响任务创建）
    try:
        subscribe_task_events()
        logger.info(f"[飞书同步] TaskV2事件订阅成功, business_id={business_task_id}")
    except Exception as sub_err:
        logger.warning(f"[飞书同步] TaskV2事件订阅失败（非阻塞）: {sub_err}")

    # 重新开启 session 写入映射
    with orm_session() as session:
        LarkTaskSyncModels.create_mapping(
            session=session,
            business_id=task_id,
            business_type='business_task',
            lark_task_guid=task_guid,
            lark_summary=task_title,
            owner_open_id=owner_open_id,
        )
    logger.info(f"[飞书同步] 成功, business_id={business_task_id}, guid={task_guid}")
    return True


def do_create_lark_task(business_task_id, attempt=1):
    """
    同步业务任务到飞书，失败按阶梯重试。

    :param business_task_id: 业务任务ID
    :param attempt: 当前重试次数
    """
    if not _is_sync_enabled():
        logger.info(f"[飞书同步] 开关关闭, 跳过 business_id={business_task_id}")
        return

    if attempt > RETRY_TIMES:
        logger.error(f"[飞书同步] 3次重试均失败, business_id={business_task_id}")
        return

    try:
        success = _do_sync_once(business_task_id, attempt)
        if success:
            return
    except Exception:
        logger.exception(f"[飞书同步] 第{attempt}次失败, business_id={business_task_id}")

    if attempt < RETRY_TIMES:
        delay = RETRY_DELAYS.get(attempt + 1, 300)
        logger.info(f"[飞书同步] {delay}秒后开始第{attempt + 1}次重试, business_id={business_task_id}")
        time.sleep(delay)
        do_create_lark_task(business_task_id, attempt + 1)


def submit_create_lark_task(business_task_id):
    """
    业务创建任务后调用，提交异步同步任务。
    """
    logger.info(f"[飞书同步] 收到同步提交, business_id={business_task_id}")
    if not _is_sync_enabled():
        logger.info(f"[飞书同步] 开关关闭, 跳过 business_id={business_task_id}")
        return
    logger.info(f"[飞书同步] 提交异步任务, business_id={business_task_id}")
    task_manager.submit(do_create_lark_task, business_task_id)


def handle_lark_webhook(payload):
    """
    处理飞书任务状态变更回调。

    :param payload: 飞书推送的原始请求体字典
    :return: 处理结果字符串，用于响应飞书
    """
    logger.info(f"[飞书回调] 进入处理, payload={payload}")

    # 明文 URL 验证（未配置 Encrypt Key 时）
    if payload.get('type') == 'url_verification':
        challenge = payload.get('challenge')
        logger.info(f"[飞书回调] URL验证(明文), challenge={challenge}")
        return {"challenge": challenge}

    if not _is_sync_enabled():
        logger.info("[飞书回调] 同步开关关闭, 忽略回调")
        return "success"

    # 解密事件
    encrypt_msg = payload.get('encrypt')
    if not encrypt_msg:
        logger.warning("[飞书回调] 缺少 encrypt 字段")
        return "success"

    event = decrypt_lark_event(encrypt_msg)
    logger.info(f"[飞书回调] 解密后事件, event={event}")

    # 加密 URL 验证（配置 Encrypt Key 后）
    if event.get('type') == 'url_verification':
        challenge = event.get('challenge')
        logger.info(f"[飞书回调] URL验证(加密), challenge={challenge}")
        return {"challenge": challenge}

    header = event.get('header', {})
    event_id = header.get('event_id')
    event_type = header.get('event_type')
    event_time = header.get('create_time')

    logger.info(
        f"[飞书回调] 解析事件头, event_id={event_id}, "
        f"event_type={event_type}, event_time={event_time}"
    )

    if not event_id:
        logger.warning("[飞书回调] 缺少 event_id")
        return "success"

    V1_TYPES = ('task.task.updated_v1', 'task.task.update_tenant_v1')
    V2_TYPE = 'task.task.update_user_access_v2'

    if event_type not in V1_TYPES and event_type != V2_TYPE:
        logger.info(f"[飞书回调] 非任务更新事件, 忽略, event_type={event_type}")
        return "success"

    with orm_session() as session:
        # 幂等
        if LarkTaskSyncModels.is_event_handled(session, event_id):
            logger.info(f"[飞书回调] 事件已处理, event_id={event_id}")
            return "success"

        event_body = event.get('event', {})
        logger.info(f"[飞书回调] 事件体, event_body={event_body}")

        resolved = _resolve_task_status_change(event)
        if not resolved:
            logger.info("[飞书回调] 非完成/取消完成相关变更, 忽略")
            return "success"

        lark_task_guid, new_status = resolved
        if not lark_task_guid:
            logger.warning("[飞书回调] 缺少任务 GUID")
            return "success"

        # 查映射
        mapping = LarkTaskSyncModels.get_mapping_by_lark_guid(session, lark_task_guid)
        if not mapping:
            logger.warning(f"[飞书回调] 未找到映射, guid={lark_task_guid}")
            return "success"

        logger.info(f"[飞书回调] 找到映射, business_id={mapping.business_id}, guid={lark_task_guid}")

        # 更新业务任务状态
        LarkTaskSyncModels.update_task_status(session, mapping.business_id, new_status)

        # 记录幂等
        LarkTaskSyncModels.mark_event_handled(session, event_id, event_type, event_time)
        logger.info(f"[飞书回调] 状态更新成功, business_id={mapping.business_id}, status={new_status}")

        # 推送 WebSocket 通知，让网页端实时刷新
        try:
            notification_manager.send_data_update(
                data_type='business_task',
                action='update',
                record_id=str(mapping.business_id),
                data={
                    'status': new_status,
                    'lark_task_guid': lark_task_guid,
                },
            )
            logger.info(f"[飞书回调] WebSocket通知已发送, business_id={mapping.business_id}")
        except Exception as notify_err:
            logger.warning(f"[飞书回调] WebSocket通知发送失败: {notify_err}")

    return "success"


def _resolve_task_status_change(event):
    """
    从 V1/V2 任务事件中解析出任务 GUID 和新的完成状态。

    :return: (task_guid, status) 元组；status=1 已完成, status=0 未完成。
             如果与完成状态无关，返回 None。
    """
    header = event.get('header', {})
    event_type = header.get('event_type')
    event_body = event.get('event', {})

    # V1 事件：obj_type 5=完成, 6=取消完成
    if event_type in ('task.task.updated_v1', 'task.task.update_tenant_v1'):
        obj_type = event_body.get('obj_type')
        if obj_type not in (5, 6):
            return None
        return event_body.get('task_id'), 1 if obj_type == 5 else 0

    # V2 事件：task.task.update_user_access_v2
    if event_type == 'task.task.update_user_access_v2':
        event_types = event_body.get('event_types') or []
        if 'task_completed_update' not in event_types and 'task_todo_update' not in event_types:
            return None

        task_guid = event_body.get('task_guid')
        if not task_guid:
            return None

        # V2 事件本身不携带完成状态，需要反查任务详情
        task_data = get_lark_task(task_guid)
        completed_at = task_data.get('task', {}).get('completed_at')
        is_completed = bool(completed_at and str(completed_at) not in ('0', ''))
        return task_guid, 1 if is_completed else 0

    return None
