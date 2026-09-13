# -*- coding:utf-8 -*-
"""
业务任务 - 数据访问层

职责：只负责 business_task 表的查询与写入，不做业务编排。
"""

from sqlalchemy import func, or_

from app.models.orm_models import BusinessTask
from app.utils.orm.session import orm_session


class TaskRepository:

    @staticmethod
    def create(session, title, content, assignee_id, deadline, created_by):
        task = BusinessTask(
            title=title,
            content=content,
            assignee_id=assignee_id,
            deadline=deadline,
            created_by=created_by,
        )
        session.add(task)
        session.flush()
        return task

    @staticmethod
    def get_by_id(session, task_id):
        return session.query(BusinessTask).filter(BusinessTask.id == task_id).first()

    @staticmethod
    def update(session, task, fields):
        allowed = {'title', 'content', 'assignee_id', 'deadline', 'status'}
        for key, value in fields.items():
            if key in allowed and value is not None:
                setattr(task, key, value)
        session.flush()
        return task

    @staticmethod
    def list_tasks(session, keyword=None, status=None, offset=0, limit=10):
        query = session.query(BusinessTask)
        query = TaskRepository._apply_filters(query, keyword, status)
        return query.order_by(BusinessTask.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def count_tasks(session, keyword=None, status=None):
        query = session.query(func.count(BusinessTask.id))
        query = TaskRepository._apply_filters(query, keyword, status)
        return query.scalar() or 0

    @staticmethod
    def _apply_filters(query, keyword, status):
        if status is not None:
            query = query.filter(BusinessTask.status == status)
        if keyword:
            like = f'%{keyword}%'
            query = query.filter(
                or_(
                    BusinessTask.title.ilike(like),
                    BusinessTask.content.ilike(like),
                )
            )
        return query

    @staticmethod
    def get_statistics(session):
        total = session.query(func.count(BusinessTask.id)).scalar() or 0
        pending = session.query(func.count(BusinessTask.id)).filter(
            BusinessTask.status == 0
        ).scalar() or 0
        completed = session.query(func.count(BusinessTask.id)).filter(
            BusinessTask.status == 1
        ).scalar() or 0
        return {
            'total': total,
            'pending': pending,
            'completed': completed,
        }


def task_session():
    """提供独立的 orm_session 上下文（便于 service 层使用）。"""
    return orm_session()
