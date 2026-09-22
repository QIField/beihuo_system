# -*- coding:utf-8 -*-
"""
飞书子任务 → 本地 对账编排

按父任务拉取飞书子任务列表，与本地 business_subtask 清单比对：
1. 已存在（按 lark_subtask_guid 匹配）：回写状态/标题；
2. 飞书侧新建、本地缺失：补录为本地子任务。

本地已删除项不在此物理删除，避免误删；删除以本地操作为准。
"""

from datetime import datetime

from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger

from .client import list_lark_subtasks
from .models import LarkTaskSyncModels
from app.services.business_task_service.subtask_repository import SubtaskRepository

logger = get_task_logger('lark_task_sync')


def _parse_remote_completed(item):
    """解析飞书子任务完成状态，返回 (status, completed_at)。"""
    completed_at_raw = item.get('completed_at')
    if not completed_at_raw or str(completed_at_raw) in ('0', ''):
        return 0, None
    completed_at = datetime.fromtimestamp(int(completed_at_raw) / 1000)
    return 1, completed_at


def reconcile_subtasks(business_id):
    """
    拉取指定父任务的飞书子任务并对账回写本地。

    :param business_id: 父业务任务ID
    :return: 对账结果字典
    """
    SubtaskRepository.ensure_table()

    with orm_session() as session:
        mapping = LarkTaskSyncModels.get_mapping_by_business_id(session, business_id)
        if not mapping:
            logger.info(f"[飞书子任务对账] 父任务无飞书映射, business_id={business_id}")
            return {'code': 404, 'msg': '父任务未同步到飞书', 'data': None}

        parent_guid = mapping.lark_task_guid
        local_rows = SubtaskRepository.list_by_task(session, business_id)
        local_by_guid = {
            row.lark_subtask_guid: row for row in local_rows if row.lark_subtask_guid
        }

        # 与既有 sync_task_status_from_lark 一致：网络调用在 session 内完成
        remote_items = list_lark_subtasks(parent_guid)

        updated = 0
        created = 0
        next_order = len(local_rows)
        for index, item in enumerate(remote_items):
            guid = item.get('guid')
            summary = item.get('summary') or ''
            status, completed_at = _parse_remote_completed(item)

            row = local_by_guid.get(guid)
            if row:
                changed = False
                if row.status != status:
                    row.status = status
                    row.completed_at = completed_at
                    changed = True
                elif status == 1 and not row.completed_at:
                    row.completed_at = completed_at
                    changed = True
                if summary and row.title != summary:
                    row.title = summary
                    changed = True
                if changed:
                    session.flush()
                    updated += 1
            else:
                SubtaskRepository.create(
                    session=session,
                    task_id=business_id,
                    title=summary or '(未命名子任务)',
                    sort_order=next_order + index,
                    lark_subtask_guid=guid,
                    status=status,
                    completed_at=completed_at,
                )
                created += 1

    logger.info(
        f"[飞书子任务对账] 完成, business_id={business_id}, "
        f"remote={len(remote_items)}, updated={updated}, created={created}"
    )
    return {
        'code': 0,
        'msg': 'success',
        'data': {
            'business_id': business_id,
            'remote_count': len(remote_items),
            'updated': updated,
            'created': created,
        },
    }
