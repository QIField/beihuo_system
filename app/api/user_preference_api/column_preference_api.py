# -*- coding:utf-8 -*-
# @Project : beihuo_system
# @File    : column_preference_api.py
# @Description: 用户表格列偏好配置 API

from flask import Blueprint, request, jsonify, session

from app.services.user_preference_service import ColumnPreferenceService

bp = Blueprint('user_column_preference', __name__, url_prefix='/column_preference')


def _get_current_user_id():
    """从 session 获取当前登录用户ID"""
    try:
        return session.get('user_id') if 'logged_in' in session else session.get('user_id')
    except Exception:
        return None


@bp.route('', methods=['GET'])
def get_column_preference():
    """
    获取当前用户在指定页面、指定表格上的列状态

    Query Parameters:
        page_key: 页面标识（必填）
        grid_key: 表格标识（必填）

    Returns:
        JSON: {code: 0, data: <columnState 数组 或 null>, message: 'success'}
    """
    try:
        user_id = _get_current_user_id()
        page_key = (request.args.get('page_key') or '').strip()
        grid_key = (request.args.get('grid_key') or '').strip()

        if not user_id:
            return jsonify({'code': 0, 'data': None, 'message': 'no user'})

        if not page_key or not grid_key:
            return jsonify({
                'code': 400,
                'data': None,
                'message': 'page_key 与 grid_key 必填'
            }), 400

        column_state = ColumnPreferenceService.get_preference(user_id, page_key, grid_key)
        return jsonify({
            'code': 0,
            'data': column_state,
            'message': 'success'
        })
    except Exception as e:
        import traceback
        print(f"[ColumnPreferenceAPI] 获取错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'code': 500,
            'data': None,
            'message': f'查询失败: {str(e)}'
        }), 500


@bp.route('', methods=['POST'])
def save_column_preference():
    """
    保存（或更新）当前用户在指定页面、指定表格上的列状态

    Request JSON:
        {
            "page_key": "ks_inquiry_records",
            "grid_key": "detail_grid",
            "column_state": [...]  // AG Grid columnApi.getColumnState() 结果
        }

    Returns:
        JSON: {code: 0, data: null, message: 'success'}
    """
    try:
        user_id = _get_current_user_id()
        if not user_id:
            return jsonify({'code': 0, 'data': None, 'message': 'no user'})

        payload = request.get_json(silent=True) or {}
        page_key = (payload.get('page_key') or '').strip()
        grid_key = (payload.get('grid_key') or '').strip()
        column_state = payload.get('column_state')

        if not page_key or not grid_key:
            return jsonify({
                'code': 400,
                'data': None,
                'message': 'page_key 与 grid_key 必填'
            }), 400

        if column_state is not None and not isinstance(column_state, list):
            return jsonify({
                'code': 400,
                'data': None,
                'message': 'column_state 必须为数组'
            }), 400

        ColumnPreferenceService.save_preference(user_id, page_key, grid_key, column_state)
        return jsonify({'code': 0, 'data': None, 'message': 'success'})
    except Exception as e:
        import traceback
        print(f"[ColumnPreferenceAPI] 保存错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'code': 500,
            'data': None,
            'message': f'保存失败: {str(e)}'
        }), 500


@bp.route('', methods=['DELETE'])
def delete_column_preference():
    """
    删除当前用户在指定页面、指定表格上的列状态（恢复默认）

    Query Parameters:
        page_key: 页面标识（必填）
        grid_key: 表格标识（必填）
    """
    try:
        user_id = _get_current_user_id()
        if not user_id:
            return jsonify({'code': 0, 'data': None, 'message': 'no user'})

        page_key = (request.args.get('page_key') or '').strip()
        grid_key = (request.args.get('grid_key') or '').strip()

        if not page_key or not grid_key:
            return jsonify({
                'code': 400,
                'data': None,
                'message': 'page_key 与 grid_key 必填'
            }), 400

        ColumnPreferenceService.delete_preference(user_id, page_key, grid_key)
        return jsonify({'code': 0, 'data': None, 'message': 'success'})
    except Exception as e:
        import traceback
        print(f"[ColumnPreferenceAPI] 删除错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'code': 500,
            'data': None,
            'message': f'删除失败: {str(e)}'
        }), 500
