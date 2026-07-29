# -*- coding:utf-8 -*-
"""
CRM 零件品牌别名 API

提供别名映射的增删改查接口
"""

from flask import jsonify, request, session

from app.api import api_bp
from app.services.pp_alias_service import pp_alias_service


def _get_operator():
    """
    获取当前登录用户
    """
    return session.get('username', 'unknown')


@api_bp.route('/pp-alias/list', methods=['GET'])
def list_aliases():
    """
    分页查询别名列表

    支持按 pp_name、alias_name 模糊搜索
    """
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('limit', 10, type=int)
        pp_name = request.args.get('pp_name', '', type=str).strip() or None
        alias_name = request.args.get('alias_name', '', type=str).strip() or None

        data = pp_alias_service.get_paged_aliases(
            page=page,
            page_size=page_size,
            pp_name=pp_name,
            alias_name=alias_name
        )

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': data['data_list'],
            'count': data['total']
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': [],
            'count': 0
        })


@api_bp.route('/pp-alias/create', methods=['POST'])
def create_alias():
    """
    创建别名映射
    """
    try:
        data = request.get_json() or {}
        pp_name = data.get('pp_name', '').strip()
        alias_name = data.get('alias_name', '').strip()

        alias = pp_alias_service.create_alias(pp_name, alias_name, operator=_get_operator())
        return jsonify({
            'code': 200,
            'msg': '创建成功',
            'data': alias
        })
    except ValueError as e:
        return jsonify({
            'code': 400,
            'msg': str(e),
            'data': None
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'创建失败: {str(e)}',
            'data': None
        })


@api_bp.route('/pp-alias/update', methods=['POST'])
def update_alias():
    """
    更新别名映射
    """
    try:
        data = request.get_json() or {}
        alias_id = data.get('id')
        pp_name = data.get('pp_name', '').strip()
        alias_name = data.get('alias_name', '').strip()

        if not alias_id:
            return jsonify({
                'code': 400,
                'msg': 'ID 不能为空',
                'data': None
            })

        alias = pp_alias_service.update_alias(alias_id, pp_name, alias_name, operator=_get_operator())
        if alias:
            return jsonify({
                'code': 200,
                'msg': '更新成功',
                'data': alias
            })
        return jsonify({
            'code': 404,
            'msg': '记录不存在',
            'data': None
        })
    except ValueError as e:
        return jsonify({
            'code': 400,
            'msg': str(e),
            'data': None
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'更新失败: {str(e)}',
            'data': None
        })


@api_bp.route('/pp-alias/delete', methods=['POST'])
def delete_alias():
    """
    删除别名映射
    """
    try:
        data = request.get_json() or {}
        alias_id = data.get('id')

        if not alias_id:
            return jsonify({
                'code': 400,
                'msg': 'ID 不能为空',
                'data': None
            })

        result = pp_alias_service.delete_alias(alias_id, operator=_get_operator())
        if result:
            return jsonify({
                'code': 200,
                'msg': '删除成功',
                'data': None
            })
        return jsonify({
            'code': 404,
            'msg': '记录不存在',
            'data': None
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'删除失败: {str(e)}',
            'data': None
        })
