# -*- coding:utf-8 -*-
"""
CRM 品牌别名池 API

提供别名池的增删改查接口
"""

import functools

from flask import jsonify, request, session

from app.api import api_bp
from app.services.pp_alias_service import pp_alias_service


def _get_operator():
    """获取当前登录用户"""
    return session.get('username', 'unknown')


def _api_response(default_error_msg='操作失败', empty_data=None):
    """
    统一 API 响应装饰器

    统一处理异常：
    - ValueError  → 400
    - Exception   → 500

    函数内部直接返回 dict，装饰器自动 jsonify
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return jsonify(result)
            except ValueError as e:
                return jsonify({
                    'code': 400,
                    'msg': str(e),
                    'data': None
                })
            except Exception as e:
                return jsonify({
                    'code': 500,
                    'msg': f'{default_error_msg}: {str(e)}',
                    'data': empty_data
                })
        return wrapper
    return decorator


# ============ 新接口（别名池模式） ============

@api_bp.route('/pp-alias/pool/list', methods=['GET'])
@_api_response(default_error_msg='查询失败', empty_data=[])
def list_pools():
    """分页查询别名池列表（支持按 name 模糊搜索）"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('limit', 10, type=int)
    name = request.args.get('name', '', type=str).strip() or None

    data = pp_alias_service.get_paged_pools(
        page=page,
        page_size=page_size,
        name_keyword=name
    )

    return {
        'code': 200,
        'msg': 'success',
        'data': data['data_list'],
        'count': data['total']
    }


@api_bp.route('/pp-alias/pool/create', methods=['POST'])
@_api_response(default_error_msg='创建失败', empty_data=None)
def create_pool():
    """创建别名池（names 至少 2 个名称）"""
    data = request.get_json() or {}
    names = data.get('names', [])

    if not isinstance(names, list):
        names = [names]

    result = pp_alias_service.create_pool(
        names, operator=_get_operator()
    )
    return {
        'code': 200,
        'msg': '创建成功',
        'data': result
    }


@api_bp.route('/pp-alias/pool/update', methods=['POST'])
@_api_response(default_error_msg='更新失败', empty_data=None)
def update_pool():
    """更新别名池成员（全量替换）"""
    data = request.get_json() or {}
    pool_id = data.get('pool_id')
    names = data.get('names', [])

    if not pool_id:
        raise ValueError('池编号不能为空')

    if not isinstance(names, list):
        names = [names]

    result = pp_alias_service.update_pool(
        pool_id, names, operator=_get_operator()
    )
    return {
        'code': 200,
        'msg': '更新成功',
        'data': result
    }


@api_bp.route('/pp-alias/pool/delete', methods=['POST'])
@_api_response(default_error_msg='删除失败', empty_data=None)
def delete_pool():
    """删除别名池"""
    data = request.get_json() or {}
    pool_id = data.get('pool_id')

    if not pool_id:
        raise ValueError('池编号不能为空')

    result = pp_alias_service.delete_pool(pool_id, operator=_get_operator())
    if result:
        return {'code': 200, 'msg': '删除成功', 'data': None}
    return {'code': 404, 'msg': '记录不存在', 'data': None}


# ============ 兼容旧接口（参数不变，内部走别名池逻辑） ============

@api_bp.route('/pp-alias/list', methods=['GET'])
@_api_response(default_error_msg='查询失败', empty_data=[])
def list_aliases():
    """【兼容】分页查询别名列表"""
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

    data_list = []
    for item in data['data_list']:
        data_list.append({
            'pp_name': item.get('names', [''])[0] if item.get('names') else '',
            'alias_text': item.get('name_text', ''),
            'items': item.get('items', []),
            'pool_id': item.get('pool_id')
        })

    return {
        'code': 200,
        'msg': 'success',
        'data': data_list,
        'count': data['total']
    }


@api_bp.route('/pp-alias/create', methods=['POST'])
@_api_response(default_error_msg='创建失败', empty_data=None)
def create_alias():
    """【兼容】创建别名映射"""
    data = request.get_json() or {}
    pp_name = data.get('pp_name', '').strip()
    alias_names = data.get('alias_names', [])

    if not alias_names and data.get('alias_name'):
        alias_names = [data.get('alias_name', '').strip()]

    if not isinstance(alias_names, list):
        alias_names = [alias_names]

    results = pp_alias_service.create_aliases_batch(
        pp_name, alias_names, operator=_get_operator()
    )
    return {
        'code': 200,
        'msg': '创建成功',
        'data': results
    }


@api_bp.route('/pp-alias/update', methods=['POST'])
@_api_response(default_error_msg='更新失败', empty_data=None)
def update_alias():
    """【兼容】按品牌主名批量更新别名映射"""
    data = request.get_json() or {}
    old_pp_name = data.get('old_pp_name', '').strip()
    pp_name = data.get('pp_name', '').strip()
    aliases = data.get('aliases', [])

    if not old_pp_name:
        raise ValueError('原品牌主名不能为空')

    if not pp_name:
        raise ValueError('品牌主名不能为空')

    result = pp_alias_service.update_alias_group(
        old_pp_name, pp_name, aliases, operator=_get_operator()
    )
    return {
        'code': 200,
        'msg': '更新成功',
        'data': result
    }


@api_bp.route('/pp-alias/delete', methods=['POST'])
@_api_response(default_error_msg='删除失败', empty_data=None)
def delete_alias():
    """【兼容】删除别名映射（按品牌主名）"""
    data = request.get_json() or {}
    pp_name = data.get('pp_name', '').strip()

    if not pp_name:
        raise ValueError('品牌主名不能为空')

    result = pp_alias_service.delete_alias_group(pp_name, operator=_get_operator())
    if result:
        return {'code': 200, 'msg': '删除成功', 'data': None}
    return {'code': 404, 'msg': '记录不存在', 'data': None}
