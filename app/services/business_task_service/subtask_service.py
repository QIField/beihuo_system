# -*- coding:utf-8 -*-
"""
业务子任务 - 业务编排层

职责：子任务清单的本地增删改查，以及本地 → 飞书方向的同步编排。
固定时序：先保证飞书父任务存在（ensure_parent_task_guid），再创建飞书子任务。
本地清单为准，飞书调用失败只记录日志、不阻断本地操作，后续由对账补偿。
"""

from datetime import datetime

from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger
from app.services.lark_task_sync.sync_service import ensure_parent_task_guid
from app.services.lark_task_sync.models import LarkTaskSyncModels
from app.services.lark_task_sync import client as lark_client
from .repository import TaskRepository
from .subtask_repository import SubtaskRepository

logger = get_task_logger('lark_task_sync')

STATUS_PENDING = 0
STATUS_COMPLETED = 1


class SubtaskServiceError(Exception):
    pass


class SubtaskService:

    @staticmethod
    def list_for_task(task_id):
        SubtaskRepository.ensure_table()
        with orm_session() as session:
            rows = SubtaskRepository.list_by_task(session, task_id)
            return [row.to_dict() for row in rows]

    @staticmethod
    def create_many_for_new_task(task_id, titles, assignee_id, created_by=None):
        """
        父任务本地记录已创建后调用（新建任务表单随单子任务）。

        先同步确保飞书父任务存在，再逐条本地入库 + 推送飞书子任务。

        :param task_id: 父业务任务ID
        :param titles: 已清洗的子任务标题列表
        :param assignee_id: 父任务负责人ID（用于取飞书 open_id）
        :param created_by: 创建人ID
        :return: 本地子任务ID列表
        """
        SubtaskRepository.ensure_table()
        parent_guid = SubtaskService._safe_ensure_parent_guid(task_id)
        owner_open_id = SubtaskService._owner_open_id(assignee_id) if parent_guid else None

        subtask_ids = []
        with orm_session() as session:
            for index, title in enumerate(titles):
                row = SubtaskRepository.create(
                    session=session,
                    task_id=task_id,
                    title=title,
                    sort_order=index,
                    created_by=created_by,
                )
                subtask_ids.append(row.id)

        if parent_guid:
            for subtask_id, title in zip(subtask_ids, titles):
                SubtaskService._push_created(subtask_id, parent_guid, title, owner_open_id)
        return subtask_ids

    @staticmethod
    def add(task_id, title, created_by=None):
        """任务详情中追加子任务（父任务必然已存在，直接复用）。"""
        SubtaskRepository.ensure_table()
        title = SubtaskService._validate_title(title)

        with orm_session() as session:
            parent = TaskRepository.get_by_id(session, task_id)
            if not parent:
                raise SubtaskServiceError('父任务不存在')
            assignee_id = parent.assignee_id
            sort_order = SubtaskRepository.next_sort_order(session, task_id)
            row = SubtaskRepository.create(
                session=session,
                task_id=task_id,
                title=title,
                sort_order=sort_order,
                created_by=created_by,
            )
            subtask_id = row.id

        parent_guid = SubtaskService._safe_ensure_parent_guid(task_id)
        if parent_guid:
            owner_open_id = SubtaskService._owner_open_id(assignee_id)
            SubtaskService._push_created(subtask_id, parent_guid, title, owner_open_id)

        return SubtaskService._get_dict(subtask_id)

    @staticmethod
    def update_title(subtask_id, title):
        title = SubtaskService._validate_title(title)
        with orm_session() as session:
            row = SubtaskRepository.get_by_id(session, subtask_id)
            if not row:
                raise SubtaskServiceError('子任务不存在')
            SubtaskRepository.update_title(session, row, title)
            guid = row.lark_subtask_guid

        if guid:
            try:
                lark_client.patch_lark_task(
                    guid,
                    {'summary': title},
                    ['summary'],
                    action_name='飞书更新子任务标题',
                )
            except Exception:
                logger.exception(f"[子任务] 飞书标题同步失败, subtask_id={subtask_id}")
        return SubtaskService._get_dict(subtask_id)

    @staticmethod
    def set_status(subtask_id, status):
        if status not in (STATUS_PENDING, STATUS_COMPLETED):
            raise SubtaskServiceError('状态值不合法')

        completed_at = datetime.now() if status == STATUS_COMPLETED else None
        with orm_session() as session:
            row = SubtaskRepository.get_by_id(session, subtask_id)
            if not row:
                raise SubtaskServiceError('子任务不存在')
            SubtaskRepository.set_status(session, row, status, completed_at)
            guid = row.lark_subtask_guid

        if guid:
            completed_ts = str(int(completed_at.timestamp() * 1000)) if completed_at else '0'
            try:
                lark_client.patch_lark_task(
                    guid,
                    {'completed_at': completed_ts},
                    ['completed_at'],
                    action_name='飞书更新子任务状态',
                )
            except Exception:
                logger.exception(f"[子任务] 飞书状态同步失败, subtask_id={subtask_id}")
        return SubtaskService._get_dict(subtask_id)

    @staticmethod
    def remove(subtask_id):
        with orm_session() as session:
            row = SubtaskRepository.get_by_id(session, subtask_id)
            if not row:
                raise SubtaskServiceError('子任务不存在')
            guid = row.lark_subtask_guid
            SubtaskRepository.delete(session, row)

        if guid:
            try:
                lark_client.delete_lark_task(guid, action_name='飞书删除子任务')
            except Exception:
                logger.exception(f"[子任务] 飞书删除失败, subtask_id={subtask_id}")
        return True

    @staticmethod
    def _push_created(subtask_id, parent_guid, title, owner_open_id):
        """创建飞书子任务并回写 GUID；失败只记录日志，本地清单不受影响。"""
        try:
            subtask = lark_client.create_lark_subtask(
                parent_guid=parent_guid,
                summary=title,
                owner_open_id=owner_open_id,
            )
            with orm_session() as session:
                row = SubtaskRepository.get_by_id(session, subtask_id)
                if row:
                    SubtaskRepository.update_guid(session, row, subtask['guid'])
        except Exception:
            logger.exception(
                f"[子任务] 飞书创建失败, subtask_id={subtask_id}, parent_guid={parent_guid}"
            )

    @staticmethod
    def _safe_ensure_parent_guid(task_id):
        """确保飞书父任务存在；任何异常都降级为仅本地，不阻断清单操作。"""
        try:
            return ensure_parent_task_guid(task_id)
        except Exception:
            logger.exception(f"[子任务] 确保飞书父任务失败, task_id={task_id}")
            return None

    @staticmethod
    def _owner_open_id(assignee_id):
        if not assignee_id:
            return None
        with orm_session() as session:
            mapping = LarkTaskSyncModels.get_user_lark_mapping(session, assignee_id)
            return mapping.lark_open_id if mapping else None

    @staticmethod
    def _validate_title(title):
        title = (title or '').strip()
        if not title:
            raise SubtaskServiceError('子任务标题不能为空')
        return title

    @staticmethod
    def _get_dict(subtask_id):
        with orm_session() as session:
            row = SubtaskRepository.get_by_id(session, subtask_id)
            return row.to_dict() if row else None
