# -*- coding:utf-8 -*-
"""
个人记事本 API
"""

from flask import Blueprint, request, jsonify, session

from app.core.permission.decorators import require_authentication
from app.core.permission.permission_checker import PermissionCheckerRegistry
from app.services.notepad_service.notepad_service import (
    NotepadService,
    NotepadServiceError,
)

notepad_api_bp = Blueprint('notepad_api', __name__, url_prefix='/notepad')


def _success(data=None, msg='success'):
    return jsonify({'code': 200, 'msg': msg, 'data': data})


def _error(msg, code=500):
    return jsonify({'code': code, 'msg': msg, 'data': None}), code


@notepad_api_bp.route('/list', methods=['GET'])
@require_authentication()
def list_notes():
    try:
        user_id = PermissionCheckerRegistry.get_user_id()
        data = NotepadService.list_notes(user_id, keyword=request.args.get('keyword'))
        return _success(data)
    except Exception as e:
        return _error(f'获取笔记列表失败: {e}')


@notepad_api_bp.route('/create', methods=['POST'])
@require_authentication()
def create_note():
    try:
        payload = request.get_json(silent=True) or {}
        data = NotepadService.create_note(
            user_id=PermissionCheckerRegistry.get_user_id(),
            username=session.get('username'),
            title=payload.get('title'),
            content=payload.get('content'),
        )
        return _success(data, '保存成功')
    except NotepadServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'新增笔记失败: {e}')


@notepad_api_bp.route('/update', methods=['POST'])
@require_authentication()
def update_note():
    try:
        payload = request.get_json(silent=True) or {}
        note_id = payload.get('id')
        if not note_id:
            return _error('笔记ID不能为空', 400)
        data = NotepadService.update_note(
            user_id=PermissionCheckerRegistry.get_user_id(),
            note_id=note_id,
            title=payload.get('title'),
            content=payload.get('content'),
        )
        return _success(data, '更新成功')
    except NotepadServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'更新笔记失败: {e}')


@notepad_api_bp.route('/delete', methods=['POST'])
@require_authentication()
def delete_note():
    try:
        payload = request.get_json(silent=True) or {}
        note_id = payload.get('id')
        if not note_id:
            return _error('笔记ID不能为空', 400)
        NotepadService.delete_note(
            user_id=PermissionCheckerRegistry.get_user_id(),
            note_id=note_id,
        )
        return _success(True, '删除成功')
    except NotepadServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'删除笔记失败: {e}')
