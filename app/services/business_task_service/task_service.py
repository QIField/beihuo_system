# -*- coding:utf-8 -*-
"""
业务任务 - 业务编排层

职责：参数校验、业务状态流转、调用 repository 持久化、触发飞书同步。
"""

from datetime import datetime

from app.models.orm_models import LarkTaskMapping, UserLarkMapping
from app.models.orm_models.system_models import CrmappUsers
from app.services.lark_task_sync.sync_service import submit_create_lark_task
from app.services.lark_task_sync.models import LarkTaskSyncModels
from app.utils.orm.session import orm_session

from .repository import TaskRepository
from .subtask_service import SubtaskService


STATUS_PENDING = 0
STATUS_COMPLETED = 1
ALLOWED_STATUSES = {STATUS_PENDING, STATUS_COMPLETED}


class TaskServiceError(Exception):
    pass


class TaskService:

    @staticmethod
    def create_task(title, content=None, assignee_id=None, start_time=None, deadline=None,
                    created_by=None, subtasks=None):
        TaskService._validate_create(title, assignee_id)
        start_time_dt = TaskService._parse_start_time(start_time)
        deadline_dt = TaskService._parse_deadline(deadline)
        subtask_items = TaskService._normalize_subtasks(subtasks)

        with orm_session() as session:
            task = TaskRepository.create(
                session=session,
                title=title,
                content=content,
                assignee_id=assignee_id,
                start_time=start_time_dt,
                deadline=deadline_dt,
                created_by=created_by,
            )
            task_id = task.id

        # 带子任务：同步先建飞书父任务再建子任务；不带：保持原异步同步
        if subtask_items:
            SubtaskService.create_many_for_new_task(
                task_id=task_id,
                subtasks=subtask_items,
                default_assignee_id=assignee_id,
                created_by=created_by,
            )
        else:
            TaskService._submit_lark_sync(task_id)
        return TaskService.get_detail(task_id)

    @staticmethod
    def batch_create(tasks, created_by=None):
        if not isinstance(tasks, list) or not tasks:
            raise TaskServiceError('tasks 必须是非空数组')

        created_records = []
        with orm_session() as session:
            for item in tasks:
                TaskService._validate_create(item.get('title'), item.get('assignee_id'))
                start_time_dt = TaskService._parse_start_time(item.get('start_time'))
                deadline_dt = TaskService._parse_deadline(item.get('deadline'))
                task = TaskRepository.create(
                    session=session,
                    title=item['title'],
                    content=item.get('content'),
                    assignee_id=item['assignee_id'],
                    start_time=start_time_dt,
                    deadline=deadline_dt,
                    created_by=created_by,
                )
                created_records.append({
                    'task_id': task.id,
                    'assignee_id': item['assignee_id'],
                    'subtask_items': TaskService._normalize_subtasks(item.get('subtasks')),
                })

        # 每个父任务各自复制一份子任务清单：先父后子
        for record in created_records:
            task_id = record['task_id']
            if record['subtask_items']:
                SubtaskService.create_many_for_new_task(
                    task_id=task_id,
                    subtasks=record['subtask_items'],
                    default_assignee_id=record['assignee_id'],
                    created_by=created_by,
                )
            else:
                TaskService._submit_lark_sync(task_id)

        return [TaskService.get_detail(r['task_id']) for r in created_records]

    @staticmethod
    def update_task(task_id, fields):
        if not task_id:
            raise TaskServiceError('任务ID不能为空')
        update_fields = TaskService._filter_update_fields(fields)

        with orm_session() as session:
            task = TaskRepository.get_by_id(session, task_id)
            if not task:
                raise TaskServiceError('任务不存在')
            TaskRepository.update(session, task, update_fields)

        return TaskService.get_detail(task_id)

    @staticmethod
    def update_status(task_id, status):
        if status not in ALLOWED_STATUSES:
            raise TaskServiceError('状态值不合法')
        return TaskService.update_task(task_id, {'status': status})

    @staticmethod
    def list_tasks(keyword=None, status=None, page=1, page_size=10):
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        offset = (page - 1) * page_size

        with orm_session() as session:
            tasks = TaskRepository.list_tasks(session, keyword, status, offset, page_size)
            total = TaskRepository.count_tasks(session, keyword, status)
            task_list = [TaskService._format_task(task) for task in tasks]

        TaskService._attach_sync_status(task_list)
        TaskService._attach_assignee_names(task_list)

        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'list': task_list,
        }

    @staticmethod
    def get_detail(task_id):
        with orm_session() as session:
            task = TaskRepository.get_by_id(session, task_id)
            if not task:
                raise TaskServiceError('任务不存在')
            data = TaskService._format_task(task)

            task_list = [data]
            TaskService._attach_sync_status(task_list)
            TaskService._attach_assignee_names(task_list)

        data['subtasks'] = SubtaskService.list_for_task(task_id)
        return data

    @staticmethod
    def get_statistics():
        with orm_session() as session:
            stats = TaskRepository.get_statistics(session)
            total_users = session.query(CrmappUsers).count()
            bound_users = session.query(UserLarkMapping).filter(
                UserLarkMapping.status == 1
            ).count()
        stats['total_users'] = total_users
        stats['bound_users'] = bound_users
        return stats

    @staticmethod
    def _validate_create(title, assignee_id):
        if not title or not str(title).strip():
            raise TaskServiceError('任务标题不能为空')
        if not assignee_id:
            raise TaskServiceError('负责人ID不能为空')

    @staticmethod
    def _normalize_subtasks(raw):
        """
        清洗前端提交的子任务清单。

        兼容元素格式：字符串标题，或 {"title": "xxx", "assignee_id": 1}。
        去空白、去空项、保持前端填写顺序；未指定负责人时 assignee_id 为 None。
        """
        if not raw:
            return []
        items = []
        for item in raw:
            if isinstance(item, dict):
                title = item.get('title')
                assignee_id = item.get('assignee_id')
            else:
                title = item
                assignee_id = None
            title = (str(title).strip() if title is not None else '')
            if title:
                items.append({'title': title, 'assignee_id': assignee_id})
        return items

    @staticmethod
    def _parse_start_time(start_time):
        if not start_time:
            return datetime.now()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(str(start_time), fmt)
            except ValueError:
                continue
        raise TaskServiceError('开始时间格式不合法')

    @staticmethod
    def _parse_deadline(deadline):
        if not deadline:
            return None
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(str(deadline), fmt)
            except ValueError:
                continue
        raise TaskServiceError('截止时间格式不合法')

    @staticmethod
    def _filter_update_fields(fields):
        allowed = {'title', 'content', 'assignee_id', 'start_time', 'deadline', 'status'}
        result = {}
        for key in allowed:
            if key in fields:
                result[key] = fields[key]
        if 'start_time' in result:
            result['start_time'] = TaskService._parse_start_time(result['start_time'])
        if 'deadline' in result:
            result['deadline'] = TaskService._parse_deadline(result['deadline'])
        if 'status' in result and result['status'] not in ALLOWED_STATUSES:
            raise TaskServiceError('状态值不合法')
        return result

    @staticmethod
    def _format_task(task):
        return task.to_dict()

    @staticmethod
    def _attach_sync_status(task_list):
        if not task_list:
            return
        ids = [t['id'] for t in task_list]
        mappings = TaskService._get_mappings_by_ids(ids)
        for task in task_list:
            mapping = mappings.get(task['id'])
            if mapping:
                task['lark_sync_status'] = 'synced'
                task['lark_task_guid'] = mapping['lark_task_guid']
            else:
                task['lark_sync_status'] = TaskService._judge_not_sync_reason(task['assignee_id'])
                task['lark_task_guid'] = None

    @staticmethod
    def _attach_assignee_names(task_list):
        if not task_list:
            return
        assignee_ids = list({t['assignee_id'] for t in task_list if t.get('assignee_id')})
        if not assignee_ids:
            return
        with orm_session() as session:
            users = session.query(CrmappUsers).filter(CrmappUsers.id.in_(assignee_ids)).all()
            user_map = {u.id: u.username for u in users}
        for task in task_list:
            task['assignee_name'] = user_map.get(task.get('assignee_id'), '')

    @staticmethod
    def _get_mappings_by_ids(business_ids):
        if not business_ids:
            return {}
        with orm_session() as session:
            mappings = session.query(LarkTaskMapping).filter(
                LarkTaskMapping.business_id.in_(business_ids),
                LarkTaskMapping.status == 1,
            ).all()
            return {m.business_id: m.to_dict() for m in mappings}

    @staticmethod
    def _judge_not_sync_reason(assignee_id):
        with orm_session() as session:
            bound = LarkTaskSyncModels.get_user_lark_mapping(session, assignee_id)
        return 'not_synced' if bound else 'no_binding'

    @staticmethod
    def _submit_lark_sync(task_id):
        from app.utils.logger_config import get_task_logger
        sync_logger = get_task_logger('lark_task_sync')
        sync_logger.info(f"[业务任务] 触发飞书同步, task_id={task_id}")
        try:
            submit_create_lark_task(task_id)
        except Exception:
            sync_logger.exception(f"[业务任务] 触发飞书同步失败, task_id={task_id}")
