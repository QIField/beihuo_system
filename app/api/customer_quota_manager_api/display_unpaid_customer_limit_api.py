# -*- coding:utf-8 -*-
# @Time    : 2026/4/24 15:48
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : display_unpaid_customer_limit_api.py
# @Software: PyCharm

from flask import jsonify, request

from . import customer_quota_manager_bp
from app.services.customer_quota_manager_service import display_unpaid_customer_limit_service


@customer_quota_manager_bp.route('/get_overdue_unpaid_customers_with_quota_api', methods=['GET'])
def get_overdue_unpaid_customers_with_quota_api():
    """
    查询：到期日过了且没有给够钱的客户，并包含客户授信总额度 API
    """
    try:
        page = request.args.get('page', 1)
        limit = request.args.get('limit', 20)
        customer_name = request.args.get('customer_name')
        level_name = request.args.get('level_name')
        payment_description = request.args.get('payment_description')
        quota_status = request.args.get('quota_status')
        
        result = display_unpaid_customer_limit_service.get_overdue_unpaid_customers_with_quota(
            page, limit, customer_name, level_name, payment_description, quota_status
        )
        return jsonify({
            'code': 200,
            'msg': '查询成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@customer_quota_manager_bp.route('/get_receipts_by_customer_code_api', methods=['GET'])
def get_receipts_by_customer_code_api():
    """
    根据客户编码分页获取应收单列表 API
    """
    try:
        customer_code = request.args.get('customer_code')
        page = request.args.get('page', 1)
        limit = request.args.get('limit', 20)
        payment_status = request.args.get('payment_status')
        
        if not customer_code:
            return jsonify({
                'code': 400,
                'msg': '客户编码不能为空',
                'data': None
            })
        
        result = display_unpaid_customer_limit_service.get_receipts_by_customer_code(
            customer_code, page, limit, payment_status
        )
        return jsonify({
            'code': 200,
            'msg': '查询成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })
