# -*- coding:utf-8 -*-
# @Time    : 2026/4/28 16:33
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : summary_api.py
# @Software: PyCharm

from flask import jsonify, request, session

from app.core.permission.decorators import require_authentication
from app.core.permission.decorators_plus import require_param_permission

from . import report_wx_quote_data_bp
from app.services.report_wx_quote_data_services import quote_summary_service


@report_wx_quote_data_bp.route('/daily_summary_list_api', methods=['GET'])
@require_param_permission(
    param_name='groupname',
    permission_value_map={
        'wx_group': '全部',

        'wx_group:view_group_f3': 'F3查询群',
        'wx_group:view_group_fs_nb': '佛山巴博瑞内部查询群',
        'wx_group:view_group_fs_crm': '佛山报价CRM中台数据',
        'wx_group:view_group_fs_zt': '佛山报价中台数据',
        'wx_group:view_group_fs_kc': '查佛山库存卖价',
        'wx_group:view_group_hf_nb': '合峰内部查询群',
        'wx_group:view_group_kd': '开单群',
        'wx_group:view_group_hl': '湖南巴博瑞自动报价',
        'wx_group:view_group_zh_nb': '珠海巴博瑞内部查询群',
        'wx_group:view_group_gx_nb': '广西嘉昊内部查询群',
        'wx_group:view_group_gx_proxy': '广西嘉昊-代理价',
        'wx_group:view_group_gx_wholesale': '广西嘉昊-批发价',
        'wx_group:view_group_gx_retail': '广西嘉昊-零售价',
    },
    bypass_permission='wx_group:view_group_all',
)
def daily_summary_list_api():
    """
    获取每日汇总列表 API
    """
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        date = request.args.get('date')
        groupname = request.args.get('groupname')
        
        if groupname == '' or groupname == '全部':
            groupname = None
        
        if not date:
            return jsonify({
                'code': 400,
                'msg': '日期不能为空',
                'data': None
            })
        
        user_id = session.get('user_id')
        
        result = quote_summary_service.summarize_oe_codes_daily(
            start_date=date,
            end_date=date,
            groupname=groupname,
            page=page,
            limit=limit,
            user_id=user_id
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
@require_param_permission(
    param_name='groupname',
    permission_value_map={
        'wx_group': '全部',

        'wx_group:view_group_f3': 'F3查询群',
        'wx_group:view_group_fs_nb': '佛山巴博瑞内部查询群',
        'wx_group:view_group_fs_crm': '佛山报价CRM中台数据',
        'wx_group:view_group_fs_zt': '佛山报价中台数据',
        'wx_group:view_group_fs_kc': '查佛山库存卖价',
        'wx_group:view_group_hf_nb': '合峰内部查询群',
        'wx_group:view_group_kd': '开单群',
        'wx_group:view_group_hl': '湖南巴博瑞自动报价',
        'wx_group:view_group_zh_nb': '珠海巴博瑞内部查询群',
        'wx_group:view_group_gx_nb': '广西嘉昊内部查询群',
        'wx_group:view_group_gx_proxy': '广西嘉昊-代理价',
        'wx_group:view_group_gx_wholesale': '广西嘉昊-批发价',
        'wx_group:view_group_gx_retail': '广西嘉昊-零售价',
    },
    bypass_permission='wx_group:view_group_all',
)
def monthly_summary_list_api():
    """
    获取每月汇总列表 API
    """
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        month = request.args.get('month')
        groupname = request.args.get('groupname')
        
        if groupname == '' or groupname == '全部':
            groupname = None
        
        if not month:
            return jsonify({
                'code': 400,
                'msg': '月份不能为空',
                'data': None
            })
        
        user_id = session.get('user_id')
        
        result = quote_summary_service.summarize_oe_codes_monthly(
            month_str=month,
            groupname=groupname,
            page=page,
            limit=limit,
            user_id=user_id
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
