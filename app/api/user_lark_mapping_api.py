# -*- coding:utf-8 -*-
"""
用户飞书绑定管理 API
"""

from flask import Blueprint, request, jsonify, session

from app.core.permission.decorators import require_authentication
from app.services.user_lark_mapping_service import UserLarkMappingService
from app.services.user_lark_mapping_service.mapping_service import UserLarkMappingServiceError

user_lark_mapping_bp = Blueprint('user_lark_mapping', __name__, url_prefix='/user-lark-mappings')


def _get_current_store():
    """获取当前登录用户的门店代码，默认佛山。"""
    user_store = session.get('store', 'fsbbr')
    current_org = session.get('current_org', user_store)
    return current_org or user_store or 'fsbbr'


def _success(data=None, msg='success'):
    return jsonify({'code': 200, 'msg': msg, 'data': data})


def _error(msg, code=500):
    return jsonify({'code': code, 'msg': msg, 'data': None}), code


def _parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@user_lark_mapping_bp.route('/list', methods=['GET'])
@require_authentication()
def list_mappings():
    try:
        keyword = (request.args.get('keyword') or '').strip()
        page = _parse_int(request.args.get('page'), 1)
        page_size = _parse_int(request.args.get('page_size'), 10)

        data = UserLarkMappingService.list_mappings(
            keyword=keyword or None,
            page=page,
            page_size=page_size,
            store=_get_current_store(),
        )
        return _success(data)
    except Exception as e:
        return _error(f'获取绑定列表失败: {e}')


@user_lark_mapping_bp.route('/update', methods=['POST'])
@require_authentication()
def update_mapping():
    try:
        payload = request.get_json(silent=True) or {}
        mapping_id = _parse_int(payload.get('id'), None)
        lark_open_id = payload.get('lark_open_id')
        lark_union_id = payload.get('lark_union_id')

        if not mapping_id:
            return _error('绑定ID不能为空', 400)

        data = UserLarkMappingService.update_mapping(mapping_id, lark_open_id, lark_union_id)
        return _success(data, '更新成功')
    except UserLarkMappingServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'更新绑定失败: {e}')


@user_lark_mapping_bp.route('/update-binding-and-contact', methods=['POST'])
@require_authentication()
def update_binding_and_contact():
    """
    同时更新已绑定用户的联系方式和飞书 open_id。
    """
    try:
        payload = request.get_json(silent=True) or {}
        mapping_id = _parse_int(payload.get('id'), None)
        mobile = payload.get('mobile')
        email = payload.get('email')
        lark_open_id = payload.get('lark_open_id')

        if not mapping_id:
            return _error('绑定ID不能为空', 400)

        data = UserLarkMappingService.update_binding_and_contact(
            mapping_id=mapping_id,
            mobile=mobile,
            email=email,
            lark_open_id=lark_open_id,
        )
        return _success(data, '更新成功')
    except UserLarkMappingServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'更新失败: {e}')


@user_lark_mapping_bp.route('/toggle', methods=['POST'])
@require_authentication()
def toggle_mapping():
    try:
        payload = request.get_json(silent=True) or {}
        mapping_id = _parse_int(payload.get('id'), None)
        status = _parse_int(payload.get('status'), None)

        if not mapping_id or status is None:
            return _error('绑定ID和状态不能为空', 400)

        data = UserLarkMappingService.toggle_status(mapping_id, status)
        return _success(data, '状态更新成功')
    except UserLarkMappingServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'更新状态失败: {e}')


@user_lark_mapping_bp.route('/candidates', methods=['GET'])
@require_authentication()
def list_candidates():
    try:
        keyword = (request.args.get('keyword') or '').strip()
        data = UserLarkMappingService.list_candidates(
            keyword=keyword or None,
            store=_get_current_store(),
        )
        return _success(data)
    except Exception as e:
        return _error(f'获取候选用户失败: {e}')


@user_lark_mapping_bp.route('/users', methods=['GET'])
@require_authentication()
def list_all_users():
    try:
        keyword = (request.args.get('keyword') or '').strip()
        data = UserLarkMappingService.list_all_users(
            keyword=keyword or None,
            store=_get_current_store(),
        )
        return _success(data)
    except Exception as e:
        return _error(f'获取用户列表失败: {e}')


@user_lark_mapping_bp.route('/update-contact', methods=['POST'])
@require_authentication()
def update_user_contact():
    try:
        payload = request.get_json(silent=True) or {}
        user_id = _parse_int(payload.get('user_id'), None)
        mobile = payload.get('mobile')
        email = payload.get('email')

        if not user_id:
            return _error('用户ID不能为空', 400)

        data = UserLarkMappingService.update_user_contact(user_id, mobile, email)
        return _success(data, '联系方式更新成功')
    except UserLarkMappingServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'更新联系方式失败: {e}')


@user_lark_mapping_bp.route('/batch-bind-by-contact', methods=['POST'])
@require_authentication()
def batch_bind_by_contact():
    try:
        payload = request.get_json(silent=True) or {}
        user_ids = payload.get('user_ids') or []

        if not isinstance(user_ids, list) or not user_ids:
            return _error('user_ids 必须是非空数组', 400)

        data = UserLarkMappingService.batch_bind_by_contact(user_ids)
        return _success(data, f'成功绑定 {data["success"]} 个用户')
    except UserLarkMappingServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'批量绑定失败: {e}')


@user_lark_mapping_bp.route('/batch-refresh-by-contact', methods=['POST'])
@require_authentication()
def batch_refresh_by_contact():
    """
    批量刷新已绑定用户的飞书 open_id。

    根据用户当前手机号/邮箱重新反查飞书用户 ID，并更新已有绑定记录。
    """
    try:
        payload = request.get_json(silent=True) or {}
        mapping_ids = payload.get('mapping_ids') or []

        if not isinstance(mapping_ids, list) or not mapping_ids:
            return _error('mapping_ids 必须是非空数组', 400)

        data = UserLarkMappingService.batch_refresh_by_contact(mapping_ids)
        return _success(data, f'成功刷新 {data["success"]} 个用户绑定')
    except UserLarkMappingServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        return _error(f'批量刷新失败: {e}')
