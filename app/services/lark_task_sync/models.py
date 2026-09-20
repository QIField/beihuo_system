# -*- coding:utf-8 -*-
"""
飞书任务同步 - 数据库操作封装
"""

from app.models.orm_models import (
    BusinessTask,
    UserLarkMapping,
    LarkTaskMapping,
    LarkEventLog,
)


class LarkTaskSyncModels:

    @staticmethod
    def get_task_by_id(session, task_id):
        return session.query(BusinessTask).filter(BusinessTask.id == task_id).first()

    @staticmethod
    def update_task_status(session, task_id, status):
        task = session.query(BusinessTask).filter(BusinessTask.id == task_id).first()
        if task:
            task.status = status
            session.flush()
        return task

    @staticmethod
    def get_mapping_by_business_id(session, business_id, business_type='business_task'):
        return session.query(LarkTaskMapping).filter(
            LarkTaskMapping.business_id == business_id,
            LarkTaskMapping.business_type == business_type,
            LarkTaskMapping.status == 1,
        ).first()

    @staticmethod
    def get_mapping_by_lark_guid(session, lark_task_guid):
        return session.query(LarkTaskMapping).filter(
            LarkTaskMapping.lark_task_guid == lark_task_guid,
            LarkTaskMapping.status == 1,
        ).first()

    @staticmethod
    def get_pending_mappings(session, business_type='business_task'):
        """获取所有未完成的业务任务映射（用于主动同步飞书状态）。"""
        return session.query(LarkTaskMapping).join(
            BusinessTask,
            LarkTaskMapping.business_id == BusinessTask.id,
        ).filter(
            LarkTaskMapping.business_type == business_type,
            LarkTaskMapping.status == 1,
            BusinessTask.status == 0,
        ).all()

    @staticmethod
    def create_mapping(session, business_id, business_type, lark_task_guid, lark_summary, owner_open_id):
        mapping = LarkTaskMapping(
            business_id=business_id,
            business_type=business_type,
            lark_task_guid=lark_task_guid,
            lark_summary=lark_summary,
            owner_open_id=owner_open_id,
        )
        session.add(mapping)
        session.flush()
        return mapping

    @staticmethod
    def get_user_lark_mapping(session, user_id):
        return session.query(UserLarkMapping).filter(
            UserLarkMapping.user_id == user_id,
            UserLarkMapping.status == 1,
        ).first()

    @staticmethod
    def is_event_handled(session, event_id):
        return session.query(LarkEventLog).filter(LarkEventLog.event_id == event_id).first() is not None

    @staticmethod
    def mark_event_handled(session, event_id, event_type, event_time):
        log = LarkEventLog(
            event_id=event_id,
            event_type=event_type,
            event_time=event_time,
        )
        session.add(log)
        session.flush()
        return log
