# -*- coding:utf-8 -*-
"""
业务任务管理 API
"""

from flask import Blueprint, request, jsonify

from app.core.permission.decorators import require_authentication
from app.core.permission.permission_checker import PermissionCheckerRegistry
from app.services.business_task_service import TaskService
from app.services.business_task_service.task_service import TaskServiceError

business_task_bp = Blueprint('business_task', __name__, url_prefix='/business-tasks')


def _get_current_user_id():
    return PermissionCheckerRegistry.get_user_id()


def _success(data=None, msg='success'):
    return jsonify({'code': 200, 'msg': msg, 'data': data})


def _error(msg, code=500):
    return jsonify({'code': code, 'msg': msg, 'data': None}), code


def _parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@business_task_bp.route('/list', methods=['GET'])
@require_authentication()
def list_tasks():
    try:
        keyword = (request.args.get('keyword') or '').strip()
        status = request.args.get('status')
        status_int = _parse_int(status, None)
        page = _parse_int(request.args.get('page'), 1)
        page_size = _parse_int(request.args.get('page_size'), 10)

        data = TaskService.list_tasks(
            keyword=keyword or None,
            status=status_int,
            page=page,
            page_size=page_size,
        )
        return _success(data)
    except Exception as e:
        return _error(f'获取任务列表失败: {e}')


@business_task_bp.route('/create', methods=['POST'])
@require_authentication()
def create_task():
    try:
        payload = request.get_json(silent=True) or {}
        data = TaskService.create_task(
            title=payload.get('title'),
            content=payload.get('content'),
            assignee_id=payload.get('assignee_id'),
            deadline=payload.get('deadline'),
            created_by=_get_current_user_id(),
        )
        return _success(data, '创建成功')
    except TaskServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'创建任务失败: {e}')


@business_task_bp.route('/batch-create', methods=['POST'])
@require_authentication()
def batch_create_tasks():
    try:
        payload = request.get_json(silent=True) or {}
        tasks = payload.get('tasks')
        data = TaskService.batch_create(tasks, created_by=_get_current_user_id())
        return _success(data, '批量创建成功')
    except TaskServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'批量创建任务失败: {e}')


@business_task_bp.route('/detail', methods=['GET'])
@require_authentication()
def task_detail():
    try:
        task_id = _parse_int(request.args.get('id'), None)
        if not task_id:
            return _error('任务ID不能为空', 400)
        data = TaskService.get_detail(task_id)
        return _success(data)
    except TaskServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'获取任务详情失败: {e}')


@business_task_bp.route('/update', methods=['POST'])
@require_authentication()
def update_task():
    try:
        payload = request.get_json(silent=True) or {}
        task_id = payload.get('id')
        if not task_id:
            return _error('任务ID不能为空', 400)
        data = TaskService.update_task(task_id, payload)
        return _success(data, '更新成功')
    except TaskServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'更新任务失败: {e}')


@business_task_bp.route('/update-status', methods=['POST'])
@require_authentication()
def update_task_status():
    try:
        payload = request.get_json(silent=True) or {}
        task_id = payload.get('id')
        status = _parse_int(payload.get('status'), None)
        if not task_id or status is None:
            return _error('任务ID和状态不能为空', 400)
        data = TaskService.update_status(task_id, status)
        return _success(data, '状态更新成功')
    except TaskServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'更新任务状态失败: {e}')


@business_task_bp.route('/statistics', methods=['GET'])
@require_authentication()
def task_statistics():
    try:
        data = TaskService.get_statistics()
        return _success(data)
    except Exception as e:
        return _error(f'获取统计失败: {e}')
