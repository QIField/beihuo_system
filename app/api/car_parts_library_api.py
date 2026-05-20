# -*- coding:utf-8 -*-
# @Time    : 2026/5/20
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : car_parts_library_api.py
# @Software: PyCharm

"""
汽车配件库API接口
负责处理配件库的HTTP请求
"""

from flask import Blueprint, request, jsonify
from app.services.car_parts_library_service.car_parts_library_service import CarPartsLibraryService

car_parts_library_bp = Blueprint('car_parts_library', __name__, url_prefix='/car-parts')


@car_parts_library_bp.route('/list', methods=['GET'])
def get_parts_list():
    """
    获取配件列表（分页）

    参数:
        page: 页码，默认1
        page_size: 每页条数，默认20
        part_number: 配件编号筛选（可选）
        description_cn: 中文描述筛选（可选）

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "list": [...],
                "total": 总条数,
                "page": 当前页,
                "page_size": 每页条数
            }
        }
    """
    try:
        # 获取参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        part_number = request.args.get('part_number')
        description_cn = request.args.get('description_cn')

        # 查询数据
        total, parts = CarPartsLibraryService.get_parts_list(
            page=page,
            page_size=page_size,
            part_number=part_number,
            description_cn=description_cn
        )

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': {
                'list': parts,
                'total': total,
                'page': page,
                'page_size': page_size
            }
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@car_parts_library_bp.route('/detail', methods=['GET'])
def get_part_detail():
    """
    获取配件详情

    参数:
        part_number: 配件编号（查询参数）

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {...}
        }
    """
    try:
        part_number = request.args.get('part_number')
        if not part_number:
            return jsonify({
                'code': 400,
                'msg': '配件编号不能为空',
                'data': None
            })
        
        part = CarPartsLibraryService.get_part_by_number(part_number)
        if part:
            return jsonify({
                'code': 200,
                'msg': 'success',
                'data': part
            })
        else:
            return jsonify({
                'code': 404,
                'msg': '配件不存在',
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })