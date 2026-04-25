# -*- coding:utf-8 -*-
# @Time    : 2026/4/24 09:45
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : customer_quota_api.py
# @Software: PyCharm

from flask import jsonify, request

from . import customer_quota_manager_bp
from app.services.customer_quota_manager_service import customer_quota_service


@customer_quota_manager_bp.route('/customer_quota_list_api', methods=['GET'])
def customer_quota_list_api():
    """
    获取客户额度列表 API
    """
    try:
        page = request.args.get('page')
        limit = request.args.get('limit')
        fullname = request.args.get('fullname')
        quota_status = request.args.get('quota_status')
        
        if not page or not limit:
            return jsonify({
                'code': 400,
                'msg': '页码和条数不能为空',
                'data': None
            })
        
        result = customer_quota_service.get_customer_quota_list(
            page, limit, fullname, quota_status
        )
        return jsonify({
            'code': 200,
            'msg': '获取客户额度列表成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取客户额度列表失败: {str(e)}',
            'data': None
        })


@customer_quota_manager_bp.route('/customer_quota_detail_api', methods=['GET'])
def customer_quota_detail_api():
    """
    获取客户额度详情 API
    """
    try:
        id = request.args.get('id')
        
        if not id:
            return jsonify({
                'code': 400,
                'msg': 'ID不能为空',
                'data': None
            })
        
        result = customer_quota_service.get_customer_quota_by_id(id)
        if result:
            return jsonify({
                'code': 200,
                'msg': '获取客户额度详情成功',
                'data': result
            })
        else:
            return jsonify({
                'code': 404,
                'msg': '客户额度不存在',
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取客户额度详情失败: {str(e)}',
            'data': None
        })


@customer_quota_manager_bp.route('/update_customer_quota_api', methods=['POST'])
def update_customer_quota_api():
    """
    更新客户额度 API
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        id = data.get('id')
        if not id:
            return jsonify({
                'code': 400,
                'msg': 'ID不能为空',
                'data': None
            })
        
        result = customer_quota_service.update_customer_quota(id, data)
        if result:
            return jsonify({
                'code': 200,
                'msg': '更新客户额度成功',
                'data': result
            })
        else:
            return jsonify({
                'code': 404,
                'msg': '客户额度不存在',
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'更新客户额度失败: {str(e)}',
            'data': None
        })
