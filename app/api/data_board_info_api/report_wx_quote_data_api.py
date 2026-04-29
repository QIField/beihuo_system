# -*- coding:utf-8 -*-
# @Time    : 2026/4/28 16:33
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : report_wx_quote_data_api.py
# @Software: PyCharm

from flask import jsonify, request

from . import report_wx_quote_data_bp
from app.services.report_wx_quote_data_services import weixin_decoding_result_service
from app.services.report_wx_quote_data_services import quote_summary_service


@report_wx_quote_data_bp.route('/weixin_decoding_result_list_api', methods=['GET'])
def weixin_decoding_result_list_api():
    """
    获取每日报价明细列表 API
    """
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 处理空值，如果日期是空字符串，设置为None
        if start_date == '':
            start_date = None
        if end_date == '':
            end_date = None
            
        # 如果只给了一个日期，默认查询当天
        if start_date and not end_date:
            end_date = start_date
        
        result = weixin_decoding_result_service.fetch_data_paged(
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit
        )
        return jsonify({
            'code': 200,
            'msg': '获取每日报价明细成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取每日报价明细失败: {str(e)}',
            'data': None
        })


@report_wx_quote_data_bp.route('/daily_summary_list_api', methods=['GET'])
def daily_summary_list_api():
    """
    获取每日汇总列表 API
    """
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        date = request.args.get('date')
        
        if not date:
            return jsonify({
                'code': 400,
                'msg': '日期不能为空',
                'data': None
            })
        
        result = quote_summary_service.summarize_oe_codes_daily(
            date_str=date,
            page=page,
            limit=limit
        )
        return jsonify({
            'code': 200,
            'msg': '获取每日汇总成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取每日汇总失败: {str(e)}',
            'data': None
        })


@report_wx_quote_data_bp.route('/monthly_summary_list_api', methods=['GET'])
def monthly_summary_list_api():
    """
    获取每月汇总列表 API
    """
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        month = request.args.get('month')
        
        if not month:
            return jsonify({
                'code': 400,
                'msg': '月份不能为空',
                'data': None
            })
        
        result = quote_summary_service.summarize_oe_codes_monthly(
            month_str=month,
            page=page,
            limit=limit
        )
        return jsonify({
            'code': 200,
            'msg': '获取每月汇总成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取每月汇总失败: {str(e)}',
            'data': None
        })
