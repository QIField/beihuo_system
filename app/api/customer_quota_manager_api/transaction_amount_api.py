# -*- coding:utf-8 -*-
# @Time    : 2026/4/20 20:03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : transaction_amount_api.py
# @Software: PyCharm
from flask import jsonify, request

from . import customer_quota_manager_bp
from ...services.customer_quota_manager_service import transaction_amount_service


@customer_quota_manager_bp.route('/time_transaction_sum_api', methods=['GET'])
def time_transaction_sum_api():
    """
    获取指定时间段客户交易金额汇总 API
    """
    try:


        page = request.args.get('page')
        limit = request.args.get('limit')
        start_month = request.args.get('start_month')
        end_month = request.args.get('end_month')
        customer_name = request.args.get('customer_name')
        level_id = request.args.get('level_id')
        payment_description = request.args.get('payment_description')
        total_price_min = request.args.get('total_price_min')
        total_price_max = request.args.get('total_price_max')


        if not page or not limit:
            return jsonify({
                'code': 400,
                'msg': '页码和条数不能为空',
                'data': None
            })
        
        result = transaction_amount_service.time_transaction_sum(page,limit,start_month, end_month, customer_name,level_id,
                         payment_description, total_price_min, total_price_max)
        return jsonify({
            'code': 200,
            'msg': '获取交易总金额数据成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取交易总金额数据失败: {str(e)}',
            'data': None
        })

