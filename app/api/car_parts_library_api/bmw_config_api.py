# -*- coding:utf-8 -*-
# @Time    : 2026/6/16
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : bmw_config_api.py
# @Software: PyCharm

"""
华晨宝马（BMW Brilliance）零件库配置API接口
负责处理宝马大库配置的 HTTP 请求
"""

from flask import Blueprint, request, jsonify

from app.services.car_parts_library_service.bmw_config_service import set_bmw_config, get_bmw_config


# 创建宝马大库配置蓝图，与 bmw_parts_bp 共享 /bmw 前缀
bmw_config_bp = Blueprint('bmw_config', __name__, url_prefix='/bmw')


@bmw_config_bp.route('/set-config', methods=['POST'])
def set_bmw_config_api():
    """
    设置宝马大库配置 API

    请求体 (JSON):
        {
            "cookie": "BMW Brilliance 登录态 Cookie"
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

        cookie = data.get('cookie')

        if not cookie or not str(cookie).strip():
            return jsonify({
                'code': 400,
                'msg': 'cookie 不能为空',
                'data': None
            })

        result = set_bmw_config(cookie=cookie)

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


@bmw_config_bp.route('/get-config', methods=['GET'])
def get_bmw_config_api():
    """
    获取宝马大库配置 API

    返回:
        {
            "code": 200,
            "msg": "查询成功",
            "data": {
                "cookie": "BMW Brilliance 登录态 Cookie"
            }
        }
    """
    try:
        config = get_bmw_config()

        if config:
            return jsonify({
                'code': 200,
                'msg': '查询成功',
                'data': config
            })
        else:
            return jsonify({
                'code': 200,
                'msg': '配置不存在，返回默认值',
                'data': {'cookie': ''}
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询配置失败: {str(e)}',
            'data': None
        })
