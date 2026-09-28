# -*- coding:utf-8 -*-
"""
业务子任务清单管理 API
"""

from flask import Blueprint, request, jsonify

from app.core.permission.decorators import require_authentication
from app.core.permission.permission_checker import PermissionCheckerRegistry
from app.services.business_task_service.subtask_service import (
    SubtaskService,
    SubtaskServiceError,
)

business_subtask_bp = Blueprint('business_subtask', __name__, url_prefix='/business-tasks/subtasks')


def _get_current_user_id():
    return PermissionCheckerRegistry.get_user_id()


def _success(data=None, msg='success'):
    return jsonify({'code': 200, 'msg': msg, 'data': data})


def _error(msg, code=500):
    return jsonify({'code': code, 'msg': msg, 'data': None}), code


def _parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@business_subtask_bp.route('/list', methods=['GET'])
@require_authentication()
def list_subtasks():
    try:
        task_id = _parse_int(request.args.get('task_id'), None)
        if not task_id:
            return _error('父任务ID不能为空', 400)
        data = SubtaskService.list_for_task(task_id)
        return _success(data)
    except Exception as e:
        return _error(f'获取子任务列表失败: {e}')


@business_subtask_bp.route('/create', methods=['POST'])
@require_authentication()
def create_subtask():
    try:
        payload = request.get_json(silent=True) or {}
        task_id = _parse_int(payload.get('task_id'), None)
        data = SubtaskService.add(
            task_id=task_id,
            title=payload.get('title'),
            assignee_id=_parse_int(payload.get('assignee_id'), None),
            created_by=_get_current_user_id(),
        )
        return _success(data, '添加成功')
    except SubtaskServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'添加子任务失败: {e}')


@business_subtask_bp.route('/update', methods=['POST'])
@require_authentication()
def update_subtask():
    try:
        payload = request.get_json(silent=True) or {}
        subtask_id = _parse_int(payload.get('id'), None)
        if not subtask_id:
            return _error('子任务ID不能为空', 400)

        if 'title' in payload:
            data = SubtaskService.update_title(subtask_id, payload.get('title'))
        else:
            data = SubtaskService._get_dict(subtask_id)

        if 'assignee_id' in payload:
            data = SubtaskService.update_assignee(
                subtask_id, _parse_int(payload.get('assignee_id'), None)
            )
        return _success(data, '更新成功')
    except SubtaskServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'更新子任务失败: {e}')


@business_subtask_bp.route('/update-status', methods=['POST'])
@require_authentication()
def update_subtask_status():
    try:
        payload = request.get_json(silent=True) or {}
        subtask_id = _parse_int(payload.get('id'), None)
        status = _parse_int(payload.get('status'), None)
        if not subtask_id or status is None:
            return _error('子任务ID和状态不能为空', 400)
        data = SubtaskService.set_status(subtask_id, status)
        return _success(data, '状态更新成功')
    except SubtaskServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'更新子任务状态失败: {e}')


@business_subtask_bp.route('/delete', methods=['POST'])
@require_authentication()
def delete_subtask():
    try:
        payload = request.get_json(silent=True) or {}
        subtask_id = _parse_int(payload.get('id'), None)
        if not subtask_id:
            return _error('子任务ID不能为空', 400)
        SubtaskService.remove(subtask_id)
        return _success(True, '删除成功')
    except SubtaskServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'删除子任务失败: {e}')
