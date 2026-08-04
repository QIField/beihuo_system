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
    分页查询别名列表（按品牌主名分组聚合）

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
    创建别名映射（支持为同一主名批量创建多个别名）

    请求参数:
        pp_name: 品牌主名
        alias_names: 别名列表（如 ["别名1", "别名2"]）
    """
    try:
        data = request.get_json() or {}
        pp_name = data.get('pp_name', '').strip()
        alias_names = data.get('alias_names', [])

        # 兼容旧版单个别名
        if not alias_names and data.get('alias_name'):
            alias_names = [data.get('alias_name', '').strip()]

        if not isinstance(alias_names, list):
            alias_names = [alias_names]

        results = pp_alias_service.create_aliases_batch(
            pp_name, alias_names, operator=_get_operator()
        )
        return jsonify({
            'code': 200,
            'msg': '创建成功',
            'data': results
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
    按品牌主名批量更新别名映射（增删改）

    请求参数:
        old_pp_name: 原来的品牌主名
        pp_name: 新的品牌主名
        aliases: 别名列表，每项包含 id 和 alias_name（id 为空表示新增）
    """
    try:
        data = request.get_json() or {}
        old_pp_name = data.get('old_pp_name', '').strip()
        pp_name = data.get('pp_name', '').strip()
        aliases = data.get('aliases', [])

        if not old_pp_name:
            return jsonify({
                'code': 400,
                'msg': '原品牌主名不能为空',
                'data': None
            })

        if not pp_name:
            return jsonify({
                'code': 400,
                'msg': '品牌主名不能为空',
                'data': None
            })

        result = pp_alias_service.update_alias_group(
            old_pp_name, pp_name, aliases, operator=_get_operator()
        )
        return jsonify({
            'code': 200,
            'msg': '更新成功',
            'data': result
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

    按品牌主名删除该主名对应的所有别名（分组删除）
    """
    try:
        data = request.get_json() or {}
        pp_name = data.get('pp_name', '').strip()

        if not pp_name:
            return jsonify({
                'code': 400,
                'msg': '品牌主名不能为空',
                'data': None
            })

        result = pp_alias_service.delete_alias_group(pp_name, operator=_get_operator())
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
