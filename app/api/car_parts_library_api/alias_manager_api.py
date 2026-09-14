# -*- coding:utf-8 -*-
# @Time    : 2026/09/13
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : alias_manager_api.py

"""
别名管理API接口

提供错误 OE 记录分页查看、别名库聚合分页查看两个查询接口。
"""

from flask import Blueprint, request, jsonify

from app.core.permission.decorators import require_authentication
from app.services.car_parts_library_service.alias_manager.oe_collect import page_oe_errors
from app.services.car_parts_library_service.alias_manager.alias_replace import (
    page_alias_list,
    add_alias_record,
    batch_add_alias_records,
    get_aliases_by_part_number,
)

alias_manager_bp = Blueprint('alias_manager', __name__)


@alias_manager_bp.route('/alias-manager/oe-errors', methods=['GET'])
@require_authentication()
def get_oe_errors_api():
    """
    分页获取错误 OE 记录 API（仅状态为 0-未入别名库 的记录）

    请求参数:
    - page: 页码，默认1
    - limit: 每页条数，默认10
    - keyword: 关键字筛选（可选），模糊匹配 OE 编号
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('limit', 10))
        keyword = request.args.get('keyword') or None

        result = page_oe_errors(page, page_size, keyword=keyword)
        if result.get('status'):
            return jsonify({'code': 200, 'msg': result.get('msg'), 'data': result})
        return jsonify({'code': 500, 'msg': result.get('msg'), 'data': None})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'获取错误OE记录失败: {str(e)}', 'data': None})


@alias_manager_bp.route('/alias-manager/alias-list', methods=['GET'])
@require_authentication()
def get_alias_list_api():
    """
    分页获取别名聚合数据 API（先按 part_number 聚合）

    请求参数:
    - page: 页码，默认1
    - limit: 每页条数，默认10
    - keyword: 关键字筛选（可选），模糊匹配配件编号
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('limit', 10))
        keyword = request.args.get('keyword') or None

        result = page_alias_list(page, page_size, keyword=keyword)
        if result.get('status'):
            return jsonify({'code': 200, 'msg': result.get('msg'), 'data': result})
        return jsonify({'code': 500, 'msg': result.get('msg'), 'data': None})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'获取别名列表失败: {str(e)}', 'data': None})


@alias_manager_bp.route('/alias-manager/add-alias', methods=['POST'])
@require_authentication()
def add_alias_api():
    """
    关联奔驰标准OE API

    将错误 OE（part_number_alias）关联到奔驰标准 OE（part_number），
    并同步将 benz_error_oe 中对应的错误 OE 记录标记为已入别名库（status=1）。

    请求参数:
    {
        "part_number": "奔驰标准OE",
        "part_number_alias": "错误OE",
        "remark": "备注（可选）"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求参数不能为空', 'data': None})

        part_number = (data.get('part_number') or '').strip()
        part_number_alias = (data.get('part_number_alias') or '').strip()
        remark = data.get('remark')

        if not part_number or not part_number_alias:
            return jsonify({'code': 400, 'msg': '配件编号和别名不能为空', 'data': None})

        result = add_alias_record(part_number, part_number_alias, remark)
        if result.get('status'):
            return jsonify({'code': 200, 'msg': result.get('msg'), 'data': result})
        return jsonify({'code': 400, 'msg': result.get('msg'), 'data': result})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'添加别名失败: {str(e)}', 'data': None})


@alias_manager_bp.route('/alias-manager/batch-add-alias', methods=['POST'])
@require_authentication()
def batch_add_alias_api():
    """
    批量关联奔驰标准OE API

    请求参数:
    {
        "records": [
            {"part_number": "奔驰标准OE", "part_number_alias": "错误OE", "remark": "备注（可选）"},
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求参数不能为空', 'data': None})

        records = data.get('records')
        if not records or not isinstance(records, list):
            return jsonify({'code': 400, 'msg': 'records 不能为空', 'data': None})

        result = batch_add_alias_records(records)
        if result.get('status'):
            return jsonify({'code': 200, 'msg': result.get('msg'), 'data': result})
        return jsonify({'code': 400, 'msg': result.get('msg'), 'data': result})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'批量添加别名失败: {str(e)}', 'data': None})


@alias_manager_bp.route('/alias-manager/alias-detail', methods=['GET'])
@require_authentication()
def get_alias_detail_api():
    """
    获取指定配件编号下的所有别名记录 API

    请求参数:
    - part_number: 配件编号
    """
    try:
        part_number = (request.args.get('part_number') or '').strip()
        if not part_number:
            return jsonify({'code': 400, 'msg': '配件编号不能为空', 'data': None})

        result = get_aliases_by_part_number(part_number)
        if result.get('status'):
            return jsonify({'code': 200, 'msg': result.get('msg'), 'data': result})
        return jsonify({'code': 500, 'msg': result.get('msg'), 'data': None})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'获取别名详情失败: {str(e)}', 'data': None})
