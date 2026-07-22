# -*- coding:utf-8 -*-
# @Time    : 2026/4/28 16:33
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : common_api.py
# @Software: PyCharm

from flask import jsonify, request, session

from app.core.permission.decorators import require_authentication


from . import report_wx_quote_data_bp
from app.services.report_wx_quote_data_services import wechat_daily_quote_detail_service
from app.services.report_wx_quote_data_services.get_permission import get_user_group_permissions


@report_wx_quote_data_bp.route('/groupname_list_api', methods=['GET'])
@require_authentication()
def groupname_list_api():
    """
    获取所有群名称列表 API
    """
    try:
        result = wechat_daily_quote_detail_service.fetch_groupname_list()
        return jsonify({
            'code': 200,
            'msg': '获取群名称列表成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取群名称列表失败: {str(e)}',
            'data': None
        })


@report_wx_quote_data_bp.route('/user_group_permissions_api', methods=['GET'])
@require_authentication()
def user_group_permissions_api():
    """
    获取当前用户的群权限列表 API

    返回用户拥有的 wx_group:view_group 前缀的权限列表，
    包含权限编码和对应的群名称。

    Returns:
        {
            "code": 200,
            "msg": "success",
            "data": [
                {"permission_code": "wx_group:view_group_f3", "group_name": "F3查询群"},
                ...
            ]
        }
    """
    try:
        user_id = session.get('user_id')
        permissions = get_user_group_permissions(user_id)  # pyright: ignore[reportArgumentType]
        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': permissions
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取用户权限失败: {str(e)}',
            'data': None
        })


@report_wx_quote_data_bp.route('/fetch_data_and_save_to_database_api', methods=['POST'])
@require_authentication()
def fetch_data_and_save_to_database_api():
    """
    获取并保存数据到数据库 API
    按10天分批处理指定日期范围的数据
    """
    try:
        from flask import request
        start_date = request.json.get('start_date')  # pyright: ignore[reportOptionalMemberAccess]
        end_date = request.json.get('end_date')  # pyright: ignore[reportOptionalMemberAccess]
        
        if not start_date or not end_date:
            return jsonify({
                'code': 400,
                'msg': '开始日期和结束日期不能为空',
                'data': None
            })
        
        wechat_daily_quote_detail_service.fetch_data_and_save_to_database(
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'code': 200,
            'msg': '数据获取并保存成功',
            'data': None
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'数据获取并保存失败: {str(e)}',
            'data': None
        })
