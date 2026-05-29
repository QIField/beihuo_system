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
from app.services.car_parts_library_service.car_parts_library_benz_service import set_mercedes_config, get_mercedes_config

mercedes_config_bp = Blueprint('mercedes_config', __name__)


@mercedes_config_bp.route('/set-config', methods=['POST'])
def set_mercedes_config_api():
    """
    设置奔驰大库配置 API

    请求参数:
        {
            "cookie": "Cookie 字符串",
            "customer_id": "客户ID",
            "sales_organization_id": "销售组织ID",
            "tax_rate": 税率（可选，默认 1.13）,
            "discount_rate": 折扣率（可选，默认 0.87）
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
        
        # 税率和折扣率是可选的，使用默认值
        tax_rate = data.get('tax_rate', 1.13)
        discount_rate = data.get('discount_rate', 0.83)
        
        if not cookie or not customer_id or not sales_organization_id:
            return jsonify({
                'code': 400,
                'msg': 'Cookie、customer_id 和 sales_organization_id 不能为空',
                'data': None
            })
        
        result = set_mercedes_config(cookie, customer_id, sales_organization_id, tax_rate, discount_rate)
        
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
