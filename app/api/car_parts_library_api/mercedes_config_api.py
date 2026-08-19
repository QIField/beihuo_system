# -*- coding:utf-8 -*-
# @Time    : 2026/5/20
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : mercedes_config_api.py
# @Software: PyCharm

"""
奔驰大库配置API接口
负责处理奔驰大库配置的HTTP请求
"""

from flask import Blueprint, request, jsonify
from app.core.permission.decorators import require_authentication
from app.services.car_parts_library_service.mercedes_config_service import (
    set_mercedes_config, get_mercedes_config,
    set_benz_column_config, get_benz_column_config
)

mercedes_config_bp = Blueprint('mercedes_config', __name__)


@mercedes_config_bp.route('/set-config', methods=['POST'])
@require_authentication()
def set_mercedes_config_api():
    """
    设置奔驰大库配置 API（不含列配置）

    请求参数:
        {
            "username": "登录用户名",
            "password": "登录密码",
            "customer_id": "客户ID",
            "sales_organization_id": "销售组织ID",
            "tax_rate": 税率（可选，默认 1.13）,
            "discount_rate": 折扣率（可选，默认 0.87）
        }

    返回:
        {
            "code": 200,
            "msg": "设置成功",
            "data": null
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

        username = data.get('username')
        password = data.get('password')
        customer_id = data.get('customer_id')
        sales_organization_id = data.get('sales_organization_id')
        cookie = data.get('cookie')

        tax_rate = data.get('tax_rate', 1.13)
        discount_rate = data.get('discount_rate', 0.83)

        if not username or not password or not customer_id or not sales_organization_id:
            return jsonify({
                'code': 400,
                'msg': 'username、password、customer_id 和 sales_organization_id 不能为空',
                'data': None
            })

        result = set_mercedes_config(
            username=username,
            password=password,
            customer_id=customer_id,
            sales_organization_id=sales_organization_id,
            cookie=cookie,
            tax_rate=tax_rate,
            discount_rate=discount_rate
        )

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


@mercedes_config_bp.route('/get-config', methods=['GET'])
@require_authentication()
def get_mercedes_config_api():
    """
    获取奔驰大库配置 API

    返回:
    {
        "code": 200,
        "msg": "查询成功",
        "data": {
            "username": "登录用户名",
            "password": "登录密码",
            "customer_id": "客户ID",
            "sales_organization_id": "销售组织ID",
            "tax_rate": 税率,
            "discount_rate": 折扣率
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


@mercedes_config_bp.route('/set-column-config', methods=['POST'])
@require_authentication()
def set_benz_column_config_api():
    """
    设置奔驰配件列配置 API

    请求参数:
        {
            "column_config": { "part_number": {"hide": false, "width": 180}, ... },
            "favorite_column_config": { "part_number": {"hide": false, "width": 180}, ... },
            "column_order": ["part_number", "description_cn", ...],
            "favorite_column_order": ["part_number", "description_cn", ...]
        }

    返回:
        {
            "code": 200,
            "msg": "设置成功",
            "data": null
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

        column_config = data.get('column_config')
        favorite_column_config = data.get('favorite_column_config')
        column_order = data.get('column_order')
        favorite_column_order = data.get('favorite_column_order')

        result = set_benz_column_config(
            column_config=column_config,
            favorite_column_config=favorite_column_config,
            column_order=column_order,
            favorite_column_order=favorite_column_order
        )

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
            'msg': f'设置列配置失败: {str(e)}',
            'data': None
        })


@mercedes_config_bp.route('/get-column-config', methods=['GET'])
@require_authentication()
def get_benz_column_config_api():
    """
    获取奔驰配件列配置 API

    返回:
    {
        "code": 200,
        "msg": "查询成功",
        "data": {
            "column_config": { ... },
            "favorite_column_config": { ... },
            "column_order": [ ... ],
            "favorite_column_order": [ ... ]
        }
    }
    """
    try:
        config = get_benz_column_config()

        return jsonify({
            'code': 200,
            'msg': '查询成功',
            'data': config or {}
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询列配置失败: {str(e)}',
            'data': None
        })
