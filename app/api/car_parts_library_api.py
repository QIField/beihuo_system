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
from app.services.car_parts_library_service.car_parts_library_benz_service import get_part_by_number, get_parts_list_page, data_list_page_refresh, set_mercedes_config, get_mercedes_config

car_parts_library_bp = Blueprint('car_parts_library', __name__, url_prefix='/car-parts')


@car_parts_library_bp.route('/list', methods=['GET'])
def get_parts_list():
    """
    获取配件列表（分页）

    参数:
        page: 页码，默认1
        page_size: 每页条数，默认20
        part_number: 配件编号筛选（可选）

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "status": 操作状态,
                "msg": 提示信息,
                "parts_count": 零件信息条数,
                "stock_count": 库存信息条数
            }
        }
    """
    try:
        # 获取参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        part_number = request.args.get('part_number')

        # 查询数据
        result = get_parts_list_page(
            page=page,
            page_size=page_size,
            part_number=part_number
        )

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@car_parts_library_bp.route('/refresh', methods=['GET'])
def refresh_parts_data():
    """
    刷新配件数据

    参数:
        page: 页码，默认1
        page_size: 每页条数，默认20
        part_number: 配件编号筛选（可选）

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "status": 操作状态,
                "msg": 提示信息,
                "count": 数据条数
            }
        }
    """
    try:
        # 获取参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        part_number = request.args.get('part_number')

        # 查询数据
        result = data_list_page_refresh(
            page=page,
            page_size=page_size,
            part_number=part_number
        )

        if result and result.get('status'):
            return jsonify({
                'code': 200,
                'msg': '刷新成功',
                'data': result
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '刷新失败'),
                'data': None
            })

        
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'刷新失败: {str(e)}',
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
        
        part = get_part_by_number(part_number)
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


@car_parts_library_bp.route('/set-config', methods=['POST'])
def set_mercedes_config_api():
    """
    设置奔驰大库配置 API

    请求参数:
        {
            "cookie": "Cookie 字符串",
            "customer_id": "客户ID",
            "sales_organization_id": "销售组织ID"
        }

    返回:
        {
            "code": 200,
            "msg": "设置成功",
            "data": None
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        cookie = data.get('cookie')
        customer_id = data.get('customer_id')
        sales_organization_id = data.get('sales_organization_id')
        
        if not cookie or not customer_id or not sales_organization_id:
            return jsonify({
                'code': 400,
                'msg': 'Cookie、customer_id 和 sales_organization_id 不能为空',
                'data': None
            })
        
        result = set_mercedes_config(cookie, customer_id, sales_organization_id)
        
        if result.get('code') == 200:
            return jsonify({
                'code': 200,
                'msg': result.get('message', '设置成功'),
                'data': None
            })
        else:
            return jsonify({
                'code': 500,
                'msg': result.get('message', '设置失败'),
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'设置配置失败: {str(e)}',
            'data': None
        })


@car_parts_library_bp.route('/get-config', methods=['GET'])
def get_mercedes_config_api():
    """
    获取奔驰大库配置 API

    返回:
        {
            "code": 200,
            "msg": "查询成功",
            "data": {
                "cookie": "Cookie 字符串",
                "customer_id": "客户ID",
                "sales_organization_id": "销售组织ID"
            }
        }
    """
    try:
        config = get_mercedes_config()
        
        if config:
            return jsonify({
                'code': 200,
                'msg': '查询成功',
                'data': config
            })
        else:
            return jsonify({
                'code': 404,
                'msg': '配置不存在',
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询配置失败: {str(e)}',
            'data': None
        })