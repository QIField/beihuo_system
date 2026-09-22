# -*- coding:utf-8 -*-
"""
TaskService 单元测试

目标：验证核心业务逻辑，不依赖数据库、网络和飞书同步。
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.services.business_task_service import task_service


class FakeSession:
    pass


class FakeTask:
    def __init__(self, task_id, assignee_id=100, status=0):
        self.id = task_id
        self.assignee_id = assignee_id
        self.status = status
        self.title = '测试任务'
        self.content = '测试内容'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'assignee_id': self.assignee_id,
            'status': self.status,
        }


class FakeOrmSession:
    def __enter__(self):
        return FakeSession()

    def __exit__(self, *args):
        return False


class FakeTaskRepository:
    tasks = {}
    last_create_kwargs = None
    last_update_kwargs = None

    @classmethod
    def reset(cls):
        cls.tasks = {}
        cls.last_create_kwargs = None
        cls.last_update_kwargs = None

    @classmethod
    def create(cls, **kwargs):
        cls.last_create_kwargs = kwargs
        task_id = max(cls.tasks.keys(), default=0) + 1
        task = FakeTask(task_id, assignee_id=kwargs.get('assignee_id'))
        cls.tasks[task_id] = task
        return task

    @classmethod
    def get_by_id(cls, session, task_id):
        return cls.tasks.get(task_id)

    @classmethod
    def update(cls, session, task, fields):
        cls.last_update_kwargs = fields
        for key, value in fields.items():
            setattr(task, key, value)
        return task

    @classmethod
    def list_tasks(cls, session, keyword, status, offset, limit):
        return list(cls.tasks.values())[:limit]

    @classmethod
    def count_tasks(cls, session, keyword, status):
        return len(cls.tasks)

    @classmethod
    def get_statistics(cls, session):
        return {'total': 10, 'pending': 4, 'completed': 6}


class FakeSubtaskService:
    create_calls = []

    @classmethod
    def reset(cls):
        cls.create_calls = []

    @classmethod
    def create_many_for_new_task(cls, task_id, titles, assignee_id, created_by=None):
        cls.create_calls.append({
            'task_id': task_id,
            'titles': titles,
            'assignee_id': assignee_id,
            'created_by': created_by,
        })

    @classmethod
    def list_for_task(cls, task_id):
        return []


def _mock_session():
    task_service.orm_session = FakeOrmSession
    FakeSubtaskService.reset()
    task_service.SubtaskService = FakeSubtaskService


def _mock_repository():
    FakeTaskRepository.reset()
    task_service.TaskRepository = FakeTaskRepository()


def _mock_attach():
    task_service.TaskService._attach_sync_status = lambda task_list: None


def _mock_assignee():
    task_service.TaskService._attach_assignee_names = lambda task_list: None


SYNC_CALLS = []


def _mock_sync():
    SYNC_CALLS.clear()

    def _record_sync(task_id):
        SYNC_CALLS.append(task_id)

    task_service.submit_create_lark_task = _record_sync


def test_create_task_success():
    _mock_session()
    _mock_repository()
    _mock_attach()
    _mock_assignee()
    _mock_sync()

    result = task_service.TaskService.create_task(
        title='测试任务',
        content='内容',
        assignee_id=100,
        deadline='2026-09-30',
        created_by=1,
    )
    assert result['id'] == 1
    assert FakeTaskRepository.last_create_kwargs['assignee_id'] == 100
    print('PASS: test_create_task_success')


def test_create_task_missing_title():
    _mock_session()
    _mock_repository()
    _mock_sync()
    try:
        task_service.TaskService.create_task(title='', assignee_id=100)
        assert False, '应抛出异常'
    except task_service.TaskServiceError as e:
        assert '标题' in str(e)
    print('PASS: test_create_task_missing_title')


def test_create_task_missing_assignee():
    _mock_session()
    _mock_repository()
    _mock_sync()
    try:
        task_service.TaskService.create_task(title='测试', assignee_id=None)
        assert False, '应抛出异常'
    except task_service.TaskServiceError as e:
        assert '负责人' in str(e)
    print('PASS: test_create_task_missing_assignee')


def test_update_status_success():
    _mock_session()
    _mock_repository()
    _mock_attach()
    _mock_assignee()
    _mock_sync()

    created = task_service.TaskService.create_task(title='测试', assignee_id=100)
    result = task_service.TaskService.update_status(created['id'], 1)
    assert result['status'] == 1
    print('PASS: test_update_status_success')


def test_update_status_invalid():
    _mock_session()
    _mock_repository()
    try:
        task_service.TaskService.update_status(1, 99)
        assert False, '应抛出异常'
    except task_service.TaskServiceError as e:
        assert '状态' in str(e)
    print('PASS: test_update_status_invalid')


def test_batch_create_success():
    _mock_session()
    _mock_repository()
    _mock_attach()
    _mock_assignee()
    _mock_sync()

    tasks = [
        {'title': '任务1', 'assignee_id': 100},
        {'title': '任务2', 'assignee_id': 101},
    ]
    result = task_service.TaskService.batch_create(tasks, created_by=1)
    assert len(result) == 2
    print('PASS: test_batch_create_success')


def test_list_tasks():
    _mock_session()
    _mock_repository()
    _mock_attach()
    _mock_assignee()
    _mock_sync()

    task_service.TaskService.create_task(title='任务1', assignee_id=100)
    task_service.TaskService.create_task(title='任务2', assignee_id=101)

    result = task_service.TaskService.list_tasks(keyword='测试', status=0, page=1, page_size=5)
    assert result['total'] == 2
    assert result['page'] == 1
    assert result['page_size'] == 5
    assert len(result['list']) == 2
    print('PASS: test_list_tasks')


def test_normalize_subtasks():
    raw = ['子任务1', '', '  ', {'title': '子任务2'}, {'other': 1}, None]
    titles = task_service.TaskService._normalize_subtasks(raw)
    assert titles == ['子任务1', '子任务2'], titles
    assert task_service.TaskService._normalize_subtasks(None) == []
    assert task_service.TaskService._normalize_subtasks([]) == []
    print('PASS: test_normalize_subtasks')


def test_create_task_with_subtasks():
    """带子任务：先建父任务，再走 SubtaskService 建子任务，不走异步同步。"""
    _mock_session()
    _mock_repository()
    _mock_attach()
    _mock_assignee()
    _mock_sync()

    result = task_service.TaskService.create_task(
        title='父任务',
        content='内容',
        assignee_id=100,
        created_by=1,
        subtasks=['子1', {'title': '子2'}, '  '],
    )
    assert result['id'] == 1
    assert len(FakeSubtaskService.create_calls) == 1
    call = FakeSubtaskService.create_calls[0]
    assert call['task_id'] == 1
    assert call['titles'] == ['子1', '子2']
    assert call['assignee_id'] == 100
    assert call['created_by'] == 1
    assert SYNC_CALLS == []
    print('PASS: test_create_task_with_subtasks')


def test_create_task_without_subtasks_uses_async_sync():
    """不带子任务：保持原异步同步父任务的路径。"""
    _mock_session()
    _mock_repository()
    _mock_attach()
    _mock_assignee()
    _mock_sync()

    task_service.TaskService.create_task(title='普通任务', assignee_id=100)
    assert FakeSubtaskService.create_calls == []
    assert SYNC_CALLS == [1]
    print('PASS: test_create_task_without_subtasks_uses_async_sync')


def test_batch_create_with_subtasks():
    """批量发放：每个父任务各复制一份子任务清单。"""
    _mock_session()
    _mock_repository()
    _mock_attach()
    _mock_assignee()
    _mock_sync()

    tasks = [
        {'title': '任务1', 'assignee_id': 100, 'subtasks': ['子A']},
        {'title': '任务2', 'assignee_id': 101, 'subtasks': ['子A']},
    ]
    result = task_service.TaskService.batch_create(tasks, created_by=1)
    assert len(result) == 2
    assert len(FakeSubtaskService.create_calls) == 2
    assert FakeSubtaskService.create_calls[0]['task_id'] == 1
    assert FakeSubtaskService.create_calls[0]['titles'] == ['子A']
    assert FakeSubtaskService.create_calls[1]['task_id'] == 2
    assert FakeSubtaskService.create_calls[1]['assignee_id'] == 101
    assert SYNC_CALLS == []
    print('PASS: test_batch_create_with_subtasks')


if __name__ == '__main__':
    test_create_task_success()
    test_create_task_missing_title()
    test_create_task_missing_assignee()
    test_update_status_success()
    test_update_status_invalid()
    test_batch_create_success()
    test_list_tasks()
    test_normalize_subtasks()
    test_create_task_with_subtasks()
    test_create_task_without_subtasks_uses_async_sync()
    test_batch_create_with_subtasks()
    print('ALL TASK SERVICE TESTS PASSED')
