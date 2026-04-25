# -*- coding:utf-8 -*-
# @Time    : 2026/4/23 11:54
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : account_receivable_list_api.py
# @Software: PyCharm

from flask import jsonify, request

from . import customer_quota_manager_bp
from app.services.customer_quota_manager_service import account_receivable_list_service



@customer_quota_manager_bp.route('/account_receivable_list_api', methods=['GET'])
def account_receivable_list_api():
    """
    获取应收单列表 API
    """
    try:
        page = request.args.get('page')
        limit = request.args.get('limit')
        receipt_no = request.args.get('receipt_no')
        customer_name = request.args.get('customer_name')
        
        if not page or not limit:
            return jsonify({
                'code': 400,
                'msg': '页码和条数不能为空',
                'data': None
            })
        
        result = account_receivable_list_service.get_account_receivable_list(
            page, limit, receipt_no, customer_name
        )
        return jsonify({
            'code': 200,
            'msg': '获取应收单列表成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取应收单列表失败: {str(e)}',
            'data': None
        })




@customer_quota_manager_bp.route('/get_unpaid_customers_api', methods=['GET'])
def get_unpaid_customers_api():
    """
    查询一：没有给够钱的客户 API
    """
    try:
        page = request.args.get('page', 1)
        limit = request.args.get('limit', 20)
        customer_name = request.args.get('customer_name')
        level_name = request.args.get('level_name')
        payment_description = request.args.get('payment_description')
        
        result = account_receivable_list_service.get_unpaid_customers(page, limit, customer_name, level_name, payment_description)
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



