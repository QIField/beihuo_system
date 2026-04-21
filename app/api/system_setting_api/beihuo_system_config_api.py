# -*- coding:utf-8 -*-
# @Time    : 2026/4/18 18:36
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : beihuo_system_config_api.py
# @Software: PyCharm
from flask import jsonify, request

from . import system_setting_bp
from ...services.system_setting_service import beihuo_system_config_service


@system_setting_bp.route('/get_paged_configs_api', methods=['GET'])
def get_paged_configs_api():
    try:
        page=request.args.get('page')
        page_size = request.args.get('limit', 10)  # Layui 默认参数名是 limit
        data=beihuo_system_config_service.get_paged_configs(page, page_size)
        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': data
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取配置列表失败: {str(e)}',
            'data': None
        })


@system_setting_bp.route('/create_config_api', methods=['POST'])
def create_config_api():
    """
    创建新配置 API
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        required_fields = ['config_key', 'label']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'code': 400,
                    'msg': f'{field} 不能为空',
                    'data': None
                })
        
        config = beihuo_system_config_service.create_config(data)
        return jsonify({
            'code': 200,
            'msg': '创建配置成功',
            'data': config
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'创建配置失败: {str(e)}',
            'data': None
        })


@system_setting_bp.route('/update_config_api', methods=['POST'])
def update_config_api():
    """
    更新配置 API
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        config_id = data.get('id')
        if not config_id:
            return jsonify({
                'code': 400,
                'msg': '配置ID不能为空',
                'data': None
            })
        
        config = beihuo_system_config_service.update_config(config_id, data)
        if config:
            return jsonify({
                'code': 200,
                'msg': '更新配置成功',
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
            'msg': f'更新配置失败: {str(e)}',
            'data': None
        })



