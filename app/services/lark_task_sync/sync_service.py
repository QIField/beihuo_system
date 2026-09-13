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
from .config import RETRY_TIMES, RETRY_DELAYS, LARK_TASK_SYNC_ENABLED_KEY, get_current_env
from .client import create_lark_task
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
    return config and config.config_value == '1'


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

        # 调飞书创建任务
        due_time = task.deadline.strftime('%Y-%m-%dT%H:%M:%S+08:00') if task.deadline else None
        logger.info(
            f"[飞书同步] 开始调用创建任务, business_id={business_task_id}, "
            f"summary={task.title}, owner_open_id={owner_open_id}, due_time={due_time}"
        )
        result = create_lark_task(
            summary=task.title,
            due_time=due_time,
            owner_open_id=owner_open_id,
        )
        logger.info(f"[飞书同步] 飞书创建任务响应, business_id={business_task_id}, result={result}")

        task_guid = result['task']['guid']
        LarkTaskSyncModels.create_mapping(
            session=session,
            business_id=task.id,
            business_type='business_task',
            lark_task_guid=task_guid,
            lark_summary=task.title,
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
    if not _is_sync_enabled():
        return
    task_manager.submit(do_create_lark_task, business_task_id)


def handle_lark_webhook(payload):
    """
    处理飞书任务状态变更回调。

    :param payload: 飞书推送的原始请求体字典
    :return: 处理结果字符串，用于响应飞书
    """
    if not _is_sync_enabled():
        return "success"

    # 解密事件
    encrypt_msg = payload.get('encrypt')
    if not encrypt_msg:
        logger.warning("[飞书回调] 缺少 encrypt 字段")
        return "success"

    event = decrypt_lark_event(encrypt_msg)

    # URL 验证
    if event.get('type') == 'url_verification':
        challenge = event.get('challenge')
        logger.info(f"[飞书回调] URL验证, challenge={challenge}")
        return {"challenge": challenge}

    header = event.get('header', {})
    event_id = header.get('event_id')
    event_type = header.get('event_type')
    event_time = header.get('create_time')

    if not event_id:
        logger.warning("[飞书回调] 缺少 event_id")
        return "success"

    logger.info(f"[飞书回调] 收到事件, event_id={event_id}, type={event_type}")

    if event_type != 'task.updated':
        logger.info(f"[飞书回调] 非任务更新事件, 忽略")
        return "success"

    with orm_session() as session:
        # 幂等
        if LarkTaskSyncModels.is_event_handled(session, event_id):
            logger.info(f"[飞书回调] 事件已处理, event_id={event_id}")
            return "success"

        # 解析任务状态
        event_body = event.get('event', {})
        task_obj = event_body.get('task', {})
        lark_task_guid = task_obj.get('guid')
        completed = task_obj.get('completed', False)

        if not lark_task_guid:
            logger.warning("[飞书回调] 缺少任务 guid")
            return "success"

        # 查映射
        mapping = LarkTaskSyncModels.get_mapping_by_lark_guid(session, lark_task_guid)
        if not mapping:
            logger.warning(f"[飞书回调] 未找到映射, guid={lark_task_guid}")
            return "success"

        # 更新业务任务状态
        new_status = 1 if completed else 0
        LarkTaskSyncModels.update_task_status(session, mapping.business_id, new_status)

        # 记录幂等
        LarkTaskSyncModels.mark_event_handled(session, event_id, event_type, event_time)
        logger.info(f"[飞书回调] 状态更新成功, business_id={mapping.business_id}, status={new_status}")

    return "success"
