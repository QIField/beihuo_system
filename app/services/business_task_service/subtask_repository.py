# -*- coding:utf-8 -*-
"""
业务子任务 - 数据访问层

职责：只负责 business_subtask 表的查询与写入，不做业务编排。
"""

from app.models.orm_models import BusinessSubtask
from app.models.orm_models.base_models import BaseModels
from app.utils.orm.session import get_engine


class SubtaskRepository:

    _table_ensured = False

    @classmethod
    def ensure_table(cls):
        """幂等建表（IF NOT EXISTS），每进程只执行一次。"""
        if cls._table_ensured:
            return
        BaseModels.metadata.create_all(
            get_engine(),
            tables=[BusinessSubtask.__table__],
        )
        cls._table_ensured = True

    @staticmethod
    def create(session, task_id, title, sort_order, created_by=None,
               status=0, lark_subtask_guid=None, completed_at=None, assignee_id=None):
        subtask = BusinessSubtask(
            task_id=task_id,
            title=title,
            assignee_id=assignee_id,
            sort_order=sort_order,
            created_by=created_by,
            status=status,
            lark_subtask_guid=lark_subtask_guid,
            completed_at=completed_at,
        )
        session.add(subtask)
        session.flush()
        return subtask

    @staticmethod
    def get_by_id(session, subtask_id):
        return session.query(BusinessSubtask).filter(
            BusinessSubtask.id == subtask_id
        ).first()

    @staticmethod
    def get_by_lark_guid(session, lark_guid):
        return session.query(BusinessSubtask).filter(
            BusinessSubtask.lark_subtask_guid == lark_guid
        ).first()

    @staticmethod
    def list_by_task(session, task_id):
        return session.query(BusinessSubtask).filter(
            BusinessSubtask.task_id == task_id
        ).order_by(
            BusinessSubtask.sort_order.asc(),
            BusinessSubtask.id.asc(),
        ).all()

    @staticmethod
    def next_sort_order(session, task_id):
        rows = SubtaskRepository.list_by_task(session, task_id)
        return (max((r.sort_order for r in rows), default=-1)) + 1

    @staticmethod
    def update_title(session, subtask, title):
        subtask.title = title
        session.flush()
        return subtask

    @staticmethod
    def update_assignee(session, subtask, assignee_id):
        subtask.assignee_id = assignee_id
        session.flush()
        return subtask

    @staticmethod
    def update_guid(session, subtask, lark_guid):
        subtask.lark_subtask_guid = lark_guid
        session.flush()
        return subtask

    @staticmethod
    def set_status(session, subtask, status, completed_at=None):
        subtask.status = status
        subtask.completed_at = completed_at
        session.flush()
        return subtask

    @staticmethod
    def delete(session, subtask):
        session.delete(subtask)
        session.flush()
