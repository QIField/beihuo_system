# -*- coding:utf-8 -*-
# @Time    : 2026/4/23 15:19
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : expected_unpaid_customers_api.py
# @Software: PyCharm

from flask import jsonify, request

from . import customer_quota_manager_bp
from app.services.customer_quota_manager_service import expected_unpaid_customers_services


@customer_quota_manager_bp.route('/get_overdue_unpaid_customers_api', methods=['GET'])
def get_overdue_unpaid_customers_api():
    """
    查询：到期日过了且没有给够钱的客户 API
    """
    try:
        page = request.args.get('page', 1)
        limit = request.args.get('limit', 20)
        customer_name = request.args.get('customer_name')
        level_name = request.args.get('level_name')
        payment_description = request.args.get('payment_description')
        
        result = expected_unpaid_customers_services.get_overdue_unpaid_customers(page, limit, customer_name, level_name, payment_description)
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
